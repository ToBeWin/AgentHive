import { SendHorizontal } from "lucide-react";
import { Button } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { ChatMessageResponse, WorkbenchAgentInstanceResponse } from "../../lib/api";
import { AgentRuntimeBlocker } from "./AgentRuntimeBlocker";
import { workflowActionKeys } from "./agentCategory";
import { EmployeeMessageStream } from "./EmployeeMessageStream";
import { EmployeeQuickPrompts } from "./EmployeeQuickPrompts";

export function EmployeeConversationPanel({
  canChat,
  canInspectEvidence,
  draft,
  inputRef,
  messages,
  onApplyStarter,
  onDraftChange,
  onSend,
  selectedEmployee,
  sending,
}: {
  canChat: boolean;
  canInspectEvidence: boolean;
  draft: string;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  messages: ChatMessageResponse[];
  onApplyStarter: (starterKey: string) => void;
  onDraftChange: (draft: string) => void;
  onSend: () => void;
  selectedEmployee: WorkbenchAgentInstanceResponse | null;
  sending: boolean;
}) {
  const { t } = useLocale();
  const agentRunnable = selectedEmployee?.runnable !== false;
  const starterKeys = workflowActionKeys(selectedEmployee);
  const hasMessages = messages.some((message) => message.content.trim());

  return (
    <section className="employee-conversation-panel">
      <EmployeeMessageStream
        canChat={canChat && agentRunnable}
        canInspectEvidence={canInspectEvidence}
        messages={messages}
        onApplyStarter={onApplyStarter}
        selectedEmployee={selectedEmployee}
        sending={sending}
        starterKeys={starterKeys}
      />

      {selectedEmployee && !agentRunnable && (
        <AgentRuntimeBlocker
          canInspectEvidence={canInspectEvidence}
          onShowRunEvidence={() => undefined}
          selectedEmployee={selectedEmployee}
        />
      )}

      <div className="employee-conversation-footer">
        {!hasMessages && starterKeys.length > 0 ? (
          <EmployeeQuickPrompts
            disabled={!selectedEmployee || !canChat || !agentRunnable}
            onSelect={onApplyStarter}
            promptKeys={starterKeys}
          />
        ) : null}

        <div className="employee-composer">
          <textarea
            ref={inputRef}
            disabled={!selectedEmployee || !canChat || !agentRunnable}
            onChange={(event) => onDraftChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                onSend();
              }
            }}
            placeholder={t("digitalEmployeesInputPlaceholder")}
            rows={1}
            value={draft}
          />
          <Button
            disabled={!selectedEmployee || !canChat || !agentRunnable || !draft.trim() || sending}
            onClick={onSend}
            variant="primary"
          >
            <SendHorizontal size={16} />
            {!agentRunnable
              ? t("digitalEmployeesAgentNotRunnableAction")
              : sending
                ? t("digitalEmployeesSending")
                : t("digitalEmployeesSend")}
          </Button>
        </div>
      </div>
    </section>
  );
}
