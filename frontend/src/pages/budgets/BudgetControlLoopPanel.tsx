import { CircleDollarSign, FileDown, GitBranch, type LucideIcon, ReceiptText, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  BudgetLedgerItem,
  BudgetLedgerResponse,
  BudgetPolicyResponse,
  BudgetSummaryResponse,
  UsageBreakdownDimension,
  UsageBreakdownResponse,
  UsageLedgerResponse,
} from "../../lib/api";
import type { BudgetLedgerTab, BudgetOverviewTab, BudgetPolicyTab, BudgetsPageTab } from "./budgetWorkspaceTypes";

type BudgetLoopStageId = "attribution" | "policies" | "guard" | "settlement" | "export";

interface BudgetControlLoopPanelProps {
  activeTab: BudgetsPageTab;
  breakdown: UsageBreakdownResponse | null;
  breakdownDimension: UsageBreakdownDimension;
  budgetLedger: BudgetLedgerResponse | null;
  canExport: boolean;
  ledger: UsageLedgerResponse | null;
  ledgerTab: BudgetLedgerTab;
  onOpenAttribution: () => void;
  onOpenBudgetLedger: () => void;
  onOpenPolicies: () => void;
  onOpenUsageLedger: () => void;
  onOpenUsageLedgerExport: () => void;
  overviewTab: BudgetOverviewTab;
  policies: BudgetPolicyResponse[];
  policyTab: BudgetPolicyTab;
  summary: BudgetSummaryResponse | null;
}

export function BudgetControlLoopPanel({
  activeTab,
  breakdown,
  breakdownDimension,
  budgetLedger,
  canExport,
  ledger,
  ledgerTab,
  onOpenAttribution,
  onOpenBudgetLedger,
  onOpenPolicies,
  onOpenUsageLedger,
  onOpenUsageLedgerExport,
  overviewTab,
  policies,
  policyTab,
  summary,
}: BudgetControlLoopPanelProps) {
  const { t } = useLocale();
  const activePolicies = policies.filter((policy) => policy.status === "active");
  const hardPolicies = policies.filter((policy) => policy.budget_type === "hard");
  const budgetEvents = budgetLedger?.items ?? [];
  const usageItems = ledger?.items ?? [];
  const preCallEvents = countBudgetEvents(budgetEvents, ["reserve", "deny"]);
  const settlementEvents = usageItems.length;
  const attributionRows = breakdown?.items.length ?? summary?.by_scope.length ?? 0;
  const totalCost = ledger?.items.reduce((sum, item) => sum + Number(item.cost_amount || 0), 0) ?? 0;
  const hasExportableEvidence = canExport && (budgetEvents.length > 0 || usageItems.length > 0);
  const stages: Array<{
    action: () => void;
    detail: string;
    icon: LucideIcon;
    id: BudgetLoopStageId;
    metric: string;
    status: string;
    title: string;
    tone: "ok" | "warning" | "blocked";
  }> = [
    {
      action: onOpenAttribution,
      detail: t("budgetsLoopAttributionDetail").replace(
        "{{dimension}}",
        t(budgetDimensionLabelKey(breakdownDimension)),
      ),
      icon: GitBranch,
      id: "attribution",
      metric: t("budgetsLoopAttributionMetric").replace("{{count}}", String(attributionRows)),
      status: attributionRows > 0 ? t("budgetsLoopReady") : t("budgetsLoopNeedsUsage"),
      title: t("budgetsLoopAttribution"),
      tone: attributionRows > 0 ? "ok" : "warning",
    },
    {
      action: onOpenPolicies,
      detail: t("budgetsLoopPoliciesDetail").replace("{{hard}}", String(hardPolicies.length)),
      icon: ShieldCheck,
      id: "policies",
      metric: t("budgetsLoopPoliciesMetric")
        .replace("{{active}}", String(activePolicies.length))
        .replace("{{total}}", String(policies.length)),
      status: activePolicies.length ? t("budgetsLoopReady") : t("budgetsLoopNeedsPolicy"),
      title: t("budgetsLoopPolicies"),
      tone: activePolicies.length ? "ok" : policies.length ? "warning" : "blocked",
    },
    {
      action: onOpenBudgetLedger,
      detail: t("budgetsLoopGuardDetail")
        .replace("{{reserve}}", String(countBudgetEvents(budgetEvents, ["reserve"])))
        .replace("{{deny}}", String(countBudgetEvents(budgetEvents, ["deny"]))),
      icon: CircleDollarSign,
      id: "guard",
      metric: t("budgetsLoopGuardMetric").replace("{{count}}", String(preCallEvents)),
      status: preCallEvents ? t("budgetsLoopReady") : t("budgetsLoopNeedsGuardEvidence"),
      title: t("budgetsLoopGuard"),
      tone: preCallEvents ? "ok" : activePolicies.length ? "warning" : "blocked",
    },
    {
      action: onOpenUsageLedger,
      detail: t("budgetsLoopSettlementDetail").replace("{{cost}}", `$${totalCost.toFixed(4)}`),
      icon: ReceiptText,
      id: "settlement",
      metric: t("budgetsLoopSettlementMetric").replace("{{count}}", String(settlementEvents)),
      status: settlementEvents ? t("budgetsLoopReady") : t("budgetsLoopNeedsSettlement"),
      title: t("budgetsLoopSettlement"),
      tone: settlementEvents ? "ok" : activePolicies.length ? "warning" : "blocked",
    },
    {
      action: onOpenUsageLedgerExport,
      detail: canExport ? t("budgetsLoopExportDetail") : t("budgetsLoopExportPermissionDetail"),
      icon: FileDown,
      id: "export",
      metric: hasExportableEvidence ? t("budgetsLoopExportReady") : t("budgetsLoopExportPending"),
      status: hasExportableEvidence
        ? t("budgetsLoopReady")
        : canExport
          ? t("budgetsLoopNeedsLedger")
          : t("budgetsLoopNeedsExportPermission"),
      title: t("budgetsLoopExport"),
      tone: hasExportableEvidence ? "ok" : canExport ? "warning" : "blocked",
    },
  ];
  const preferredStageId =
    stages.find((stage) => stage.tone === "blocked")?.id ??
    stages.find((stage) => stage.tone === "warning")?.id ??
    activeStageId(activeTab, overviewTab, ledgerTab, policyTab);
  const [selectedStageId, setSelectedStageId] = useState<BudgetLoopStageId>(() => preferredStageId);
  const selectedStage = stages.find((stage) => stage.id === selectedStageId) ?? stages[0];
  const SelectedIcon = selectedStage.icon;
  const readyCount = stages.filter((stage) => stage.tone === "ok").length;
  const reviewCount = stages.filter((stage) => stage.tone === "warning").length;
  const blockedCount = stages.filter((stage) => stage.tone === "blocked").length;

  return (
    <details className="budget-control-loop" aria-label={t("budgetsLoopTitle")}>
      <summary className="budget-control-loop-summary">
        <div>
          <span>{t("budgetsLoopEyebrow")}</span>
          <strong>{t("budgetsLoopTitle")}</strong>
          <small>{t("budgetsLoopCollapseHint")}</small>
        </div>
        <div className="budget-control-loop-summary-status">
          <StatusBadge label={t("budgetsLoopReadyCount").replace("{{count}}", String(readyCount))} status="ok" />
          {reviewCount > 0 && (
            <StatusBadge
              label={t("budgetsLoopReviewCount").replace("{{count}}", String(reviewCount))}
              status="warning"
            />
          )}
          {blockedCount > 0 && (
            <StatusBadge
              label={t("budgetsLoopBlockedCount").replace("{{count}}", String(blockedCount))}
              status="blocked"
            />
          )}
        </div>
      </summary>
      <p className="budget-control-loop-description">{t("budgetsLoopDescription")}</p>
      <div className="budget-control-loop-workspace">
        <div className="budget-control-loop-steps" role="tablist" aria-label={t("budgetsLoopStageTabs")}>
          {stages.map((stage) => {
            const Icon = stage.icon;
            return (
              <button
                aria-selected={stage.id === selectedStage.id}
                className={cx(
                  "budget-control-loop-step",
                  stage.tone,
                  stage.id === activeStageId(activeTab, overviewTab, ledgerTab, policyTab) && "active-workspace",
                  stage.id === selectedStage.id && "selected",
                )}
                key={stage.id}
                onClick={() => setSelectedStageId(stage.id)}
                role="tab"
                type="button"
              >
                <span className="budget-control-loop-index">
                  <Icon size={16} />
                </span>
                <span>
                  <strong>{stage.title}</strong>
                  <small>{stage.status}</small>
                </span>
              </button>
            );
          })}
        </div>
        <div className={cx("budget-control-loop-detail", selectedStage.tone)} role="tabpanel">
          <div className="budget-control-loop-detail-head">
            <span className="budget-control-loop-icon">
              <SelectedIcon size={18} />
            </span>
            <div>
              <span>{t("budgetsLoopSelectedStage")}</span>
              <strong>{selectedStage.title}</strong>
              <small>{selectedStage.detail}</small>
            </div>
            <StatusBadge label={selectedStage.status} status={selectedStage.tone} />
          </div>
          <div className="budget-control-loop-detail-metric">
            <span>{t("budgetsLoopCurrentMetric")}</span>
            <strong>{selectedStage.metric}</strong>
          </div>
          <button className="button" onClick={selectedStage.action} type="button">
            {t("budgetsLoopOpenStep")}
          </button>
        </div>
      </div>
    </details>
  );
}

function activeStageId(
  activeTab: BudgetsPageTab,
  overviewTab: BudgetOverviewTab,
  ledgerTab: BudgetLedgerTab,
  policyTab: BudgetPolicyTab,
): BudgetLoopStageId {
  if (activeTab === "policies") {
    return policyTab === "create" ? "policies" : "policies";
  }
  if (activeTab === "ledger") {
    return ledgerTab === "budget" ? "guard" : "settlement";
  }
  return overviewTab === "attribution" ? "attribution" : "attribution";
}

function countBudgetEvents(items: BudgetLedgerItem[], eventTypes: BudgetLedgerItem["event_type"][]) {
  const allowed = new Set(eventTypes);
  return items.filter((item) => allowed.has(item.event_type)).length;
}

function budgetDimensionLabelKey(dimension: UsageBreakdownDimension) {
  const labelKeys: Record<UsageBreakdownDimension, string> = {
    agent: "budgetsBreakdownAgent",
    channel: "budgetsBreakdownChannel",
    cost_center: "budgetsBreakdownCostCenter",
    department: "budgetsBreakdownDepartment",
    model: "budgetsBreakdownModel",
    status: "budgetsBreakdownStatus",
    user: "budgetsBreakdownUser",
  };
  return labelKeys[dimension];
}
