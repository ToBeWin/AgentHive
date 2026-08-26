import { useState } from "react";
import {
  prototypeBudgetLedgerExport,
  useBudgetGovernanceTargets,
  useBudgetLedger,
  useBudgetPolicies,
  useBudgetPolicyActions,
  useBudgetSummary,
  useBudgetUsageBreakdown,
  useBudgetUsageLedger,
} from "../../hooks/useAdminData";
import { useLocale } from "../../i18n-context";
import {
  type AuthUser,
  adminApi,
  type BudgetGovernanceTargetsResponse,
  type BudgetPeriod,
  type BudgetPolicyStatus,
  type UsageBreakdownDimension,
} from "../../lib/api";
import { downloadTextFile } from "../../lib/download";
import { canAccess } from "../../lib/permissions";
import type { BudgetLedgerTab, BudgetOverviewTab, BudgetPolicyTab, BudgetsPageTab } from "./BudgetWorkspaces";
import {
  type BudgetFormState,
  budgetFormHasValidAlertThreshold,
  budgetFormHasValidLimit,
  budgetScopeOptions,
} from "./budgetUtils";

const BUDGETS_EXPORT_PERMISSION = "budgets:export";
const BUDGETS_WRITE_PERMISSION = "budgets:write";
const EMPTY_BUDGET_GOVERNANCE_TARGETS: BudgetGovernanceTargetsResponse = {
  agents: [],
  channels: [],
  cost_centers: [],
  departments: [],
  users: [],
};

export function useBudgetsPageController({
  isPrototype = false,
  user,
}: {
  isPrototype?: boolean;
  user: AuthUser | null;
}) {
  const { t } = useLocale();
  const canWriteBudgets = isPrototype || canAccess(user, [BUDGETS_WRITE_PERMISSION]);
  const [activeTab, setActiveTab] = useState<BudgetsPageTab>("overview");
  const [overviewTab, setOverviewTab] = useState<BudgetOverviewTab>("health");
  const [policyTab, setPolicyTab] = useState<BudgetPolicyTab>("list");
  const [ledgerTab, setLedgerTab] = useState<BudgetLedgerTab>("budget");
  const [summaryPeriod, setSummaryPeriod] = useState<BudgetPeriod>("monthly");
  const [breakdownDimension, setBreakdownDimension] = useState<UsageBreakdownDimension>("department");
  const [exportingLedger, setExportingLedger] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const {
    data: summary,
    error: summaryError,
    loading: summaryLoading,
    refetch: refetchSummary,
  } = useBudgetSummary(summaryPeriod, { fallbackOnError: isPrototype });
  const {
    data: policies,
    error: policiesError,
    loading: policiesLoading,
    refetch: refetchPolicies,
  } = useBudgetPolicies({ fallbackOnError: isPrototype });
  const {
    data: budgetLedger,
    error: budgetLedgerError,
    loading: budgetLedgerLoading,
    refetch: refetchBudgetLedger,
  } = useBudgetLedger({ fallbackOnError: isPrototype });
  const {
    data: ledger,
    error: ledgerError,
    loading: ledgerLoading,
    refetch: refetchLedger,
  } = useBudgetUsageLedger({
    fallbackOnError: isPrototype,
  });
  const {
    data: breakdown,
    error: breakdownError,
    loading: breakdownLoading,
    refetch: refetchBreakdown,
  } = useBudgetUsageBreakdown(breakdownDimension, { fallbackOnError: isPrototype });
  const {
    error: saveError,
    message: saveMessage,
    savePolicy,
    saving,
    statusUpdatingPolicyId,
    updatePolicyStatus,
  } = useBudgetPolicyActions({ fallbackOnError: isPrototype });
  const { data: budgetTargets, loading: budgetTargetsLoading } = useBudgetGovernanceTargets({
    fallbackOnError: isPrototype,
  });
  const [budgetForm, setBudgetForm] = useState<BudgetFormState>({
    alertThreshold: "80",
    amountLimit: "1000",
    budgetType: "hard",
    name: t("budgetsDefaultPolicyName"),
    period: "monthly",
    scopeId: "",
    scopeType: "tenant",
    tokenLimit: "",
  });

  const totalLimit = summary?.total_amount_limit ?? "0";
  const totalSpent = summary?.total_amount_spent ?? "0";
  const scopeOptions = budgetScopeOptions({
    scopeType: budgetForm.scopeType,
    targets: budgetTargets ?? EMPTY_BUDGET_GOVERNANCE_TARGETS,
  });
  const scopeOptionsLoading = budgetForm.scopeType !== "tenant" && budgetTargetsLoading;
  const canSaveBudget =
    canWriteBudgets &&
    !saving &&
    (budgetForm.scopeType === "tenant" || Boolean(budgetForm.scopeId)) &&
    budgetFormHasValidLimit(budgetForm) &&
    budgetFormHasValidAlertThreshold(budgetForm);
  const canExportBudgets = isPrototype || canAccess(user, [BUDGETS_EXPORT_PERMISSION]);
  const periodLabel =
    summary?.period === "daily"
      ? t("budgetsPeriodLabelDay")
      : summary?.period === "custom"
        ? t("budgetsPeriodLabelCustom")
        : t("budgetsPeriodLabelMonth");

  const refreshBudgetData = async () => {
    await Promise.all([
      refetchSummary(),
      refetchPolicies(),
      refetchBudgetLedger(),
      refetchLedger(),
      refetchBreakdown(),
    ]);
  };

  const handleSaveBudget = async () => {
    if (!canWriteBudgets) {
      return;
    }
    const saved = await savePolicy({
      alert_threshold_pct: Number(budgetForm.alertThreshold),
      amount_limit: budgetForm.amountLimit,
      budget_type: budgetForm.budgetType,
      currency: "USD",
      name: budgetForm.name,
      period: budgetForm.period,
      scope_id: budgetForm.scopeType === "tenant" ? null : budgetForm.scopeId || null,
      scope_type: budgetForm.scopeType,
      status: "active",
      token_limit: budgetForm.tokenLimit ? Number(budgetForm.tokenLimit) : null,
    });
    if (saved) {
      await refreshBudgetData();
      setPolicyTab("list");
    }
  };

  const handlePrimaryBudgetAction = () => {
    if (activeTab !== "policies") {
      setActiveTab("policies");
      setPolicyTab("create");
      return;
    }
    if (policyTab !== "create") {
      setPolicyTab("create");
      return;
    }
    void handleSaveBudget();
  };

  const handleCreatePolicyFromOverview = () => {
    setActiveTab("policies");
    setPolicyTab("create");
  };

  const handleUpdatePolicyStatus = async (policyId: string, status: BudgetPolicyStatus) => {
    if (!canWriteBudgets) {
      return;
    }
    const updated = await updatePolicyStatus(policyId, status);
    if (updated) {
      await refreshBudgetData();
    }
  };

  const handleExportBudgetLedgerCsv = async () => {
    await exportBudgetFile({
      extension: "csv",
      exporter: isPrototype
        ? () => Promise.resolve(prototypeBudgetLedgerExport("csv", "budget"))
        : adminApi.exportBudgetLedgerCsv,
      filenamePrefix: "agenthive-budget-ledger",
      key: "budget-csv",
      mimeType: "text/csv;charset=utf-8",
      setExportError,
      setExportingLedger,
      t,
    });
  };

  const handleExportBudgetLedgerJson = async () => {
    await exportBudgetFile({
      extension: "json",
      exporter: isPrototype
        ? () => Promise.resolve(prototypeBudgetLedgerExport("json", "budget"))
        : adminApi.exportBudgetLedgerJson,
      filenamePrefix: "agenthive-budget-ledger",
      key: "budget-json",
      mimeType: "application/json;charset=utf-8",
      setExportError,
      setExportingLedger,
      t,
    });
  };

  const handleExportUsageLedgerCsv = async () => {
    await exportBudgetFile({
      extension: "csv",
      exporter: isPrototype
        ? () => Promise.resolve(prototypeBudgetLedgerExport("csv", "usage"))
        : adminApi.exportUsageLedgerCsv,
      filenamePrefix: "agenthive-usage-ledger",
      key: "usage-csv",
      mimeType: "text/csv;charset=utf-8",
      setExportError,
      setExportingLedger,
      t,
    });
  };

  const handleExportUsageLedgerJson = async () => {
    await exportBudgetFile({
      extension: "json",
      exporter: isPrototype
        ? () => Promise.resolve(prototypeBudgetLedgerExport("json", "usage"))
        : adminApi.exportUsageLedgerJson,
      filenamePrefix: "agenthive-usage-ledger",
      key: "usage-json",
      mimeType: "application/json;charset=utf-8",
      setExportError,
      setExportingLedger,
      t,
    });
  };

  return {
    activeTab,
    breakdown,
    breakdownDimension,
    breakdownError,
    breakdownLoading,
    budgetForm,
    budgetLedger,
    budgetLedgerError,
    budgetLedgerLoading,
    canExportBudgets,
    canSaveBudget,
    canWriteBudgets,
    exportingLedger,
    exportError,
    handleCreatePolicyFromOverview,
    handleExportBudgetLedgerCsv,
    handleExportBudgetLedgerJson,
    handleExportUsageLedgerCsv,
    handleExportUsageLedgerJson,
    handlePrimaryBudgetAction,
    handleSaveBudget,
    handleUpdatePolicyStatus,
    ledger,
    ledgerError,
    ledgerLoading,
    ledgerTab,
    overviewTab,
    periodLabel,
    policies,
    policiesError,
    policiesLoading,
    policyTab,
    refetchBreakdown,
    refetchBudgetLedger,
    refetchLedger,
    refetchPolicies,
    refetchSummary,
    saveError,
    saveMessage,
    saving,
    scopeOptions,
    scopeOptionsLoading,
    setActiveTab,
    setBreakdownDimension,
    setBudgetForm,
    setLedgerTab,
    setOverviewTab,
    setPolicyTab,
    setSummaryPeriod,
    statusUpdatingPolicyId,
    summary,
    summaryError,
    summaryLoading,
    summaryPeriod,
    totalLimit,
    totalSpent,
  };
}

async function exportBudgetFile({
  extension,
  exporter,
  filenamePrefix,
  key,
  mimeType,
  setExportError,
  setExportingLedger,
  t,
}: {
  extension: "csv" | "json";
  exporter: () => Promise<string>;
  filenamePrefix: string;
  key: string;
  mimeType: string;
  setExportError: (value: string | null) => void;
  setExportingLedger: (value: string | null) => void;
  t: (key: string) => string;
}) {
  setExportingLedger(key);
  setExportError(null);
  try {
    const content = await exporter();
    downloadTextFile(content, `${filenamePrefix}-${new Date().toISOString().slice(0, 10)}.${extension}`, mimeType);
  } catch (error) {
    setExportError(error instanceof Error ? error.message : t("budgetsExportFailedMessage"));
  } finally {
    setExportingLedger(null);
  }
}
