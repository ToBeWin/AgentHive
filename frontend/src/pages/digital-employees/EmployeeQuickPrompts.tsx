import { Sparkles } from "lucide-react";
import { useLocale } from "../../i18n-context";

export function EmployeeQuickPrompts({
  disabled,
  onSelect,
  promptKeys,
}: {
  disabled?: boolean;
  onSelect: (promptKey: string) => void;
  promptKeys: readonly string[];
}) {
  const { t } = useLocale();

  if (promptKeys.length === 0) {
    return null;
  }

  return (
    <section className="employee-quick-prompts" aria-label={t("digitalEmployeesQuickPrompts")}>
      <span>{t("digitalEmployeesQuickPrompts")}</span>
      <div className="employee-quick-prompts-list">
        {promptKeys.slice(0, 4).map((promptKey) => (
          <button
            className="employee-quick-prompt"
            disabled={disabled}
            key={promptKey}
            onClick={() => onSelect(promptKey)}
            type="button"
          >
            <Sparkles size={14} />
            {t(promptKey)}
          </button>
        ))}
      </div>
    </section>
  );
}
