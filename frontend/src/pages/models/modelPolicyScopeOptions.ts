import type { LLMGovernanceTargetItem, LLMGovernanceTargetsResponse, LLMPolicyScope } from "../../lib/api";
import type { CredentialOwnerType } from "./modelUtils";

export interface ModelPolicyScopeTargetOption {
  id: string;
  label: string;
}

export interface ModelCredentialOwnerOption {
  id: string;
  label: string;
}

export function modelCredentialOwnerOptions({
  targets,
  ownerType,
}: {
  targets: LLMGovernanceTargetsResponse;
  ownerType: CredentialOwnerType;
}): ModelCredentialOwnerOption[] {
  if (ownerType === "department") {
    return targetOptions(targets.departments);
  }
  if (ownerType === "user") {
    return targetOptions(targets.users);
  }
  return [];
}

export function modelPolicyScopeTargetOptions({
  scopeType,
  targets,
}: {
  scopeType: LLMPolicyScope;
  targets: LLMGovernanceTargetsResponse;
}): ModelPolicyScopeTargetOption[] {
  if (scopeType === "department") {
    return targetOptions(targets.departments);
  }
  if (scopeType === "cost_center") {
    return targetOptions(targets.cost_centers);
  }
  if (scopeType === "user") {
    return targetOptions(targets.users);
  }
  if (scopeType === "agent") {
    return targetOptions(targets.agents);
  }
  if (scopeType === "channel") {
    return targetOptions(targets.channels);
  }
  return [];
}

function targetOptions(targets: LLMGovernanceTargetItem[]) {
  return targets.map((target) => ({
    id: target.id,
    label: target.status && target.status !== "active" ? `${target.label} (${target.status})` : target.label,
  }));
}
