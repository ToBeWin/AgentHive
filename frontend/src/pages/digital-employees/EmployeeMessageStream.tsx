import { Bot, Sparkles, UserRound } from "lucide-react";
import { useEffect, useRef } from "react";
import { cx } from "../../components/app-ui";
import { Markdown } from "../../components/Markdown";
import { useLocale } from "../../i18n-context";
import { agentDisplayName } from "../../lib/agentDisplay";
import type { ChatMessageResponse, WorkbenchAgentInstanceResponse } from "../../lib/api";
import { EmployeeMessageRuntimeMeta } from "./EmployeeMessageRuntimeMeta";
import { hasActiveStreamMessage, isStreamingAssistantMessage } from "./employeeMessageStreamUtils";

function messageInitials(label: string) {
  const trimmed = label.trim();
  if (!trimmed) {
    return "AI";
  }
  if (/[\u4e00-\u9fff]/.test(trimmed)) {
    return trimmed.slice(0, 2);
  }
  const parts = trimmed.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase();
  }
  return trimmed.slice(0, 2).toUpperCase();
}

function formatMessageTime(value: string | undefined, locale: string) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat(locale, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function renderMessageBody(content: string) {
  return content.split("\n").map((line) => (
    <span className="employee-message-line" key={`${line.length}:${line.slice(0, 24)}`}>
      {line || "\u00a0"}
    </span>
  ));
}

export function EmployeeMessageStream({
  canChat,
  canInspectEvidence,
  messages,
  onApplyStarter,
  selectedEmployee,
  sending,
  starterKeys,
}: {
  canChat: boolean;
  canInspectEvidence: boolean;
  messages: ChatMessageResponse[];
  onApplyStarter: (starterKey: string) => void;
  selectedEmployee: WorkbenchAgentInstanceResponse | null;
  sending: boolean;
  starterKeys: readonly string[];
}) {
  const { locale, t } = useLocale();
  const streamRef = useRef<HTMLDivElement | null>(null);
  const assistantLabel = selectedEmployee ? agentDisplayName(selectedEmployee, locale) : t("digitalEmployeesAssistant");

  const scrollAnchor = `${messages.at(-1)?.id ?? "empty"}:${messages.at(-1)?.content?.length ?? 0}:${sending ? "typing" : "idle"}`;
  const showTypingIndicator = sending && !hasActiveStreamMessage(messages);

  // biome-ignore lint/correctness/useExhaustiveDependencies: scroll when message list or typing state changes
  useEffect(() => {
    const node = streamRef.current;
    if (!node) {
      return;
    }
    node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [scrollAnchor]);

  return (
    <div className="employee-message-stream" ref={streamRef}>
      {messages.length ? (
        messages.map((message) => {
          const isAssistant = message.role === "assistant";
          const label = isAssistant ? assistantLabel : t("digitalEmployeesMe");
          return (
            <article
              className={cx(
                "employee-message",
                isAssistant ? "assistant" : "user",
                isStreamingAssistantMessage(message) && "streaming",
              )}
              key={message.id}
            >
              <div className="employee-message-head">
                <span className={cx("employee-message-avatar", isAssistant ? "assistant" : "user")}>
                  {isAssistant ? <Bot size={15} /> : <UserRound size={15} />}
                  <i>{messageInitials(label)}</i>
                </span>
                <div className="employee-message-meta">
                  <strong>{label}</strong>
                  {formatMessageTime(message.created_at, locale) ? (
                    <time dateTime={message.created_at}>{formatMessageTime(message.created_at, locale)}</time>
                  ) : null}
                </div>
              </div>
              <div className="employee-message-body">
                {message.content ? (
                  isAssistant ? (
                    <Markdown className={isStreamingAssistantMessage(message) ? "streaming" : undefined}>
                      {message.content}
                    </Markdown>
                  ) : (
                    renderMessageBody(message.content)
                  )
                ) : (
                  <span>{t("digitalEmployeesWorking")}</span>
                )}
              </div>
              {canInspectEvidence && isAssistant ? <EmployeeMessageRuntimeMeta message={message} /> : null}
            </article>
          );
        })
      ) : (
        <article className="employee-message assistant employee-message-welcome">
          <div className="employee-message-head">
            <span className="employee-message-avatar assistant">
              <Bot size={15} />
              <i>{messageInitials(assistantLabel)}</i>
            </span>
            <div className="employee-message-meta">
              <strong>{assistantLabel}</strong>
              <span>{t("digitalEmployeesWelcomeEyebrow")}</span>
            </div>
          </div>
          <div className="employee-message-body">{t("digitalEmployeesWelcome")}</div>
          {selectedEmployee && canChat && (
            <fieldset className="employee-start-suggestions">
              <legend>{t("digitalEmployeesStarterTitle")}</legend>
              {starterKeys.slice(0, 3).map((starterKey) => (
                <button key={starterKey} onClick={() => onApplyStarter(starterKey)} type="button">
                  <Sparkles size={14} />
                  {t(starterKey)}
                </button>
              ))}
            </fieldset>
          )}
        </article>
      )}

      {showTypingIndicator ? (
        <article className="employee-message assistant employee-message-typing" aria-live="polite">
          <div className="employee-message-head">
            <span className="employee-message-avatar assistant">
              <Bot size={15} />
              <i>{messageInitials(assistantLabel)}</i>
            </span>
            <div className="employee-message-meta">
              <strong>{assistantLabel}</strong>
              <span>{t("digitalEmployeesTyping")}</span>
            </div>
          </div>
          <div className="employee-typing-dots" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
        </article>
      ) : null}
    </div>
  );
}
