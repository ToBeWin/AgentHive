import { useEffect, useMemo, useRef, useState } from "react";
import { useChatConsole, useWorkbenchAgentInstances } from "../../hooks/useAdminData";
import { useLocale } from "../../i18n-context";
import { agentDisplayName, localizedTaskTitle, maxTokensForAgent } from "../../lib/agentDisplay";
import type { AuthUser, ChatSessionResponse, WorkbenchAgentInstanceResponse } from "../../lib/api";
import { canAccess } from "../../lib/permissions";
import { latestAssistantRunDetails } from "../chat/chatRunDetails";
import { categoryForEmployee, categoryOrder, type EmployeeCategory } from "./agentCategory";

export interface ActiveEmployeeTaskSummary {
  completedAt: string | null;
  hasResult: boolean;
  latestAnswer: string;
  modelKey: string;
  providerKey: string;
  requestId: string;
  statusKey: string;
  title: string;
  totalTokens: string;
  workflowKey: string | null;
}

export function useDigitalEmployeesController({
  isPrototype = false,
  user = null,
}: {
  isPrototype?: boolean;
  user?: AuthUser | null;
}) {
  const { locale, t } = useLocale();
  const chat = useChatConsole({ fallbackOnError: isPrototype });
  const {
    data: agentInstances,
    error,
    loading,
    refetch,
  } = useWorkbenchAgentInstances({
    fallbackOnError: isPrototype,
  });
  const canUseAgents = isPrototype || canAccess(user, ["agents:read", "chat:read", "chat:write"]);
  const canChat = isPrototype || canAccess(user, ["chat:write"]);
  const canInspectEvidence =
    isPrototype || canAccess(user, ["agents:write", "audit:read", "budgets:read", "models:read"]);
  const activeEmployees = useMemo(
    () => (agentInstances ?? []).filter((instance) => instance.status === "active"),
    [agentInstances],
  );
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(
    () => window.sessionStorage.getItem("agenthive.selected_agent_id") ?? "",
  );
  const [activeCategory, setActiveCategory] = useState<EmployeeCategory>("all");
  const [draft, setDraft] = useState("");
  const [agentsCollapsed, setAgentsCollapsed] = useState(false);
  const [resultPanelOpen, setResultPanelOpen] = useState(true);
  const [selectedWorkflowKey, setSelectedWorkflowKey] = useState<string | null>(null);
  const [copiedResult, setCopiedResult] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const visibleEmployees = useMemo(
    () =>
      activeCategory === "all"
        ? activeEmployees
        : activeEmployees.filter((employee) => categoryForEmployee(employee) === activeCategory),
    [activeCategory, activeEmployees],
  );
  const selectedEmployee =
    visibleEmployees.find((employee) => employee.id === selectedEmployeeId) ??
    visibleEmployees.find((employee) => employee.id === chat.activeSession?.agent_id) ??
    visibleEmployees[0] ??
    activeEmployees[0] ??
    null;
  const categoryCounts = useMemo(
    () =>
      Object.fromEntries(
        categoryOrder.map((category) => [
          category,
          category === "all"
            ? activeEmployees.length
            : activeEmployees.filter((employee) => categoryForEmployee(employee) === category).length,
        ]),
      ) as Record<EmployeeCategory, number>,
    [activeEmployees],
  );
  const latestAssistantMessage = useMemo(
    () => [...chat.messages].reverse().find((message) => message.role === "assistant" && message.content.trim()),
    [chat.messages],
  );
  const latestRunDetails = useMemo(
    () => latestAssistantRunDetails(latestAssistantMessage ? [latestAssistantMessage] : []),
    [latestAssistantMessage],
  );
  const latestUserMessage = useMemo(
    () => [...chat.messages].reverse().find((message) => message.role !== "assistant" && message.content.trim()),
    [chat.messages],
  );
  const selectedEmployeeSessions = useMemo(
    () => (chat.sessions.data ?? []).filter((session) => session.agent_id === selectedEmployee?.id),
    [chat.sessions.data, selectedEmployee?.id],
  );
  const taskStatusKey = chat.sending
    ? "digitalEmployeesTaskStatusRunning"
    : latestAssistantMessage
      ? "digitalEmployeesTaskStatusCompleted"
      : "digitalEmployeesTaskStatusReady";
  const activeSessionTitle =
    chat.activeSession && chat.activeSession.agent_id === selectedEmployee?.id
      ? localizedTaskTitle(chat.activeSession.title, locale)
      : "";
  const lastTask = useMemo(() => recordValue(chat.activeSession?.metadata.last_task), [chat.activeSession?.metadata]);
  const currentTaskTitle = latestUserMessage?.content || draft || activeSessionTitle || t("digitalEmployeesNoTaskYet");
  const activeTaskSummary = useMemo<ActiveEmployeeTaskSummary>(
    () => ({
      completedAt: stringOrNull(lastTask?.completed_at),
      hasResult: Boolean(latestAssistantMessage?.content.trim()),
      latestAnswer: latestAssistantMessage?.content.trim() ?? "",
      modelKey: stringOrFallback(lastTask?.model_key, latestRunDetails.modelKey),
      providerKey: stringOrFallback(lastTask?.provider_key, latestRunDetails.providerKey),
      requestId: stringOrFallback(lastTask?.request_id, latestRunDetails.requestId),
      statusKey: taskStatusKey,
      title: stringOrFallback(lastTask?.title, currentTaskTitle),
      totalTokens: stringOrFallback(lastTask?.total_tokens, latestRunDetails.runtimeTotalTokens),
      workflowKey: stringOrNull(lastTask?.workflow_key) ?? selectedWorkflowKey,
    }),
    [
      currentTaskTitle,
      lastTask,
      latestAssistantMessage?.content,
      latestRunDetails.modelKey,
      latestRunDetails.providerKey,
      latestRunDetails.requestId,
      latestRunDetails.runtimeTotalTokens,
      selectedWorkflowKey,
      taskStatusKey,
    ],
  );

  const applyStarter = (starterKey: string) => {
    setSelectedWorkflowKey(starterKey);
    setDraft(t(starterKey));
    window.requestAnimationFrame(() => inputRef.current?.focus());
  };

  const copyLatestAnswer = async () => {
    if (!latestAssistantMessage?.content) {
      return;
    }
    await navigator.clipboard?.writeText(latestAssistantMessage.content);
    setCopiedResult(true);
    window.setTimeout(() => setCopiedResult(false), 1600);
  };

  const refineLatestAnswer = () => {
    setDraft(t("digitalEmployeesFollowUpPrompt"));
    window.requestAnimationFrame(() => inputRef.current?.focus());
  };

  const selectEmployee = (employee: WorkbenchAgentInstanceResponse) => {
    setSelectedEmployeeId(employee.id);
    setSelectedWorkflowKey(null);
    window.sessionStorage.setItem("agenthive.selected_agent_id", employee.id);
  };

  const startConversation = async (employee: WorkbenchAgentInstanceResponse | null) => {
    if (!employee || !canChat) {
      return null;
    }
    setSelectedEmployeeId(employee.id);
    return await chat.createSession({
      agent_id: employee.id,
      metadata: {
        agent_key: employee.agent_key,
        surface: "agent_workbench",
      },
      source: "agent_workbench",
      title: agentDisplayName(employee, locale),
    });
  };

  const send = async (contentOverride?: string) => {
    const content = (contentOverride ?? draft).trim();
    if (!selectedEmployee || !canChat || selectedEmployee.runnable === false || !content || chat.sending) {
      return;
    }
    setDraft("");
    const session = await ensureEmployeeSession(selectedEmployee);
    await chat.sendMessage(
      {
        content,
        max_tokens: maxTokensForAgent(selectedEmployee.agent_key),
        metadata: {
          agent_key: selectedEmployee.agent_key,
          surface: "agent_workbench",
          workflow_key: selectedWorkflowKey ?? undefined,
        },
      },
      session ? { session } : undefined,
    );
    setResultPanelOpen(true);
  };

  const ensureEmployeeSession = async (
    employee: WorkbenchAgentInstanceResponse,
  ): Promise<ChatSessionResponse | null> => {
    if (chat.activeSession?.agent_id === employee.id) {
      return chat.activeSession;
    }
    return await startConversation(employee);
  };

  useEffect(() => {
    const media = window.matchMedia("(max-width: 900px)");
    const syncLayout = () => {
      if (media.matches) {
        setAgentsCollapsed(true);
        setResultPanelOpen(false);
      }
    };
    syncLayout();
    media.addEventListener("change", syncLayout);
    return () => media.removeEventListener("change", syncLayout);
  }, []);

  useEffect(() => {
    const handleSelectedAgent = (event: Event) => {
      const agentId = event instanceof CustomEvent ? event.detail?.agentId : null;
      if (typeof agentId === "string") {
        setActiveCategory("all");
        setSelectedEmployeeId(agentId);
      }
    };
    window.addEventListener("agenthive:selected-agent", handleSelectedAgent);
    return () => window.removeEventListener("agenthive:selected-agent", handleSelectedAgent);
  }, []);

  useEffect(() => {
    if (!selectedEmployee) {
      return;
    }
    if (chat.activeSession?.agent_id === selectedEmployee.id) {
      return;
    }
    chat.setActiveSession(selectedEmployeeSessions[0] ?? null);
  }, [chat.activeSession?.agent_id, chat.setActiveSession, selectedEmployee, selectedEmployeeSessions]);

  useEffect(() => {
    if (latestAssistantMessage?.id) {
      setResultPanelOpen(true);
    }
  }, [latestAssistantMessage?.id]);

  return {
    activeCategory,
    activeEmployees,
    activeTaskSummary,
    agentsCollapsed,
    applyStarter,
    canChat,
    canInspectEvidence,
    canUseAgents,
    categoryCounts,
    chat,
    copiedResult,
    copyLatestAnswer,
    draft,
    error,
    inputRef,
    latestAssistantMessage,
    loading,
    refetch,
    refineLatestAnswer,
    resultPanelOpen,
    selectEmployee,
    selectedEmployee,
    selectedEmployeeSessions,
    selectedWorkflowKey,
    send,
    setActiveCategory,
    setAgentsCollapsed,
    setDraft,
    setResultPanelOpen,
    startConversation,
    visibleEmployees,
  };
}

function recordValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function stringOrNull(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function stringOrFallback(value: unknown, fallback: string) {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return fallback && fallback !== "-" ? fallback : "-";
}
