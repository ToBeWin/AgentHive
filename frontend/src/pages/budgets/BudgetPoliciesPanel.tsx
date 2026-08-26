import { PauseCircle, PlayCircle, Plus, Wallet } from "lucide-react";
import { useMemo, useState } from "react";
import { ApiNotice, Button, EmptyState, LoadingState, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { BudgetPolicyResponse, BudgetPolicyStatus } from "../../lib/api";
import { budgetUsagePct, formatCurrency } from "../../lib/formatters";
import { formatBudgetStatus, formatScope } from "./budgetUtils";

export function BudgetPoliciesPanel({
  canWrite,
  error,
  loading,
  onCreate,
  onUpdatePolicyStatus,
  onRetry,
  policies,
  statusUpdatingPolicyId,
}: {
  canWrite: boolean;
  error: string | null;
  loading: boolean;
  onCreate?: () => void;
  onUpdatePolicyStatus: (policyId: string, status: BudgetPolicyStatus) => void;
  onRetry: () => void;
  policies: BudgetPolicyResponse[];
  statusUpdatingPolicyId: string | null;
}) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<"policies" | "agent" | "ledger">("policies");
  const visiblePolicies = useMemo(() => {
    if (activeTab === "agent") {
      return policies.filter((policy) => policy.scope_type === "agent");
    }
    if (activeTab === "ledger") {
      return [];
    }
    return policies;
  }, [activeTab, policies]);
  const emptyMessage =
    activeTab === "agent"
      ? t("budgetsNoAgentPolicies")
      : activeTab === "ledger"
        ? t("budgetsModelLedgerTabMessage")
        : t("budgetsNoPolicies");

  return (
    <section className="panel table-panel">
      <div className="tabs">
        <button
          type="button"
          className={activeTab === "policies" ? "active" : undefined}
          onClick={() => setActiveTab("policies")}
        >
          {t("budgetsPolicies")}
        </button>
        <button
          type="button"
          className={activeTab === "agent" ? "active" : undefined}
          onClick={() => setActiveTab("agent")}
        >
          {t("budgetsAgentScope")}
        </button>
        <button
          type="button"
          className={activeTab === "ledger" ? "active" : undefined}
          onClick={() => setActiveTab("ledger")}
        >
          {t("budgetsModelUsageLedger")}
        </button>
      </div>
      {activeTab === "ledger" && (
        <ApiNotice title={t("budgetsModelUsageLedger")} message={t("budgetsModelLedgerTabHint")} />
      )}
      {error && (
        <ApiNotice
          title={t("budgetsPoliciesUnavailable")}
          message={error}
          action={<Button onClick={onRetry}>{t("commonRetry")}</Button>}
        />
      )}
      <table className="data-table">
        <thead>
          <tr>
            <th>{t("budgetsScope")}</th>
            <th>{t("budgetsBudgetLimit")}</th>
            <th>{t("budgetsSpent")}</th>
            <th>{t("budgetsUsagePercent")}</th>
            <th>{t("budgetsAlertStatus")}</th>
            <th>{t("budgetsActions")}</th>
          </tr>
        </thead>
        <tbody>
          {loading && (
            <tr>
              <td colSpan={6}>
                <LoadingState lines={3} />
              </td>
            </tr>
          )}
          {!loading && !visiblePolicies.length && (
            <tr>
              <td className="table-empty-cell" colSpan={6}>
                <EmptyState
                  icon={<Wallet />}
                  title={t("emptyTitleBudgetPolicies")}
                  message={emptyMessage}
                  action={
                    canWrite && activeTab !== "ledger" && onCreate ? (
                      <Button variant="primary" onClick={onCreate}>
                        <Plus size={16} /> {t("createBudget")}
                      </Button>
                    ) : undefined
                  }
                />
              </td>
            </tr>
          )}
          {visiblePolicies.map((row) => {
            const pct = budgetUsagePct(row.amount_spent, row.amount_limit);
            const nextStatus: BudgetPolicyStatus = row.status === "active" ? "inactive" : "active";
            const updating = statusUpdatingPolicyId === row.id;
            return (
              <tr key={row.id}>
                <td>
                  <strong>{row.name ?? formatScope(row.scope_type, t)}</strong>
                  <span className="row-subtitle">
                    {formatScope(row.scope_type, t)} · {t(`budgetsPeriod${capitalize(row.period)}`)} ·{" "}
                    {t(`budgetsLimit${capitalize(row.budget_type)}`)}
                  </span>
                </td>
                <td>{formatCurrency(row.amount_limit, row.currency)}</td>
                <td>{formatCurrency(row.amount_spent, row.currency)}</td>
                <td>{pct}%</td>
                <td>
                  <StatusBadge status={formatBudgetStatus(row)} />
                </td>
                <td>
                  <Button
                    variant="ghost"
                    disabled={!canWrite || updating}
                    onClick={() => onUpdatePolicyStatus(row.id, nextStatus)}
                  >
                    {nextStatus === "active" ? <PlayCircle size={16} /> : <PauseCircle size={16} />}
                    {updating
                      ? t("budgetsUpdatingPolicy")
                      : nextStatus === "active"
                        ? t("budgetsActivatePolicy")
                        : t("budgetsDeactivatePolicy")}
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

function capitalize(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
