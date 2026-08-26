import { CheckCircle2, Eye, FileEdit, Save } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiNotice, Button, cx, PageHeader, PageTabs } from "../components/app-ui";
import { useAgentGovernanceTargets, useAgentInstances, useBuilderActions, useMcpServers } from "../hooks/useAdminData";
import { useLocale } from "../i18n-context";
import type { AgentInstanceResponse, AuthUser } from "../lib/api";
import { canAccess } from "../lib/permissions";
import { BuilderForm } from "./builder/BuilderForm";
import { BuilderPreviewPanel } from "./builder/BuilderPreviewPanel";
import {
  type AgentKnowledgeBaseOption,
  type AgentMcpServerOption,
  type AgentModelDeploymentOption,
  type BuilderFormState,
  configToForm,
  deriveRuntimeHints,
  emptyBuilderForm,
  formToConfig,
} from "./builder/builderUtils";

type BuilderTab = "editor" | "preview";

interface BuilderPageProps {
  isPrototype?: boolean;
  user?: AuthUser | null;
}

const NOTICE_AUTO_DISMISS_MS = 4000;
const BUILDER_PRESELECT_INSTANCE_KEY = "agenthive.builder.preselect_instance_id";

export function BuilderPage({ isPrototype = false, user = null }: BuilderPageProps) {
  const { locale, t } = useLocale();
  const canWrite = isPrototype || canAccess(user, ["agents:write"]);

  const [activeTab, setActiveTab] = useState<BuilderTab>("editor");
  const [form, setForm] = useState<BuilderFormState>(emptyBuilderForm);
  const [editingInstanceId, setEditingInstanceId] = useState<string | null>(null);
  const [localNotice, setLocalNotice] = useState("");
  const [savedSnapshot, setSavedSnapshot] = useState<BuilderFormState | null>(null);
  // In create mode the instances rail is hidden by default to let the form
  // use the full width. The user can opt-in to show it via "Switch instance".
  const [showInstancesRail, setShowInstancesRail] = useState(false);
  const [preselectInstanceId] = useState(() => {
    const stored = window.sessionStorage.getItem(BUILDER_PRESELECT_INSTANCE_KEY);
    if (stored) {
      window.sessionStorage.removeItem(BUILDER_PRESELECT_INSTANCE_KEY);
      return stored;
    }
    return "";
  });
  const preselectHandledRef = useRef(false);

  const { data: governanceTargets, error: govError } = useAgentGovernanceTargets({
    fallbackOnError: isPrototype,
  });
  const { data: mcpServers, error: mcpError } = useMcpServers({ fallbackOnError: isPrototype });
  const { data: instances, refetch: refetchInstances } = useAgentInstances({
    fallbackOnError: isPrototype,
  });
  const actions = useBuilderActions({ fallbackOnError: isPrototype });

  const knowledgeBases: AgentKnowledgeBaseOption[] = useMemo(
    () =>
      (governanceTargets?.knowledge_bases ?? []).map((target) => ({
        id: target.id,
        name: String(target.metadata.name ?? target.label),
        rag_engine: String(target.metadata.rag_engine ?? ""),
      })),
    [governanceTargets],
  );

  const modelDeployments: AgentModelDeploymentOption[] = useMemo(
    () =>
      (governanceTargets?.model_deployments ?? []).map((target) => ({
        id: target.id,
        label: target.label,
        routing_key: String(target.metadata.routing_key ?? ""),
      })),
    [governanceTargets],
  );

  const mcpServerOptions: AgentMcpServerOption[] = useMemo(
    () =>
      (mcpServers ?? []).map((server) => ({
        id: server.id,
        name: server.name,
        server_key: server.server_key,
        status: server.status,
      })),
    [mcpServers],
  );

  const builderInstances = useMemo(
    () => (instances ?? []).filter((instance) => instance.agent_key === "custom_builder"),
    [instances],
  );

  const onFieldChange = useCallback(
    <K extends keyof BuilderFormState>(field: K, value: BuilderFormState[K]) => {
      setForm((current) => ({ ...current, [field]: value }));
      // Clear stale validation so the save button isn't locked by the previous
      // failed report while the user is editing.
      actions.clearValidation();
    },
    [actions],
  );

  // Real-time hints derived from form state (mirrors backend cross-field validators).
  const runtimeHints = useMemo(() => deriveRuntimeHints(form, locale), [form, locale]);

  const formHasUnsavedChanges = useMemo(() => {
    if (!savedSnapshot) return form !== emptyBuilderForm;
    return JSON.stringify(savedSnapshot) !== JSON.stringify(form);
  }, [form, savedSnapshot]);

  const confirmDiscardIfDirty = useCallback((): boolean => {
    if (!formHasUnsavedChanges) return true;
    return window.confirm(t("builderUnsavedChanges"));
  }, [formHasUnsavedChanges, t]);

  const resetForm = useCallback(() => {
    if (!confirmDiscardIfDirty()) return;
    setForm(emptyBuilderForm);
    setSavedSnapshot(null);
    setEditingInstanceId(null);
    setShowInstancesRail(false);
    actions.reset();
  }, [actions, confirmDiscardIfDirty]);

  const startEdit = useCallback(
    (instance: AgentInstanceResponse) => {
      if (editingInstanceId !== instance.id && !confirmDiscardIfDirty()) return;
      const builderConfig = (instance.config?.builder_config as { config?: unknown } | undefined)?.config;
      if (!builderConfig) {
        setLocalNotice(t("builderEditNoConfig"));
        return;
      }
      const next = configToForm(builderConfig as Parameters<typeof configToForm>[0]);
      setForm(next);
      setSavedSnapshot(next);
      setEditingInstanceId(instance.id);
      setShowInstancesRail(false);
      actions.reset();
      setActiveTab("editor");
    },
    [actions, confirmDiscardIfDirty, editingInstanceId, t],
  );

  const handleValidate = useCallback(async () => {
    await actions.validate(formToConfig(form));
    // Do NOT force tab switch — let the user stay in the editor to see inline
    // field-level feedback. They can click the Preview tab manually.
  }, [actions, form]);

  const handlePreview = useCallback(async () => {
    await actions.runPreview(formToConfig(form));
    setActiveTab("preview");
  }, [actions, form]);

  const inFlightRef = useRef(false);
  const handleSave = useCallback(async () => {
    if (inFlightRef.current) return; // de-dup concurrent save attempts
    inFlightRef.current = true;
    try {
      const config = formToConfig(form);
      const report = await actions.validate(config);
      if (report && !report.ok) {
        // Stay in the editor so the user sees inline field-level errors
        // instead of being yanked to the preview tab.
        return;
      }
      if (editingInstanceId) {
        const updated = await actions.updateInstance(editingInstanceId, config);
        if (updated) setSavedSnapshot(form);
      } else {
        const saved = await actions.createInstance(config);
        if (saved) {
          setEditingInstanceId(saved.id);
          setSavedSnapshot(form);
        }
      }
      void refetchInstances();
    } finally {
      inFlightRef.current = false;
    }
  }, [actions, editingInstanceId, form, refetchInstances]);

  // Auto-dismiss success/error notices after a delay so they don't linger forever.
  const noticeTimerRef = useRef<number | null>(null);
  useEffect(() => {
    if (noticeTimerRef.current !== null) {
      window.clearTimeout(noticeTimerRef.current);
      noticeTimerRef.current = null;
    }
    if (actions.message || actions.error || localNotice) {
      noticeTimerRef.current = window.setTimeout(() => {
        // Clear only transient notices — keep the underlying action state intact.
        setLocalNotice("");
      }, NOTICE_AUTO_DISMISS_MS);
    }
    return () => {
      if (noticeTimerRef.current !== null) window.clearTimeout(noticeTimerRef.current);
    };
  }, [actions.message, actions.error, localNotice]);

  // One-shot: when arriving from the Agents page quick action, load the target
  // instance into the editor as soon as the instance list is available.
  useEffect(() => {
    if (preselectHandledRef.current || !preselectInstanceId || !instances) {
      return;
    }
    const target = instances.find((instance) => instance.id === preselectInstanceId);
    if (!target) {
      return;
    }
    preselectHandledRef.current = true;
    startEdit(target);
  }, [preselectInstanceId, instances, startEdit]);

  const dismissNotice = useCallback(() => {
    setLocalNotice("");
    actions.reset();
  }, [actions]);

  const formIssues = actions.validation?.issues ?? actions.preview?.issues ?? [];

  // Edit mode always shows the instances rail so the user can switch between
  // existing configs. Create mode hides it by default (full-width form) but
  // lets the user opt-in via the "Switch instance" link in the banner.
  const railVisible = editingInstanceId !== null || showInstancesRail;

  // Stricter formValid: require name, system_prompt, AND at least one routing target.
  // This matches the backend _ensure_routing_target validator so the user can't
  // click Publish and get a server-side rejection.
  const hasRoutingTarget =
    form.deployment_id.trim() !== "" || form.model_key.trim() !== "" || form.routing_key.trim() !== "";
  const hasNoBlockingHint = !runtimeHints.some((hint) => hint.field !== "deployment_id"); // routing-target hint is the only blocker surfaced via hints on deployment_id
  const formValid =
    actions.validation?.ok ??
    (actions.validation === null &&
      form.name.length > 0 &&
      form.system_prompt.length > 0 &&
      hasRoutingTarget &&
      hasNoBlockingHint);

  // Suppress the unused-var lint for `hasNoBlockingHint` when not needed — it's part of formValid.
  void hasNoBlockingHint;

  return (
    <section className="page">
      <PageHeader
        title={t("builderTitle")}
        subtitle={t("builderSubtitle")}
        actions={
          <>
            <Button onClick={handleValidate} disabled={!canWrite || actions.validating} loading={actions.validating}>
              <CheckCircle2 size={16} /> {t("builderValidate")}
            </Button>
            <Button onClick={handlePreview} disabled={!canWrite || actions.previewing} loading={actions.previewing}>
              <Eye size={16} /> {t("builderPreview")}
            </Button>
            <Button
              variant="primary"
              onClick={handleSave}
              disabled={!canWrite || actions.saving || !formValid}
              loading={actions.saving}
            >
              <Save size={16} /> {editingInstanceId ? t("builderUpdate") : t("builderPublish")}
            </Button>
          </>
        }
      />

      {(govError || mcpError) && <ApiNotice title={t("builderLoadErrorTitle")} message={govError ?? mcpError ?? ""} />}

      {(localNotice || actions.error || actions.message) && (
        <div className={`form-message ${actions.error ? "error" : actions.message ? "success" : ""}`}>
          <span>{localNotice || actions.error || actions.message}</span>
          <button type="button" className="link-button" onClick={dismissNotice}>
            {t("builderNoticeDismiss")}
          </button>
        </div>
      )}

      <PageTabs
        active={activeTab}
        onChange={setActiveTab}
        tabs={[
          { id: "editor", label: t("builderTabEditor"), description: t("builderTabEditorDesc") },
          { id: "preview", label: t("builderTabPreview"), description: t("builderTabPreviewDesc") },
        ]}
      />

      {activeTab === "editor" && (
        <div
          className={cx(
            "nested-workspace",
            "builder-editor-workspace",
            !railVisible && "builder-editor-workspace--single",
          )}
        >
          <div className="builder-editor-form">
            <div className="builder-editing-banner">
              {editingInstanceId ? (
                <span>
                  <FileEdit size={14} /> {t("builderEditing").replace("{{id}}", editingInstanceId)}{" "}
                  <button type="button" className="link-button" onClick={resetForm}>
                    {t("builderReset")}
                  </button>
                </span>
              ) : (
                <span>
                  {t("builderCreating")}
                  {builderInstances.length > 0 && (
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => setShowInstancesRail((open) => !open)}
                      style={{ marginLeft: 8 }}
                    >
                      {showInstancesRail ? t("builderHideInstances") : t("builderSwitchInstance")}
                    </button>
                  )}
                </span>
              )}
              {formHasUnsavedChanges && (
                <span className="form-hint" style={{ marginLeft: "auto" }}>
                  {locale === "zh-CN" ? "未保存" : "unsaved"}
                </span>
              )}
            </div>
            <BuilderForm
              canWrite={canWrite}
              form={form}
              knowledgeBases={knowledgeBases}
              mcpServers={mcpServerOptions}
              modelDeployments={modelDeployments}
              onFieldChange={onFieldChange}
              issues={formIssues}
              runtimeHints={runtimeHints}
            />
          </div>
          {railVisible && (
            <aside className="builder-instances-rail">
              <h4>{t("builderExistingInstances")}</h4>
              <p className="form-hint">{t("builderExistingInstancesDesc")}</p>
              {builderInstances.length === 0 && (
                <div className="builder-empty-instances">{t("builderNoInstances")}</div>
              )}
              <ul className="builder-instance-list">
                {builderInstances.map((instance) => (
                  <li key={instance.id} className={editingInstanceId === instance.id ? "active" : ""}>
                    <button type="button" onClick={() => startEdit(instance)}>
                      <strong>{instance.name}</strong>
                      <small>{instance.agent_key}</small>
                      <span>{instance.status}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </aside>
          )}
        </div>
      )}

      {activeTab === "preview" && (
        <BuilderPreviewPanel
          preview={actions.preview}
          issues={formIssues}
          validating={actions.validating}
          previewing={actions.previewing}
        />
      )}
    </section>
  );
}
