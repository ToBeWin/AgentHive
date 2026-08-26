import type React from "react";
import { useState } from "react";
import { ApiNotice, Button, cx, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { BudgetScopeType } from "../../lib/api";
import type { BudgetFormState } from "./budgetUtils";
import { formatScope } from "./budgetUtils";

type BudgetGuardrailTab = "scope" | "limits";

export function BudgetGuardrailPanel({
  budgetForm,
  canSaveBudget,
  canWrite,
  onSave,
  saveError,
  saveMessage,
  saving,
  scopeOptions,
  scopeOptionsLoading,
  setBudgetForm,
}: {
  budgetForm: BudgetFormState;
  canSaveBudget: boolean;
  canWrite: boolean;
  onSave: () => void;
  saveError: string | null;
  saveMessage: string | null;
  saving: boolean;
  scopeOptions: Array<{ id: string; label: string }>;
  scopeOptionsLoading: boolean;
  setBudgetForm: React.Dispatch<React.SetStateAction<BudgetFormState>>;
}) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<BudgetGuardrailTab>("scope");
  return (
    <section className="panel budget-form-panel">
      <h2>{t("budgetsGuardrail")}</h2>
      {!canWrite && (
        <ApiNotice title={t("budgetsWritePermissionRequired")} message={t("budgetsWritePermissionRequiredDetail")} />
      )}
      <label>
        {t("budgetsPolicyName")}
        <input
          disabled={!canWrite}
          value={budgetForm.name}
          onChange={(event) => setBudgetForm((current) => ({ ...current, name: event.target.value }))}
        />
      </label>
      <PageTabs
        active={activeTab}
        onChange={setActiveTab}
        tabs={[
          { id: "scope", label: t("budgetsGuardrailTabScope"), description: t("budgetsGuardrailTabScopeDesc") },
          { id: "limits", label: t("budgetsGuardrailTabLimits"), description: t("budgetsGuardrailTabLimitsDesc") },
        ]}
      />
      <BudgetGuardrailPreview budgetForm={budgetForm} scopeOptions={scopeOptions} />
      {activeTab === "scope" && (
        <>
          <div className="budget-form-grid">
            <label>
              {t("budgetsScope")}
              <select
                disabled={!canWrite}
                value={budgetForm.scopeType}
                onChange={(event) =>
                  setBudgetForm((current) => ({
                    ...current,
                    scopeId: "",
                    scopeType: event.target.value as BudgetScopeType,
                  }))
                }
              >
                {["tenant", "department", "cost_center", "user", "agent", "channel"].map((scope) => (
                  <option key={scope} value={scope}>
                    {formatScope(scope as BudgetScopeType, t)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {t("budgetsPeriod")}
              <select
                disabled={!canWrite}
                value={budgetForm.period}
                onChange={(event) =>
                  setBudgetForm((current) => ({
                    ...current,
                    period: event.target.value as "daily" | "monthly" | "custom",
                  }))
                }
              >
                <option value="daily">{t("budgetsDaily")}</option>
                <option value="monthly">{t("budgetsMonthly")}</option>
                <option value="custom">{t("budgetsCustom")}</option>
              </select>
            </label>
          </div>
          <ScopeTargetField
            budgetForm={budgetForm}
            scopeOptions={scopeOptions}
            scopeOptionsLoading={scopeOptionsLoading}
            setBudgetForm={setBudgetForm}
            canWrite={canWrite}
          />
        </>
      )}
      {activeTab === "limits" && (
        <>
          <div className="budget-form-grid">
            <label>
              {t("budgetsAmountLimit")}
              <input
                disabled={!canWrite}
                inputMode="decimal"
                value={budgetForm.amountLimit}
                onChange={(event) => setBudgetForm((current) => ({ ...current, amountLimit: event.target.value }))}
              />
            </label>
            <label>
              {t("budgetsTokenLimit")}
              <input
                disabled={!canWrite}
                inputMode="numeric"
                placeholder={t("budgetsOptional")}
                value={budgetForm.tokenLimit}
                onChange={(event) => setBudgetForm((current) => ({ ...current, tokenLimit: event.target.value }))}
              />
            </label>
          </div>
          <div className="budget-form-grid">
            <label>
              {t("budgetsLimitType")}
              <select
                disabled={!canWrite}
                value={budgetForm.budgetType}
                onChange={(event) =>
                  setBudgetForm((current) => ({ ...current, budgetType: event.target.value as "hard" | "soft" }))
                }
              >
                <option value="hard">{t("budgetsHardStop")}</option>
                <option value="soft">{t("budgetsSoftAlert")}</option>
              </select>
            </label>
            <label>
              {t("budgetsAlertThreshold")}
              <input
                disabled={!canWrite}
                inputMode="numeric"
                value={budgetForm.alertThreshold}
                onChange={(event) => setBudgetForm((current) => ({ ...current, alertThreshold: event.target.value }))}
              />
            </label>
          </div>
          <div className="inline-note">{t("budgetsHardStopNote")}</div>
        </>
      )}
      <div className="provider-actions">
        <Button onClick={onSave} disabled={!canSaveBudget}>
          {saving ? t("budgetsSaving") : t("budgetsSaveGuardrail")}
        </Button>
      </div>
      {(saveMessage || saveError) && (
        <div className={cx("form-message", saveError ? "error" : false)}>{saveError ?? saveMessage}</div>
      )}
    </section>
  );
}

function BudgetGuardrailPreview({
  budgetForm,
  scopeOptions,
}: {
  budgetForm: BudgetFormState;
  scopeOptions: Array<{ id: string; label: string }>;
}) {
  const { t } = useLocale();
  const targetLabel =
    budgetForm.scopeType === "tenant"
      ? t("budgetsScopeTenant")
      : scopeOptions.find((option) => option.id === budgetForm.scopeId)?.label || t("budgetsScopeTargetPending");
  const amountLimit = budgetForm.amountLimit.trim()
    ? `$${budgetForm.amountLimit.trim()}`
    : t("budgetsAmountLimitPending");
  const tokenLimit = budgetForm.tokenLimit.trim()
    ? t("budgetsTokenLimitPreview").replace("{{count}}", budgetForm.tokenLimit.trim())
    : t("budgetsTokenLimitPending");

  return (
    <aside className="budget-guardrail-preview" aria-label={t("budgetsGuardrailPreview")}>
      <div>
        <span>{t("budgetsGuardrailPreviewScope")}</span>
        <strong>
          {formatScope(budgetForm.scopeType, t)} · {targetLabel}
        </strong>
      </div>
      <div>
        <span>{t("budgetsGuardrailPreviewLimit")}</span>
        <strong>
          {amountLimit} · {tokenLimit}
        </strong>
      </div>
      <div>
        <span>{t("budgetsGuardrailPreviewEnforcement")}</span>
        <strong>
          {budgetForm.budgetType === "hard" ? t("budgetsHardStop") : t("budgetsSoftAlert")} ·{" "}
          {t("budgetsGuardrailPreviewAlert").replace("{{threshold}}", budgetForm.alertThreshold || "-")}
        </strong>
      </div>
    </aside>
  );
}

function ScopeTargetField({
  budgetForm,
  canWrite,
  scopeOptions,
  scopeOptionsLoading,
  setBudgetForm,
}: {
  budgetForm: BudgetFormState;
  canWrite: boolean;
  scopeOptions: Array<{ id: string; label: string }>;
  scopeOptionsLoading: boolean;
  setBudgetForm: React.Dispatch<React.SetStateAction<BudgetFormState>>;
}) {
  const { t } = useLocale();
  if (budgetForm.scopeType === "tenant") {
    return null;
  }
  if (budgetForm.scopeType === "agent" && !scopeOptionsLoading && scopeOptions.length === 0) {
    return (
      <>
        <label>
          {t("budgetsAgentInstanceUuid")}
          <input
            disabled={!canWrite}
            placeholder={t("budgetsAgentInstancePlaceholder")}
            value={budgetForm.scopeId}
            onChange={(event) => setBudgetForm((current) => ({ ...current, scopeId: event.target.value }))}
          />
        </label>
        <div className="inline-note">{t("budgetsNoAgentInstances")}</div>
      </>
    );
  }
  return (
    <>
      <label>
        {t("budgetsScopeTarget")}
        <select
          value={budgetForm.scopeId}
          onChange={(event) => setBudgetForm((current) => ({ ...current, scopeId: event.target.value }))}
          disabled={!canWrite || scopeOptionsLoading || scopeOptions.length === 0}
        >
          <option value="">
            {scopeOptionsLoading
              ? t("budgetsLoadingTargets")
              : `${t("budgetsSelectTarget")} ${formatScope(budgetForm.scopeType, t)}`}
          </option>
          {scopeOptions.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      {budgetForm.scopeType !== "agent" && !scopeOptionsLoading && scopeOptions.length === 0 && (
        <div className="inline-note">
          {t("budgetsNoTargetsPrefix")} {formatScope(budgetForm.scopeType, t)} {t("budgetsNoTargetsSuffix")}
        </div>
      )}
    </>
  );
}
