import {
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Menu,
  Plus,
  RefreshCw,
  Search,
  SendHorizontal,
  Square,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ApiNotice, Button, cx, LoadingState, PageHeader, StatusBadge } from "../components/app-ui";
import { Markdown } from "../components/Markdown";
import { chatStreamStatusMessage, useAgentInstances, useChatConsole } from "../hooks/useAdminData";
import type { Locale } from "../i18n";
import { useLocale } from "../i18n-context";
import { agentDisplayName, localizedTaskTitle, maxTokensForAgent } from "../lib/agentDisplay";
import type { AuthUser, ChatMessageResponse, ChatStreamStatusResponse } from "../lib/api";
import { formatCurrency } from "../lib/formatters";
import { canAccess } from "../lib/permissions";
import { ChatRunDetailsPanel } from "./chat/ChatRunDetailsPanel";
import { MessageTraceSummary } from "./chat/MessageTraceSummary";

const CHAT_PRESELECT_AGENT_KEY = "agenthive.chat.preselect_agent_id";

type TranslateFn = (key: string) => string;

const AVATAR_COLORS = ["#006a61", "#3b5b8c", "#8c5a3b", "#7a3b8c", "#3b8c5a", "#8c6b3b", "#5a3b8c", "#3b7a8c"];

function avatarColorForKey(key: string | undefined): string {
  if (!key) return AVATAR_COLORS[0];
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = (hash * 31 + key.charCodeAt(i)) | 0;
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function avatarCharForName(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return "?";
  const first = Array.from(trimmed)[0] ?? "?";
  return first >= "a" && first <= "z" ? first.toUpperCase() : first;
}

function formatMessageTime(value: string, locale: Locale): string {
  try {
    return new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
  } catch {
    return "";
  }
}

function MessageItem({
  message,
  canInspectTrace,
  isLastAssistant,
  regenerateDisabled,
  onRegenerate,
  t,
  agentName,
  agentKey,
  locale,
}: {
  message: ChatMessageResponse;
  canInspectTrace: boolean;
  isLastAssistant: boolean;
  regenerateDisabled: boolean;
  onRegenerate: () => void;
  t: TranslateFn;
  agentName?: string;
  agentKey?: string;
  locale: Locale;
}) {
  const [traceOpen, setTraceOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const isAssistant = message.role === "assistant";
  const localState = (message.metadata?.local_state as string) || "";
  const streamStatus = message.metadata?.stream_status as ChatStreamStatusResponse | undefined;
  const isThinking = isAssistant && !message.content;
  const thinkingText = isThinking && streamStatus ? chatStreamStatusMessage(streamStatus, t) : t("chatGatewayRouting");
  const isStreaming = isAssistant && (localState === "stream_status" || localState === "streaming_response");
  const hasTrace = isAssistant && canInspectTrace && (message.model_key || message.total_tokens);
  const canCopy = isAssistant && !isThinking;
  const canRegenerate = isLastAssistant && !isStreaming && !isThinking;
  const displayName = isAssistant ? agentName || t("chatRoleAssistant") : t("chatRoleUser");
  const avatarChar = avatarCharForName(displayName);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard unavailable; ignore
    }
  };

  return (
    <div className={cx("message", isAssistant ? "assistant" : "user")}>
      <div className="message-header">
        {isAssistant && (
          <div className="message-avatar" style={{ background: avatarColorForKey(agentKey) }} aria-hidden="true">
            {avatarChar}
          </div>
        )}
        <strong>{displayName}</strong>
        {message.created_at && (
          <time className="message-time" dateTime={message.created_at}>
            {formatMessageTime(message.created_at, locale)}
          </time>
        )}
      </div>
      {isThinking ? (
        <div className="chat-thinking" role="status" aria-live="polite">
          <span className="thinking-dot" aria-hidden="true" />
          <span className="thinking-dot" aria-hidden="true" />
          <span className="thinking-dot" aria-hidden="true" />
          <span className="thinking-text">{thinkingText}</span>
        </div>
      ) : isAssistant ? (
        <Markdown className={isStreaming ? "streaming" : undefined}>{message.content}</Markdown>
      ) : (
        <p>{message.content}</p>
      )}
      {hasTrace && (
        <div className="message-trace">
          <button
            className="message-trace-toggle"
            onClick={() => setTraceOpen((v) => !v)}
            type="button"
            aria-expanded={traceOpen}
          >
            {traceOpen ? <ChevronDown size={12} aria-hidden="true" /> : <ChevronRight size={12} aria-hidden="true" />}
            {t("chatRunDetails")}
          </button>
          {traceOpen && (
            <div className="message-trace-body">
              <small>
                {message.model_key ?? t("chatRunModel")} · {message.total_tokens} {t("chatTokenUnit")} ·{" "}
                {formatCurrency(message.cost_usd)}
              </small>
              <MessageTraceSummary message={message} />
            </div>
          )}
        </div>
      )}
      {isAssistant && !canInspectTrace && !isStreaming && <small>{t("chatAssistantAnswerReady")}</small>}
      {canCopy && (
        <div className="message-actions">
          <button className="copy-button" onClick={handleCopy} type="button" aria-label={t("chatCopy")}>
            {copied ? <Check size={12} aria-hidden="true" /> : <Copy size={12} aria-hidden="true" />}
            {copied ? t("chatCopied") : t("chatCopy")}
          </button>
          {canRegenerate && (
            <button
              className="regenerate-button"
              disabled={regenerateDisabled}
              onClick={onRegenerate}
              type="button"
              aria-label={t("chatRegenerate")}
            >
              <RefreshCw size={12} aria-hidden="true" />
              {t("chatRegenerate")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function formatSessionTime(value: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
  }).format(new Date(value));
}

export function ChatPage({ isPrototype = false, user = null }: { isPrototype?: boolean; user?: AuthUser | null }) {
  const chat = useChatConsole({ fallbackOnError: isPrototype });
  const { data: agentInstances } = useAgentInstances({ fallbackOnError: isPrototype });
  const { locale, t } = useLocale();
  const canWriteChat = isPrototype || canAccess(user, ["chat:write"]);
  const canInspectTrace = isPrototype || canAccess(user, ["agents:write", "audit:read", "budgets:read", "models:read"]);
  const [draft, setDraft] = useState("");
  const [agentId, setAgentId] = useState("");
  const [sessionQuery, setSessionQuery] = useState("");
  const [traceOpen, setTraceOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [dismissedError, setDismissedError] = useState<string | null>(null);
  const streamRef = useRef<HTMLDivElement>(null);
  const isAtBottomRef = useRef(true);
  const [preselectAgentId] = useState(() => {
    const stored = window.sessionStorage.getItem(CHAT_PRESELECT_AGENT_KEY);
    if (stored) {
      window.sessionStorage.removeItem(CHAT_PRESELECT_AGENT_KEY);
      return stored;
    }
    return "";
  });
  const preselectHandledRef = useRef(false);
  const activeInstances = (agentInstances ?? []).filter((instance) => instance.status === "active");
  const activeSessionAgent = activeInstances.find((instance) => instance.id === chat.activeSession?.agent_id) ?? null;
  const filteredSessions = (chat.sessions.data ?? []).filter((session) => {
    if (!sessionQuery.trim()) return true;
    const q = sessionQuery.toLowerCase();
    const title = localizedTaskTitle(session.title, locale).toLowerCase();
    const source = (session.source ?? "").toLowerCase();
    return title.includes(q) || source.includes(q);
  });

  useEffect(() => {
    setAgentId(chat.activeSession?.agent_id ?? "");
  }, [chat.activeSession?.agent_id]);

  // One-shot: when arriving from the Agents page quick action, preselect the
  // agent and start a fresh session bound to it so the user can chat immediately.
  useEffect(() => {
    if (preselectHandledRef.current) {
      return;
    }
    if (!preselectAgentId || !canWriteChat) {
      return;
    }
    preselectHandledRef.current = true;
    setAgentId(preselectAgentId);
    void chat.createSession({
      agent_id: preselectAgentId,
      title: t("chatNewConversation"),
    });
  }, [preselectAgentId, canWriteChat, chat.createSession, t]);

  // Auto-scroll to bottom when new messages arrive or the last message streams in,
  // but only if the user is already near the bottom (so we don't yank them away
  // while reading earlier history). The messages array identity changes on every
  // update (new message, streaming delta, status change), which is what we want.
  const messagesLength = chat.messages.length;
  useEffect(() => {
    const el = streamRef.current;
    if (!el || !isAtBottomRef.current || chat.messages.length === 0) {
      return;
    }
    el.scrollTop = el.scrollHeight;
  }, [chat.messages]);

  const handleStreamScroll = () => {
    const el = streamRef.current;
    if (!el) {
      return;
    }
    isAtBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 100;
  };

  const send = () => {
    const content = draft.trim();
    if (!canWriteChat || !content || chat.sending) {
      return;
    }
    setDraft("");
    setDismissedError(null);
    void chat.sendMessage({
      content,
      max_tokens: maxTokensForAgent(activeSessionAgent?.agent_key),
      metadata: { surface: "admin_chat_console" },
    });
  };

  const regenerate = () => {
    if (!canWriteChat || chat.sending) {
      return;
    }
    const lastUserMessage = [...chat.messages].reverse().find((message) => message.role === "user");
    if (!lastUserMessage?.content) {
      return;
    }
    setDismissedError(null);
    void chat.sendMessage({
      content: lastUserMessage.content,
      max_tokens: maxTokensForAgent(activeSessionAgent?.agent_key),
      metadata: { surface: "admin_chat_console" },
    });
  };

  const lastMessage = chat.messages[messagesLength - 1];
  const lastAssistantIndex = lastMessage?.role === "assistant" ? messagesLength - 1 : -1;

  return (
    <section className="page chat-page">
      <PageHeader
        title={t("chatTitle")}
        subtitle={t("chatSubtitle")}
        actions={
          <Button
            disabled={!canWriteChat}
            onClick={() => {
              const selectedAgent = activeInstances.find((instance) => instance.id === agentId) ?? null;
              void chat.createSession({
                agent_id: agentId || null,
                metadata: {
                  agent_key: selectedAgent?.agent_key ?? undefined,
                },
                title: selectedAgent ? agentDisplayName(selectedAgent, locale) : t("chatNewConversation"),
              });
            }}
          >
            <Plus size={16} aria-hidden="true" /> {t("chatNewSession")}
          </Button>
        }
      />
      {(() => {
        // Blocking notices only: permission and session-load failures prevent
        // the chat surface from rendering at all. Action errors (send/stream
        // failures) are surfaced as a non-blocking banner so the conversation
        // history stays visible and the user can retry immediately.
        if (!canWriteChat) {
          return (
            <ApiNotice title={t("chatWritePermissionRequired")} message={t("chatWritePermissionRequiredDetail")} />
          );
        }
        if (chat.sessions.error && !chat.sessions.loading) {
          return (
            <ApiNotice
              title={t("chatLoadErrorTitle")}
              message={chat.sessions.error}
              action={<Button onClick={chat.refetchSessions}>{t("commonRetry")}</Button>}
            />
          );
        }
        if (chat.sessions.loading) {
          return <LoadingState message={t("chatLoadingSessionsMessage")} lines={3} />;
        }
        return null;
      })()}
      {chat.actionError && dismissedError !== chat.actionError && (
        <div className="chat-action-banner" role="alert">
          <div className="chat-action-banner-body">
            <strong>{t("chatActionErrorTitle")}</strong>
            <span>{chat.actionError}</span>
          </div>
          <button
            type="button"
            className="chat-action-banner-dismiss"
            onClick={() => setDismissedError(chat.actionError)}
            aria-label={t("chatDismissError")}
          >
            <X size={14} aria-hidden="true" />
          </button>
        </div>
      )}
      <div className="chat-layout">
        {sidebarOpen && (
          <button
            type="button"
            className="chat-sidebar-overlay"
            onClick={() => setSidebarOpen(false)}
            aria-label={t("chatSidebarClose")}
          />
        )}
        <aside className={cx("chat-sidebar", sidebarOpen && "open")}>
          <div className="chat-sidebar-head">
            <span className="chat-sidebar-title">{t("chatSessions")}</span>
            <button
              type="button"
              className="chat-sidebar-close"
              onClick={() => setSidebarOpen(false)}
              aria-label={t("chatSidebarClose")}
            >
              <X size={16} aria-hidden="true" />
            </button>
          </div>
          <div className="chat-session-search">
            <Search size={14} aria-hidden="true" />
            <input
              aria-label={t("chatSearchSessions")}
              onChange={(event) => setSessionQuery(event.target.value)}
              placeholder={t("chatSearchSessions")}
              type="search"
              value={sessionQuery}
            />
          </div>
          <div className="scope-list">
            {filteredSessions.map((session) => (
              <button
                className={cx("scope-row", chat.activeSession?.id === session.id && "selected")}
                key={session.id}
                onClick={() => {
                  chat.setActiveSession(session);
                  setSidebarOpen(false);
                }}
                type="button"
              >
                <span>
                  {localizedTaskTitle(session.title, locale)}
                  <small>{formatSessionTime(session.updated_at, locale)}</small>
                </span>
                <StatusBadge label={localizedSessionStatus(session.status, t)} status={session.status} />
              </button>
            ))}
            {filteredSessions.length === 0 && sessionQuery.trim() && (
              <p className="chat-session-empty">{t("chatNoSearchResults")}</p>
            )}
            {(chat.sessions.data ?? []).length === 0 && (
              <ApiNotice title={t("chatNoSessionsTitle")} message={t("chatNoSessionsMessage")} />
            )}
          </div>
        </aside>
        <div className="chat-main">
          <div className="chat-context-bar">
            <button
              type="button"
              className="chat-sidebar-toggle"
              onClick={() => setSidebarOpen(true)}
              aria-label={t("chatSidebarOpen")}
            >
              <Menu size={16} aria-hidden="true" />
            </button>
            <label className="chat-context-agent">
              <span>{t("chatAgentInstance")}</span>
              <select disabled={!canWriteChat} value={agentId} onChange={(event) => setAgentId(event.target.value)}>
                <option value="">{t("chatNoAgentInstance")}</option>
                {activeInstances.map((instance) => (
                  <option key={instance.id} value={instance.id}>
                    {agentDisplayName(instance, locale)}
                  </option>
                ))}
              </select>
            </label>
            <div className="chat-context-summary">
              {chat.activeSession ? (
                <>
                  <strong>{localizedTaskTitle(chat.activeSession.title, locale)}</strong>
                  <span className="chat-context-meta">
                    {activeSessionAgent
                      ? agentDisplayName(activeSessionAgent, locale)
                      : localizedSource(chat.activeSession.source, t)}
                    {" · "}
                    {chat.messages.length} {t("chatMessages")}
                  </span>
                </>
              ) : (
                <strong className="chat-context-placeholder">{t("chatNoSessionSelected")}</strong>
              )}
            </div>
            {canInspectTrace && (
              <button
                type="button"
                className="chat-trace-toggle"
                onClick={() => setTraceOpen((value) => !value)}
                aria-expanded={traceOpen}
              >
                {traceOpen ? (
                  <ChevronDown size={14} aria-hidden="true" />
                ) : (
                  <ChevronRight size={14} aria-hidden="true" />
                )}
                {t("chatRunDetails")}
              </button>
            )}
          </div>
          {traceOpen && canInspectTrace && <ChatRunDetailsPanel messages={chat.messages} />}
          <section className="panel chat-window">
            <div
              className="chat-stream"
              onScroll={handleStreamScroll}
              ref={streamRef}
              role="log"
              aria-label={t("chatMessages")}
              aria-live="polite"
              aria-busy={chat.sending}
            >
              {chat.messages.map((message, index) => (
                <MessageItem
                  key={message.id}
                  canInspectTrace={canInspectTrace}
                  isLastAssistant={index === lastAssistantIndex}
                  message={message}
                  onRegenerate={regenerate}
                  regenerateDisabled={chat.sending}
                  t={t}
                  agentName={activeSessionAgent ? agentDisplayName(activeSessionAgent, locale) : undefined}
                  agentKey={activeSessionAgent?.agent_key}
                  locale={locale}
                />
              ))}
              {chat.messages.length === 0 && (
                <div className="message assistant">
                  <strong>{t("chatRoleAssistant")}</strong>
                  <p>{t("chatAssistantReady")}</p>
                  {!chat.activeSession && <p className="chat-empty-hint">{t("chatEmptyStartHint")}</p>}
                </div>
              )}
            </div>
            <div className="chat-input">
              <textarea
                aria-label={t("chatPlaceholder")}
                disabled={!canWriteChat}
                onChange={(event) => {
                  setDraft(event.target.value);
                  // Auto-resize: reset height then grow with content (cap at 160px)
                  const el = event.target;
                  el.style.height = "auto";
                  el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    send();
                  }
                }}
                placeholder={`${t("chatPlaceholder")} (Enter ${t("chatSend")}, Shift+Enter ↵)`}
                rows={1}
                value={draft}
              />
              {chat.sending ? (
                <Button variant="ghost" onClick={chat.stopGeneration} aria-label={t("chatStopGeneration")}>
                  <Square size={14} aria-hidden="true" /> {t("chatStop")}
                </Button>
              ) : (
                <Button variant="primary" onClick={send} disabled={!canWriteChat || !draft.trim()}>
                  <SendHorizontal size={16} aria-hidden="true" /> {t("chatSend")}
                </Button>
              )}
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

function localizedSessionStatus(status: string, t: (key: string) => string) {
  const normalized = status.toLowerCase();
  if (normalized === "active") {
    return t("chatSessionStatusActive");
  }
  if (normalized === "archived") {
    return t("chatSessionStatusArchived");
  }
  return status;
}

function localizedSource(source: string | null | undefined, t: (key: string) => string) {
  if (!source) {
    return t("chatSourceChatConsole");
  }
  if (source === "chat_console") {
    return t("chatSourceChatConsole");
  }
  if (source === "agent_workbench") {
    return t("chatSourceAgentWorkbench");
  }
  return source;
}
