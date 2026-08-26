import { Bot, CheckCircle2, FileSearch, Upload } from "lucide-react";
import { Button, cx } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";

interface KnowledgeAgentBindingPanelProps {
  hasDocuments: boolean;
  hasIndexedDocuments: boolean;
  onOpenAgentBinding: () => void;
  onOpenRetrieval: () => void;
  selected: boolean;
}

export function KnowledgeAgentBindingPanel({
  hasDocuments,
  hasIndexedDocuments,
  onOpenAgentBinding,
  onOpenRetrieval,
  selected,
}: KnowledgeAgentBindingPanelProps) {
  const { t } = useLocale();

  return (
    <div className="kb-docs-section">
      <KnowledgeHandoffSteps
        hasDocuments={hasDocuments}
        hasIndexedDocuments={hasIndexedDocuments}
        onOpenAgentBinding={onOpenAgentBinding}
        onOpenRetrieval={onOpenRetrieval}
        selected={selected}
      />
      <div className="knowledge-binding-summary">
        <div>
          <Bot size={18} />
          <strong>{t("knowledgeBindingSummaryTitle")}</strong>
          <p>{t("knowledgeBindingSummaryBody")}</p>
        </div>
        <Button onClick={onOpenAgentBinding} disabled={!selected}>
          <Bot size={15} /> {t("knowledgeHandoffBindAgent")}
        </Button>
      </div>
    </div>
  );
}

function KnowledgeHandoffSteps({
  hasDocuments,
  hasIndexedDocuments,
  onOpenAgentBinding,
  onOpenRetrieval,
  selected,
}: KnowledgeAgentBindingPanelProps) {
  const { t } = useLocale();
  const steps = [
    {
      action: null,
      done: selected && hasDocuments,
      icon: Upload,
      text: t("knowledgeHandoffUpload"),
    },
    {
      action: onOpenRetrieval,
      done: selected && hasIndexedDocuments,
      icon: FileSearch,
      text: t("knowledgeHandoffRetrieval"),
    },
    {
      action: onOpenAgentBinding,
      done: false,
      icon: Bot,
      text: t("knowledgeHandoffBindAgent"),
    },
  ];

  return (
    <fieldset className="knowledge-handoff-steps">
      <legend>{t("knowledgeHandoffTitle")}</legend>
      {steps.map((step) => {
        const Icon = step.done ? CheckCircle2 : step.icon;
        if (!step.action) {
          return (
            <span className={cx(step.done && "done")} key={step.text}>
              <Icon size={15} />
              {step.text}
            </span>
          );
        }
        return (
          <button
            className={cx(step.done && "done")}
            disabled={!selected}
            key={step.text}
            onClick={step.action}
            type="button"
          >
            <Icon size={15} />
            {step.text}
          </button>
        );
      })}
    </fieldset>
  );
}
