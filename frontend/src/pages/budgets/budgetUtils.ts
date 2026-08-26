import type {
  BudgetGovernanceTargetItem,
  BudgetGovernanceTargetsResponse,
  BudgetPolicyResponse,
  BudgetScopeType,
} from "../../lib/api";

export interface BudgetFormState {
  alertThreshold: string;
  amountLimit: string;
  budgetType: "hard" | "soft";
  name: string;
  period: "daily" | "monthly" | "custom";
  scopeId: string;
  scopeType: BudgetScopeType;
  tokenLimit: string;
}

export function formatScope(scope: BudgetScopeType, t?: (key: string) => string) {
  if (t) {
    return t(`budgetsScope${scopeKeySuffix(scope)}`);
  }
  return scope.replace(/_/g, " ").replace(/\b\w/g, (match) => match.toUpperCase());
}

export function formatBudgetStatus(policy: BudgetPolicyResponse) {
  if (policy.status === "inactive") {
    return "INACTIVE";
  }
  if (policy.health === "exceeded") {
    return "EXCEEDED";
  }
  if (policy.health === "warning") {
    return "WARNING";
  }
  return "NORMAL";
}

export function budgetScopeOptions({
  scopeType,
  targets,
}: {
  scopeType: BudgetScopeType;
  targets: BudgetGovernanceTargetsResponse;
}): Array<{ id: string; label: string }> {
  if (scopeType === "department") {
    return targetOptions(targets.departments);
  }
  if (scopeType === "cost_center") {
    return targetOptions(targets.cost_centers);
  }
  if (scopeType === "user") {
    return targetOptions(targets.users);
  }
  if (scopeType === "channel") {
    return targetOptions(targets.channels);
  }
  if (scopeType === "agent") {
    return targetOptions(targets.agents);
  }
  return [];
}

export function budgetFormHasValidLimit(form: BudgetFormState) {
  return isPositiveDecimal(form.amountLimit) || isPositiveInteger(form.tokenLimit);
}

export function budgetFormHasValidAlertThreshold(form: BudgetFormState) {
  const value = Number(form.alertThreshold.trim());
  return Number.isFinite(value) && value > 0 && value <= 100;
}

function isPositiveDecimal(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return false;
  }
  const numeric = Number(trimmed);
  return Number.isFinite(numeric) && numeric > 0;
}

function isPositiveInteger(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return false;
  }
  const numeric = Number(trimmed);
  return Number.isSafeInteger(numeric) && numeric > 0;
}

function scopeKeySuffix(scope: BudgetScopeType) {
  return scope
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
}

function targetOptions(targets: BudgetGovernanceTargetItem[]) {
  return targets.map((target) => ({
    id: target.id,
    label: target.status && target.status !== "active" ? `${target.label} (${target.status})` : target.label,
  }));
}
