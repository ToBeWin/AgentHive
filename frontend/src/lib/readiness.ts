export function readinessReasonLabel(reason: string, t: (key: string) => string) {
  if (reason === "model_policy_not_configured") {
    return t("agentReadinessReasonModelMissing");
  }
  if (reason === "model_route_unavailable") {
    return t("agentReadinessReasonModelRouteUnavailable");
  }
  if (reason === "model_unavailable") {
    return t("agentReadinessReasonModelUnavailable");
  }
  if (reason === "knowledge_not_bound") {
    return t("agentReadinessReasonKnowledgeMissing");
  }
  if (reason === "agent_not_active") {
    return t("agentReadinessReasonNotActive");
  }
  return t("agentReadinessReasonUnknown");
}

export function readinessReasonLabels(reasons: string[], t: (key: string) => string) {
  return reasons.map((reason) => readinessReasonLabel(reason, t));
}

export function readinessReasonEmployeeImpact(reason: string, t: (key: string) => string) {
  if (reason === "model_policy_not_configured") {
    return t("agentReadinessEmployeeImpactModelMissing");
  }
  if (reason === "model_route_unavailable") {
    return t("agentReadinessEmployeeImpactModelRouteUnavailable");
  }
  if (reason === "model_unavailable") {
    return t("agentReadinessEmployeeImpactModelUnavailable");
  }
  if (reason === "knowledge_not_bound") {
    return t("agentReadinessEmployeeImpactKnowledgeMissing");
  }
  if (reason === "agent_not_active") {
    return t("agentReadinessEmployeeImpactNotActive");
  }
  return t("agentReadinessEmployeeImpactUnknown");
}

export function readinessReasonAdminAction(reason: string, t: (key: string) => string) {
  if (reason === "model_policy_not_configured") {
    return t("agentReadinessAdminActionModelMissing");
  }
  if (reason === "model_route_unavailable") {
    return t("agentReadinessAdminActionModelRouteUnavailable");
  }
  if (reason === "model_unavailable") {
    return t("agentReadinessAdminActionModelUnavailable");
  }
  if (reason === "knowledge_not_bound") {
    return t("agentReadinessAdminActionKnowledgeMissing");
  }
  if (reason === "agent_not_active") {
    return t("agentReadinessAdminActionNotActive");
  }
  return t("agentReadinessAdminActionUnknown");
}

export function uniqueReadinessReasons(reasons: string[]) {
  return Array.from(new Set(reasons.filter(Boolean)));
}
