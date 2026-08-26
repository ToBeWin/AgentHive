import { Plus } from "lucide-react";
import { ApiNotice, Button, PageHeader, PageTabs } from "../components/app-ui";
import type { WorkspaceId } from "../data";
import { useLocale } from "../i18n-context";
import type { AuthUser } from "../lib/api";
import { showDeliveryDiagnostics } from "../lib/deliveryDiagnostics";
import { BudgetControlLoopPanel } from "./budgets/BudgetControlLoopPanel";
import { BudgetLedgerWorkspace, BudgetOverviewWorkspace, BudgetPoliciesWorkspace } from "./budgets/BudgetWorkspaces";
import { useBudgetsPageController } from "./budgets/useBudgetsPageController";

export function BudgetsPage({
  activeWorkspace = "admin",
  isPrototype = false,
  user,
}: {
  activeWorkspace?: WorkspaceId;
  isPrototype?: boolean;
  user: AuthUser | null;
}) {
  const { t } = useLocale();
  const showDiagnostics = showDeliveryDiagnostics(activeWorkspace);
  const budgets = useBudgetsPageController({ isPrototype, user });
  const openAttribution = () => {
    budgets.setActiveTab("overview");
    window.requestAnimationFrame(() => {
      document.getElementById("budget-attribution-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };
  const openPolicies = () => {
    budgets.setActiveTab("policies");
    budgets.setPolicyTab("list");
  };
  const openBudgetLedger = () => {
    budgets.setActiveTab("ledger");
    budgets.setLedgerTab("budget");
  };
  const openUsageLedger = () => {
    budgets.setActiveTab("ledger");
    budgets.setLedgerTab("usage");
  };

  return (
    <section className="page budgets-page">
      <PageHeader
        title={t("budgetsTitle")}
        subtitle={t("budgetsSubtitle")}
        actions={
          <Button
            variant="primary"
            onClick={budgets.handlePrimaryBudgetAction}
            disabled={!budgets.canWriteBudgets || (budgets.activeTab === "policies" && !budgets.canSaveBudget)}
          >
            <Plus size={16} /> {t("createBudget")}
          </Button>
        }
      />
      {budgets.exportError && <ApiNotice title={t("budgetsExportFailedTitle")} message={budgets.exportError} />}
      {showDiagnostics ? (
        <BudgetControlLoopPanel
          activeTab={budgets.activeTab}
          breakdown={budgets.breakdown}
          breakdownDimension={budgets.breakdownDimension}
          budgetLedger={budgets.budgetLedger}
          canExport={budgets.canExportBudgets}
          ledger={budgets.ledger}
          ledgerTab={budgets.ledgerTab}
          onOpenAttribution={openAttribution}
          onOpenBudgetLedger={openBudgetLedger}
          onOpenPolicies={openPolicies}
          onOpenUsageLedger={openUsageLedger}
          onOpenUsageLedgerExport={openUsageLedger}
          overviewTab={budgets.overviewTab}
          policies={budgets.policies ?? []}
          policyTab={budgets.policyTab}
          summary={budgets.summary}
        />
      ) : null}
      <PageTabs
        active={budgets.activeTab}
        onChange={budgets.setActiveTab}
        tabs={[
          { id: "overview", label: t("budgetsTabOverview"), description: t("budgetsTabOverviewDesc") },
          { id: "policies", label: t("budgetsTabPolicies"), description: t("budgetsTabPoliciesDesc") },
          { id: "ledger", label: t("budgetsTabLedger"), description: t("budgetsTabLedgerDesc") },
        ]}
      />
      {budgets.activeTab === "overview" && (
        <BudgetOverviewWorkspace
          breakdown={budgets.breakdown}
          breakdownDimension={budgets.breakdownDimension}
          breakdownError={budgets.breakdownError}
          breakdownLoading={budgets.breakdownLoading}
          onBreakdownDimensionChange={budgets.setBreakdownDimension}
          onCreatePolicy={budgets.handleCreatePolicyFromOverview}
          onRetryBreakdown={budgets.refetchBreakdown}
          onRetrySummary={budgets.refetchSummary}
          onSummaryPeriodChange={budgets.setSummaryPeriod}
          periodLabel={budgets.periodLabel}
          summary={budgets.summary}
          summaryError={budgets.summaryError}
          summaryLoading={budgets.summaryLoading}
          summaryPeriod={budgets.summaryPeriod}
          totalLimit={budgets.totalLimit}
          totalSpent={budgets.totalSpent}
        />
      )}
      {budgets.activeTab === "policies" && (
        <BudgetPoliciesWorkspace
          budgetForm={budgets.budgetForm}
          canSaveBudget={budgets.canSaveBudget}
          canWrite={budgets.canWriteBudgets}
          onCreate={() => budgets.setPolicyTab("create")}
          onPolicyTabChange={budgets.setPolicyTab}
          onRetryPolicies={budgets.refetchPolicies}
          onSave={budgets.handleSaveBudget}
          onUpdatePolicyStatus={budgets.handleUpdatePolicyStatus}
          policies={budgets.policies ?? []}
          policiesError={budgets.policiesError}
          policiesLoading={budgets.policiesLoading}
          policyTab={budgets.policyTab}
          saveError={budgets.saveError}
          saveMessage={budgets.saveMessage}
          saving={budgets.saving}
          scopeOptions={budgets.scopeOptions}
          scopeOptionsLoading={budgets.scopeOptionsLoading}
          setBudgetForm={budgets.setBudgetForm}
          statusUpdatingPolicyId={budgets.statusUpdatingPolicyId}
        />
      )}
      {budgets.activeTab === "ledger" && (
        <BudgetLedgerWorkspace
          budgetLedgerError={budgets.budgetLedgerError}
          budgetLedgerItems={budgets.budgetLedger?.items ?? []}
          budgetLedgerLoading={budgets.budgetLedgerLoading}
          canExport={budgets.canExportBudgets}
          exportingLedger={budgets.exportingLedger}
          ledgerError={budgets.ledgerError}
          ledgerItems={budgets.ledger?.items ?? []}
          ledgerLoading={budgets.ledgerLoading}
          ledgerTab={budgets.ledgerTab}
          onExportBudgetCsv={budgets.handleExportBudgetLedgerCsv}
          onExportBudgetJson={budgets.handleExportBudgetLedgerJson}
          onExportUsageCsv={budgets.handleExportUsageLedgerCsv}
          onExportUsageJson={budgets.handleExportUsageLedgerJson}
          onLedgerTabChange={budgets.setLedgerTab}
          onRetryBudgetLedger={budgets.refetchBudgetLedger}
          onRetryUsageLedger={budgets.refetchLedger}
        />
      )}
    </section>
  );
}
