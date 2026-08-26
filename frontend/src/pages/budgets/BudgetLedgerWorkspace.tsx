import { PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { BudgetLedgerItem, UsageLedgerItem } from "../../lib/api";
import { BudgetLedgerPanel, UsageLedgerPanel } from "./BudgetPanels";
import type { BudgetLedgerTab } from "./budgetWorkspaceTypes";

interface BudgetLedgerWorkspaceProps {
  budgetLedgerError: string | null;
  budgetLedgerItems: BudgetLedgerItem[];
  budgetLedgerLoading: boolean;
  canExport: boolean;
  exportingLedger: string | null;
  ledgerError: string | null;
  ledgerItems: UsageLedgerItem[];
  ledgerLoading: boolean;
  ledgerTab: BudgetLedgerTab;
  onExportBudgetCsv: () => void;
  onExportBudgetJson: () => void;
  onExportUsageCsv: () => void;
  onExportUsageJson: () => void;
  onLedgerTabChange: (tab: BudgetLedgerTab) => void;
  onRetryBudgetLedger: () => void;
  onRetryUsageLedger: () => void;
}

export function BudgetLedgerWorkspace({
  budgetLedgerError,
  budgetLedgerItems,
  budgetLedgerLoading,
  canExport,
  exportingLedger,
  ledgerError,
  ledgerItems,
  ledgerLoading,
  ledgerTab,
  onExportBudgetCsv,
  onExportBudgetJson,
  onExportUsageCsv,
  onExportUsageJson,
  onLedgerTabChange,
  onRetryBudgetLedger,
  onRetryUsageLedger,
}: BudgetLedgerWorkspaceProps) {
  const { t } = useLocale();

  return (
    <div className="nested-workspace">
      <PageTabs
        active={ledgerTab}
        onChange={onLedgerTabChange}
        tabs={[
          {
            id: "budget",
            label: t("budgetsLedgerTabBudget"),
            description: t("budgetsLedgerTabBudgetDesc"),
          },
          {
            id: "usage",
            label: t("budgetsLedgerTabUsage"),
            description: t("budgetsLedgerTabUsageDesc"),
          },
        ]}
      />
      {ledgerTab === "budget" && (
        <BudgetLedgerPanel
          canExport={canExport}
          error={budgetLedgerError}
          exporting={exportingLedger?.startsWith("budget") ?? false}
          items={budgetLedgerItems}
          loading={budgetLedgerLoading}
          onExportCsv={onExportBudgetCsv}
          onExportJson={onExportBudgetJson}
          onRetry={onRetryBudgetLedger}
        />
      )}
      {ledgerTab === "usage" && (
        <UsageLedgerPanel
          canExport={canExport}
          error={ledgerError}
          exporting={exportingLedger?.startsWith("usage") ?? false}
          items={ledgerItems}
          loading={ledgerLoading}
          onExportCsv={onExportUsageCsv}
          onExportJson={onExportUsageJson}
          onRetry={onRetryUsageLedger}
        />
      )}
    </div>
  );
}
