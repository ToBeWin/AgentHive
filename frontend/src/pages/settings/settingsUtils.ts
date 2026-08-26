import type {
  DeliveryAssessment,
  DeliveryCheck,
  DeliveryStatus,
  SystemComponentRemediation,
  SystemComponentReport,
  SystemComponentStatus,
  SystemHealthReport,
} from "../../lib/api";

export interface ComponentHealthRow {
  key: string;
  report: SystemComponentReport;
}

type Translate = (key: string) => string;

interface DetailPair {
  key: string;
  rawKey: string;
  value: string;
}

export function healthRows(report: SystemHealthReport | null): ComponentHealthRow[] {
  if (!report) {
    return [];
  }
  return Object.entries(report.components)
    .map(([key, component]) => ({ key, report: component }))
    .sort(
      (left, right) =>
        statusWeight(left.report.status) - statusWeight(right.report.status) || left.key.localeCompare(right.key),
    );
}

export function statusTone(status: SystemComponentStatus) {
  if (status === "healthy" || status === "configured") {
    return "good";
  }
  if (status === "degraded" || status === "not_configured") {
    return "warning";
  }
  return "bad";
}

export function componentStatusLabel(status: SystemComponentStatus, t: Translate) {
  if (status === "healthy") {
    return t("settingsComponentStatusHealthy");
  }
  if (status === "configured") {
    return t("settingsComponentStatusConfigured");
  }
  if (status === "degraded") {
    return t("settingsComponentStatusDegraded");
  }
  if (status === "not_configured") {
    return t("settingsComponentStatusNotConfigured");
  }
  if (status === "unhealthy") {
    return t("settingsComponentStatusUnhealthy");
  }
  if (status === "error") {
    return t("settingsComponentStatusError");
  }
  return status;
}

export function statusWeight(status: SystemComponentStatus) {
  if (status === "unhealthy" || status === "error") {
    return 0;
  }
  if (status === "degraded" || status === "not_configured") {
    return 1;
  }
  return 2;
}

export function deliveryTone(status: DeliveryStatus | undefined) {
  if (status === "ready") {
    return "good";
  }
  if (status === "ready_with_warnings") {
    return "warning";
  }
  return "bad";
}

export function deliveryStatusLabel(status: DeliveryStatus | undefined, t: (key: string) => string) {
  if (status === "ready") {
    return t("settingsDeliveryReady");
  }
  if (status === "ready_with_warnings") {
    return t("settingsDeliveryReadyWithWarnings");
  }
  if (status === "blocked") {
    return t("settingsDeliveryBlocked");
  }
  return status || "-";
}

export function localizedDeliverySummary(
  delivery: DeliveryAssessment | null | undefined,
  t: Translate,
  fallback?: string,
) {
  if (!delivery) {
    return fallback ?? "-";
  }
  if (delivery.status === "ready") {
    return t("settingsDeliverySummaryReady");
  }
  if (delivery.status === "ready_with_warnings") {
    return t("settingsDeliverySummaryReadyWithWarnings")
      .replace("{{warnings}}", String(delivery.warning_count))
      .replace("{{checks}}", String(delivery.checks.length));
  }
  if (delivery.status === "blocked") {
    return t("settingsDeliverySummaryBlocked")
      .replace("{{blockers}}", String(delivery.blocker_count))
      .replace("{{warnings}}", String(delivery.warning_count));
  }
  return delivery.summary || fallback || delivery.status || "-";
}

export function deliveryIssueRows(checks: DeliveryCheck[]) {
  return [...checks].sort((left, right) => severityWeight(left.severity) - severityWeight(right.severity));
}

export function componentLabel(key: string, t?: Translate) {
  const labelKey = componentLabelKey(key);
  if (labelKey && t) {
    return t(labelKey);
  }
  if (labelKey) {
    return fallbackComponentLabels[key] ?? titleizeKey(key);
  }
  return titleizeKey(key);
}

export function componentLabelKey(key: string) {
  return componentLabelKeys[key] ?? null;
}

function titleizeKey(key: string) {
  return key
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

const componentLabelKeys: Record<string, string> = {
  active_video_models: "settingsDetailActiveVideoModels",
  active_slot_count: "settingsDetailActiveSlotCount",
  agent_concurrency: "settingsComponentAgentConcurrency",
  agent_limit: "settingsDetailAgentLimit",
  audit_diagnostics: "settingsComponentAuditDiagnostics",
  budget_governance: "settingsComponentBudgetGovernance",
  channel_gateway: "settingsComponentChannelGateway",
  configured: "settingsDetailConfigured",
  database: "settingsComponentDatabase",
  docs_anchor: "settingsDetailDocsAnchor",
  environment: "settingsDetailEnvironment",
  frontend: "settingsComponentFrontend",
  install_id_configured: "settingsDetailInstallIdConfigured",
  knowledge_runtime: "settingsComponentKnowledgeRuntime",
  license_identity: "settingsComponentLicenseIdentity",
  litellm: "settingsComponentLiteLLM",
  machine_fingerprint_configured: "settingsDetailMachineFingerprintConfigured",
  media_generation: "settingsComponentMediaGeneration",
  media_worker: "settingsComponentMediaWorker",
  minio: "settingsComponentMinIO",
  missing_operational_settings: "settingsDetailMissingOperationalSettings",
  pgvector: "settingsComponentPgvector",
  production_config: "settingsComponentProductionConfig",
  redis: "settingsComponentRedis",
  required_provider_settings: "settingsDetailRequiredProviderSettings",
  runtime_deployment_id_configured: "settingsDetailRuntimeDeploymentIdConfigured",
  tenant_limit: "settingsDetailTenantLimit",
  user_limit: "settingsDetailUserLimit",
  video_route_count: "settingsDetailVideoRouteCount",
  webhook_public_url_configured: "settingsDetailWebhookPublicUrlConfigured",
};

const fallbackComponentLabels: Record<string, string> = {
  active_video_models: "Active video models",
  active_slot_count: "Active slots",
  agent_concurrency: "Agent concurrency guard",
  agent_limit: "Agent limit",
  audit_diagnostics: "Audit diagnostics",
  budget_governance: "Budget governance",
  channel_gateway: "Channel gateway",
  configured: "Configured",
  database: "PostgreSQL",
  docs_anchor: "Docs anchor",
  environment: "Environment",
  frontend: "Frontend",
  install_id_configured: "Install ID configured",
  knowledge_runtime: "Knowledge runtime",
  license_identity: "License identity",
  litellm: "LiteLLM",
  machine_fingerprint_configured: "Machine fingerprint configured",
  media_generation: "Media Generation Gateway",
  media_worker: "Media Generation Worker",
  minio: "MinIO",
  missing_operational_settings: "Missing operational settings",
  pgvector: "pgvector",
  production_config: "Production config",
  redis: "Redis",
  required_provider_settings: "Required provider settings",
  runtime_deployment_id_configured: "Runtime deployment ID configured",
  tenant_limit: "Tenant limit",
  user_limit: "User limit",
  video_route_count: "Video route count",
  webhook_public_url_configured: "Webhook public URL configured",
};

export function formatCheckedAt(value: string | undefined, locale: string) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function detailPairs(details: Record<string, unknown> | undefined, t?: Translate): DetailPair[] {
  if (!details) {
    return [];
  }
  return Object.entries(details).map(([key, value]) => ({
    key: componentLabel(key, t),
    rawKey: key,
    value: formatDetailValue(value),
  }));
}

export function formatDetailValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (Array.isArray(value)) {
    return value.map(formatDetailValue).join(", ");
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

export function remediationText(remediation: SystemComponentRemediation | undefined) {
  if (!remediation) {
    return null;
  }
  return [remediation.summary, remediation.action].filter(Boolean).join(" ");
}

export function localizedRemediationText(remediation: SystemComponentRemediation | null | undefined, t: Translate) {
  const parts = localizedRemediationParts(remediation, t);
  if (!parts) {
    return null;
  }
  return [parts.summary, parts.action].filter(Boolean).join(" ");
}

export interface RemediationParts {
  action: string | null;
  docsAnchor: string | null;
  summary: string | null;
}

export function remediationParts(remediation: SystemComponentRemediation | null | undefined): RemediationParts | null {
  if (!remediation) {
    return null;
  }
  const summary = remediation.summary?.trim() || null;
  const action = remediation.action?.trim() || null;
  const docsAnchor = remediation.docs_anchor?.trim() || null;
  if (!summary && !action && !docsAnchor) {
    return null;
  }
  return { action, docsAnchor, summary };
}

export function localizedRemediationParts(
  remediation: SystemComponentRemediation | null | undefined,
  t: Translate,
): RemediationParts | null {
  const parts = remediationParts(remediation);
  if (!parts) {
    return null;
  }
  const override = parts.docsAnchor ? remediationMessageKeys[parts.docsAnchor] : null;
  if (!override) {
    return parts;
  }
  return {
    action: t(override.action),
    docsAnchor: parts.docsAnchor,
    summary: t(override.summary),
  };
}

const remediationMessageKeys: Record<string, { action: string; summary: string }> = {
  "deployment.agent_concurrency": {
    action: "settingsRemediationAgentConcurrencyAction",
    summary: "settingsRemediationAgentConcurrencySummary",
  },
  "deployment.agent_runtime": {
    action: "settingsRemediationAgentRuntimeAction",
    summary: "settingsRemediationAgentRuntimeSummary",
  },
  "deployment.database": {
    action: "settingsRemediationDatabaseAction",
    summary: "settingsRemediationDatabaseSummary",
  },
  "deployment.frontend": {
    action: "settingsRemediationFrontendAction",
    summary: "settingsRemediationFrontendSummary",
  },
  "deployment.license": {
    action: "settingsRemediationLicenseAction",
    summary: "settingsRemediationLicenseSummary",
  },
  "deployment.litellm": {
    action: "settingsRemediationLiteLLMAction",
    summary: "settingsRemediationLiteLLMSummary",
  },
  "deployment.media_generation": {
    action: "settingsRemediationMediaGenerationAction",
    summary: "settingsRemediationMediaGenerationSummary",
  },
  "deployment.media_worker": {
    action: "settingsRemediationMediaWorkerAction",
    summary: "settingsRemediationMediaWorkerSummary",
  },
  "deployment.minio": {
    action: "settingsRemediationMinIOAction",
    summary: "settingsRemediationMinIOSummary",
  },
  "deployment.pgvector": {
    action: "settingsRemediationPgvectorAction",
    summary: "settingsRemediationPgvectorSummary",
  },
  "deployment.production_config": {
    action: "settingsRemediationProductionConfigAction",
    summary: "settingsRemediationProductionConfigSummary",
  },
  "deployment.ragflow": {
    action: "settingsRemediationRAGFlowAction",
    summary: "settingsRemediationRAGFlowSummary",
  },
  "deployment.redis": {
    action: "settingsRemediationRedisAction",
    summary: "settingsRemediationRedisSummary",
  },
};

function severityWeight(severity: string) {
  if (severity === "blocker") {
    return 0;
  }
  if (severity === "warning") {
    return 1;
  }
  return 2;
}
