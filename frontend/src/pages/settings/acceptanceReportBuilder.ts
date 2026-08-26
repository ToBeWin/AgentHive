import type { SystemDiagnostics } from "../../hooks/admin/system";
import {
  componentLabel,
  deliveryStatusLabel,
  formatCheckedAt,
  formatDetailValue,
  healthRows,
  localizedDeliverySummary,
  localizedRemediationText,
} from "./settingsUtils";

export function buildAcceptanceReport({
  diagnostics,
  generatedAt,
  locale,
  t,
}: {
  diagnostics: SystemDiagnostics;
  generatedAt: string;
  locale: string;
  t: (key: string) => string;
}) {
  const { health, info, readiness } = diagnostics;
  const delivery = readiness.delivery ?? null;
  const connectionAcceptance = diagnostics.connection_acceptance ?? null;
  const knowledgeAcceptance = diagnostics.knowledge_acceptance ?? null;
  const rows = healthRows(readiness);
  const blockers = delivery?.blockers ?? [];
  const warnings = delivery?.warnings ?? [];
  const licenseIdentity = readiness.components.license_identity ?? health.components.license_identity;
  const productionConfig = readiness.components.production_config ?? health.components.production_config;

  return [
    `# ${t("settingsAcceptanceReportTitle")}`,
    "",
    `- ${t("settingsAcceptanceGeneratedAt")}: ${generatedAt}`,
    `- ${t("settingsProduct")}: ${info.name} ${info.version} (${info.edition})`,
    `- ${t("settingsAcceptanceEnvironment")}: ${readiness.environment}`,
    `- ${t("settingsCheckedAt").replace("{{time}}", formatCheckedAt(readiness.checked_at, locale))}`,
    "",
    `## ${t("settingsAcceptanceDecision")}`,
    "",
    `- ${t("settingsAcceptanceStatus")}: ${delivery ? deliveryStatusLabel(delivery.status, t) : t("settingsDeliveryUnavailable")}`,
    `- ${t("settingsDeliveryBlockers")}: ${delivery?.blocker_count ?? "-"}`,
    `- ${t("settingsDeliveryWarnings")}: ${delivery?.warning_count ?? "-"}`,
    `- ${t("settingsDeliveryChecks")}: ${delivery?.checks.length ?? rows.length}`,
    `- ${t("settingsAcceptanceSummary")}: ${localizedDeliverySummary(delivery, t, readiness.status)}`,
    "",
    `## ${t("settingsAcceptanceIssues")}`,
    "",
    ...issueSection(t("settingsDeliveryBlockers"), blockers, t),
    "",
    ...issueSection(t("settingsDeliveryWarnings"), warnings, t),
    "",
    `## ${t("settingsAcceptanceCoreEvidence")}`,
    "",
    `| ${t("settingsComponent")} | ${t("settingsStatus")} | ${t("settingsMessage")} | ${t("settingsRemediationHeader")} |`,
    "| --- | --- | --- | --- |",
    ...rows.map((row) =>
      [
        componentLabel(row.key, t),
        row.report.status,
        sanitizeMarkdownCell(row.report.message ?? "-"),
        sanitizeMarkdownCell(localizedRemediationText(row.report.remediation, t) ?? "-"),
      ].join(" | "),
    ),
    "",
    `## ${t("settingsAcceptanceDeploymentIdentity")}`,
    "",
    ...componentDetails("license_identity", licenseIdentity, t),
    "",
    `## ${t("settingsAcceptanceProductionConfig")}`,
    "",
    ...componentDetails("production_config", productionConfig, t),
    "",
    `## ${t("settingsAcceptanceConnectionEvidence")}`,
    "",
    ...connectionEvidenceDetails(connectionAcceptance, t),
    "",
    `## ${t("settingsAcceptanceKnowledgeEvidence")}`,
    "",
    ...knowledgeEvidenceDetails(knowledgeAcceptance, t),
    "",
    `## ${t("settingsAcceptanceAgentProductionEvidence")}`,
    "",
    ...agentProductionEvidenceDetails(diagnostics, t),
    "",
    `## ${t("settingsAcceptanceHandoffActions")}`,
    "",
    `1. ${t("settingsAcceptanceActionStrictDiagnostics")}`,
    `2. ${t("settingsAcceptanceActionLicense")}`,
    `3. ${t("settingsAcceptanceActionBackup")}`,
    `4. ${t("settingsAcceptanceActionSignoff")}`,
    "",
  ].join("\n");
}

function agentProductionEvidenceDetails(diagnostics: SystemDiagnostics, t: (key: string) => string) {
  const componentKeys = [
    "agent_runtime",
    "agent_concurrency",
    "knowledge_runtime",
    "budget_governance",
    "channel_gateway",
    "litellm",
    "media_generation",
  ];
  const lines = [`### ${t("settingsAcceptanceAgentRuntimeComponents")}`, ""];

  for (const key of componentKeys) {
    lines.push(
      ...componentDetails(key, diagnostics.readiness.components[key] ?? diagnostics.health.components[key], t),
      "",
    );
  }

  const knowledgeEvidence = diagnostics.knowledge_acceptance;
  const connectionEvidence = diagnostics.connection_acceptance;
  lines.push(`### ${t("settingsAcceptanceAgentRuntimeSignals")}`, "");
  lines.push(
    `- ${t("settingsAcceptanceAgentKnowledgeRuns")}: ${knowledgeEvidence?.knowledge_enabled_run_count ?? "-"}`,
    `- ${t("settingsAcceptanceAgentRunsWithSources")}: ${knowledgeEvidence?.runs_with_sources_count ?? "-"}`,
    `- ${t("settingsAcceptanceAgentHumanReview")}: ${knowledgeEvidence?.human_review_required_count ?? "-"}`,
    `- ${t("settingsAcceptanceAgentGuardrails")}: ${knowledgeEvidence?.guardrail_triggered_count ?? "-"}`,
    `- ${t("settingsAcceptanceAgentProviders")}: ${connectionEvidence?.providers.join(", ") || "-"}`,
    `- ${t("settingsAcceptanceAgentLiveModelCalls")}: ${connectionEvidence?.live_network_call_count ?? "-"}`,
    `- ${t("settingsAcceptanceAgentMediaProbes")}: ${connectionEvidence?.media_live_probe_count ?? "-"}`,
    `- ${t("settingsAcceptanceAgentRecentFailures")}: ${connectionEvidence?.failed_recent_count ?? "-"}`,
  );

  return lines;
}

function knowledgeEvidenceDetails(
  evidence: SystemDiagnostics["knowledge_acceptance"] | null,
  t: (key: string) => string,
) {
  if (!evidence) {
    return [`- ${t("settingsAcceptanceKnowledgeEvidenceUnavailable")}`];
  }
  const lines = [
    `- status: ${evidence.status}`,
    `- summary: ${evidence.summary}`,
    `- recent_runs: ${evidence.recent_run_count}`,
    `- knowledge_enabled_runs: ${evidence.knowledge_enabled_run_count}`,
    `- runs_with_sources: ${evidence.runs_with_sources_count}`,
    `- human_review_required: ${evidence.human_review_required_count}`,
    `- guardrail_triggered: ${evidence.guardrail_triggered_count}`,
    `- agents: ${evidence.agents.join(", ") || "-"}`,
  ];
  if (evidence.latest_knowledge_run) {
    lines.push("", `### ${t("settingsAcceptanceLatestKnowledgeRun")}`);
    lines.push(...knowledgeRunDetails(evidence.latest_knowledge_run));
  }
  return lines;
}

function knowledgeRunDetails(run: NonNullable<SystemDiagnostics["knowledge_acceptance"]>["latest_knowledge_run"]) {
  if (!run) {
    return [];
  }
  return [
    `- agent: ${run.agent_key ?? "-"}`,
    `- instance: ${run.agent_instance_name ?? run.agent_instance_id ?? "-"}`,
    `- model: ${run.model_key ?? "-"}`,
    `- checked_at: ${run.checked_at ?? "-"}`,
    `- sources: ${run.source_count ?? "-"}`,
    `- confidence: ${run.confidence_level ?? "-"}`,
    `- max_score: ${run.max_score ?? "-"}`,
    `- review_required: ${String(run.requires_human_review ?? "-")}`,
    `- guardrail: ${run.guardrail_mode ?? "-"}`,
  ];
}

function connectionEvidenceDetails(
  evidence: SystemDiagnostics["connection_acceptance"] | null,
  t: (key: string) => string,
) {
  if (!evidence) {
    return [`- ${t("settingsAcceptanceConnectionEvidenceUnavailable")}`];
  }
  const lines = [
    `- status: ${evidence.status}`,
    `- summary: ${evidence.summary}`,
    `- recent_tests: ${evidence.recent_test_count}`,
    `- live_network_calls: ${evidence.live_network_call_count}`,
    `- media_live_probes: ${evidence.media_live_probe_count}`,
    `- recent_failures: ${evidence.failed_recent_count}`,
    `- providers: ${evidence.providers.join(", ") || "-"}`,
  ];
  if (evidence.latest_live_probe) {
    lines.push("", `### ${t("settingsAcceptanceLatestLiveProbe")}`);
    lines.push(...connectionProbeDetails(evidence.latest_live_probe));
  }
  if (
    evidence.latest_media_live_probe &&
    JSON.stringify(evidence.latest_media_live_probe) !== JSON.stringify(evidence.latest_live_probe)
  ) {
    lines.push("", `### ${t("settingsAcceptanceLatestMediaProbe")}`);
    lines.push(...connectionProbeDetails(evidence.latest_media_live_probe));
  }
  return lines;
}

function connectionProbeDetails(probe: NonNullable<SystemDiagnostics["connection_acceptance"]>["latest_live_probe"]) {
  if (!probe) {
    return [];
  }
  return [
    `- provider: ${probe.provider_key ?? "-"}`,
    `- model: ${probe.model_key ?? "-"}`,
    `- operation: ${probe.operation ?? "-"}`,
    `- ok: ${String(probe.ok ?? "-")}`,
    `- checked_at: ${probe.checked_at ?? "-"}`,
    `- HTTP status: ${probe.status_code ?? "-"}`,
    `- probe_path: ${probe.probe_path ?? "-"}`,
    `- latency_ms: ${probe.latency_ms ?? "-"}`,
  ];
}

function issueSection(
  title: string,
  checks: Array<{ label: string; message?: string; component: string }>,
  t: (key: string) => string,
) {
  if (checks.length === 0) {
    return [`### ${title}`, "", t("settingsDeliveryNoIssues")];
  }
  return [
    `### ${title}`,
    "",
    ...checks.flatMap((check) => [
      `- **${check.label}** (${componentLabel(check.component, t)})`,
      `  ${check.message ?? "-"}`,
    ]),
  ];
}

function componentDetails(
  componentName: string,
  component?: { status: string; message?: string; details?: Record<string, unknown> },
  t?: (key: string) => string,
) {
  if (!component) {
    return [`- ${componentLabel(componentName, t)}: not_available`];
  }
  const lines = [
    `- ${componentLabel(componentName, t)}`,
    `  - ${t ? t("settingsStatus") : "status"}: ${component.status}`,
    `  - ${t ? t("settingsMessage") : "message"}: ${component.message ?? "-"}`,
  ];
  for (const [key, value] of Object.entries(component.details ?? {})) {
    lines.push(`  - ${componentLabel(key, t)}: ${formatDetailValue(value)}`);
  }
  return lines;
}

function sanitizeMarkdownCell(value: string) {
  return value.replace(/\|/g, "\\|").replace(/\n/g, " ");
}
