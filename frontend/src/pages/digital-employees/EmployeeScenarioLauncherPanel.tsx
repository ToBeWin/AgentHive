import {
  BarChart3,
  BookOpen,
  ClipboardCheck,
  Landmark,
  type LucideIcon,
  Megaphone,
  Sparkles,
  Store,
  UserRoundCheck,
  UsersRound,
} from "lucide-react";
import { useState } from "react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { agentDisplayName } from "../../lib/agentDisplay";
import type { WorkbenchAgentInstanceResponse } from "../../lib/api";
import { categoryForEmployee, type EmployeeCategory } from "./agentCategory";

type ScenarioCategory = Exclude<EmployeeCategory, "all" | "general">;

interface EmployeeScenarioLauncherPanelProps {
  activeEmployees: WorkbenchAgentInstanceResponse[];
  canChat: boolean;
  canInspectEvidence: boolean;
  canReadKnowledge: boolean;
  onOpenEvidence: () => void;
  onOpenGuide: () => void;
  onOpenKnowledge: () => void;
  onSelectScenario: (category: ScenarioCategory, workflowKey: string) => void;
  selectedEmployee: WorkbenchAgentInstanceResponse | null;
  selectedWorkflowKey: string | null;
}

interface ScenarioDefinition {
  category: ScenarioCategory;
  descriptionKey: string;
  icon: LucideIcon;
  titleKey: string;
  workflowKey: string;
}

function scenarioId(scenario: ScenarioDefinition) {
  return `${scenario.category}:${scenario.workflowKey}`;
}

const scenarios: ScenarioDefinition[] = [
  {
    category: "customer",
    descriptionKey: "digitalEmployeesScenarioCustomerDesc",
    icon: UserRoundCheck,
    titleKey: "digitalEmployeesScenarioCustomer",
    workflowKey: "agentWorkflowCustomerReply",
  },
  {
    category: "marketing",
    descriptionKey: "digitalEmployeesScenarioMarketingDesc",
    icon: Megaphone,
    titleKey: "digitalEmployeesScenarioMarketing",
    workflowKey: "agentWorkflowProductCopy",
  },
  {
    category: "media",
    descriptionKey: "digitalEmployeesScenarioMediaDesc",
    icon: Sparkles,
    titleKey: "digitalEmployeesScenarioMedia",
    workflowKey: "agentWorkflowImagePrompt",
  },
  {
    category: "hr",
    descriptionKey: "digitalEmployeesScenarioHrDesc",
    icon: UsersRound,
    titleKey: "digitalEmployeesScenarioHr",
    workflowKey: "agentWorkflowResumeSummary",
  },
  {
    category: "operations",
    descriptionKey: "digitalEmployeesScenarioOperationsDesc",
    icon: Store,
    titleKey: "digitalEmployeesScenarioOperations",
    workflowKey: "agentWorkflowStoreListing",
  },
  {
    category: "finance",
    descriptionKey: "digitalEmployeesScenarioFinanceDesc",
    icon: Landmark,
    titleKey: "digitalEmployeesScenarioFinance",
    workflowKey: "agentWorkflowFinanceExplain",
  },
  {
    category: "analytics",
    descriptionKey: "digitalEmployeesScenarioAnalyticsDesc",
    icon: BarChart3,
    titleKey: "digitalEmployeesScenarioAnalytics",
    workflowKey: "agentWorkflowReportDraft",
  },
];

export function EmployeeScenarioLauncherPanel({
  activeEmployees,
  canChat,
  canInspectEvidence,
  canReadKnowledge,
  onOpenEvidence,
  onOpenGuide,
  onOpenKnowledge,
  onSelectScenario,
  selectedEmployee,
  selectedWorkflowKey,
}: EmployeeScenarioLauncherPanelProps) {
  const { locale, t } = useLocale();
  const selectedCategory = selectedEmployee ? categoryForEmployee(selectedEmployee) : null;
  const selectedScenario = scenarios.find(
    (scenario) => scenario.category === selectedCategory && scenario.workflowKey === selectedWorkflowKey,
  );
  const [previewScenarioId, setPreviewScenarioId] = useState(() => scenarioId(selectedScenario ?? scenarios[0]));
  const previewScenario =
    scenarios.find((scenario) => scenarioId(scenario) === previewScenarioId) ?? selectedScenario ?? scenarios[0];
  const PreviewIcon = previewScenario.icon;
  const previewEmployees = activeEmployees.filter(
    (employee) => categoryForEmployee(employee) === previewScenario.category,
  );
  const previewEmployee = previewEmployees[0] ?? null;
  const previewDisabled = !canChat || !previewEmployee;
  const availableScenarioCount = scenarios.filter((scenario) =>
    activeEmployees.some((employee) => categoryForEmployee(employee) === scenario.category),
  ).length;
  const unavailableScenarioCount = scenarios.length - availableScenarioCount;
  const selectedScenarioTitle = selectedScenario ? t(selectedScenario.titleKey) : t("digitalEmployeesTaskManual");
  const selectedAgentName = selectedEmployee ? agentDisplayName(selectedEmployee, locale) : "-";
  const selectedKnowledgeCount = selectedEmployee?.knowledge_base_count ?? 0;
  const selectedHasKnowledge = Boolean(selectedEmployee?.knowledge_enabled && selectedKnowledgeCount > 0);
  const selectedIsMedia = selectedCategory === "media";

  return (
    <section className="employee-scenario-launcher" aria-label={t("digitalEmployeesScenarioTitle")}>
      <div className="employee-scenario-launcher-head">
        <div>
          <span>{t("digitalEmployeesScenarioEyebrow")}</span>
          <strong>{t("digitalEmployeesScenarioTitle")}</strong>
          <p>{t("digitalEmployeesScenarioDescription")}</p>
        </div>
        <div className="employee-scenario-summary">
          <StatusBadge
            label={t("digitalEmployeesScenarioAvailableCount").replace("{{count}}", String(availableScenarioCount))}
            status="ready"
          />
          <StatusBadge
            label={t("digitalEmployeesScenarioUnavailableCount").replace("{{count}}", String(unavailableScenarioCount))}
            status={unavailableScenarioCount ? "warning" : "ready"}
          />
        </div>
      </div>
      <div className="employee-scenario-workspace">
        <div className="employee-scenario-steps" role="tablist" aria-label={t("digitalEmployeesScenarioStageTabs")}>
          {scenarios.map((scenario) => {
            const Icon = scenario.icon;
            const matchedEmployees = activeEmployees.filter(
              (employee) => categoryForEmployee(employee) === scenario.category,
            );
            const matchedEmployee = matchedEmployees[0] ?? null;
            const selected = scenarioId(scenario) === scenarioId(previewScenario);
            const disabled = !canChat || !matchedEmployee;

            return (
              <button
                aria-selected={selected}
                className={cx("employee-scenario-step", disabled && "blocked", selected && "selected")}
                key={scenario.category}
                onClick={() => setPreviewScenarioId(scenarioId(scenario))}
                role="tab"
                type="button"
              >
                <span className="employee-scenario-icon">
                  <Icon size={17} />
                </span>
                <span className="employee-scenario-copy">
                  <strong>{t(scenario.titleKey)}</strong>
                  <span>
                    {matchedEmployee
                      ? t("digitalEmployeesScenarioAgent")
                          .replace("{{agent}}", agentDisplayName(matchedEmployee, locale))
                          .replace("{{count}}", String(matchedEmployees.length))
                      : t("digitalEmployeesScenarioUnavailable")}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
        <section
          className={cx("employee-scenario-detail", previewDisabled && "blocked")}
          aria-label={t("digitalEmployeesScenarioSelectedStage")}
        >
          <div className="employee-scenario-detail-head">
            <span className="employee-scenario-icon">
              <PreviewIcon size={18} />
            </span>
            <div>
              <span>{t("digitalEmployeesScenarioCurrentStage")}</span>
              <strong>{t(previewScenario.titleKey)}</strong>
            </div>
            <StatusBadge
              label={previewEmployee ? t("digitalEmployeesScenarioReady") : t("digitalEmployeesScenarioUnavailable")}
              status={previewEmployee ? "ready" : "blocked"}
            />
          </div>
          <p>{t(previewScenario.descriptionKey)}</p>
          <strong className="employee-scenario-detail-agent">
            {previewEmployee
              ? t("digitalEmployeesScenarioAgent")
                  .replace("{{agent}}", agentDisplayName(previewEmployee, locale))
                  .replace("{{count}}", String(previewEmployees.length))
              : t("digitalEmployeesScenarioUnavailable")}
          </strong>
          <button
            className="button"
            disabled={previewDisabled}
            onClick={() => onSelectScenario(previewScenario.category, previewScenario.workflowKey)}
            type="button"
          >
            <Sparkles size={15} />
            {t("digitalEmployeesScenarioStart")}
          </button>
        </section>
      </div>
      {selectedEmployee && (
        <section className="employee-scenario-context" aria-label={t("digitalEmployeesScenarioContextTitle")}>
          <div>
            <span>{t("digitalEmployeesScenarioContextTitle")}</span>
            <strong>
              {selectedScenarioTitle} · {selectedAgentName}
            </strong>
          </div>
          <button type="button" onClick={onOpenGuide}>
            <ClipboardCheck size={15} />
            <span>{t("digitalEmployeesScenarioOpenGuide")}</span>
          </button>
          <button type="button" disabled={!canReadKnowledge || !selectedHasKnowledge} onClick={onOpenKnowledge}>
            <BookOpen size={15} />
            <span>
              {selectedHasKnowledge
                ? t("digitalEmployeesScenarioKnowledgeReady").replace("{{count}}", String(selectedKnowledgeCount))
                : t("digitalEmployeesScenarioKnowledgeNone")}
            </span>
          </button>
          <button type="button" disabled={!canInspectEvidence} onClick={onOpenEvidence}>
            <ClipboardCheck size={15} />
            <span>
              {canInspectEvidence
                ? t("digitalEmployeesScenarioEvidenceReady")
                : t("digitalEmployeesScenarioEvidenceEmployee")}
            </span>
          </button>
          <span className={cx("employee-scenario-context-pill", selectedIsMedia && "ready")}>
            <Sparkles size={15} />
            {selectedIsMedia ? t("digitalEmployeesScenarioMediaGoverned") : t("digitalEmployeesScenarioStandardFlow")}
          </span>
        </section>
      )}
    </section>
  );
}
