import { readFileSync } from "node:fs";
import { readStylesSource } from "./read-styles.mjs";

const panelSource = readFileSync(
  new URL("../src/pages/settings/DeliveryReadinessPanel.tsx", import.meta.url),
  "utf8",
);
const acceptanceOverviewSource = readFileSync(
  new URL("../src/pages/settings/DeliveryAcceptanceOverviewPanel.tsx", import.meta.url),
  "utf8",
);
const acceptanceReportSource = readFileSync(
  new URL("../src/pages/settings/acceptanceReportBuilder.ts", import.meta.url),
  "utf8",
);
const utilsSource = readFileSync(new URL("../src/pages/settings/settingsUtils.ts", import.meta.url), "utf8");
const messagesSource = readFileSync(new URL("../src/i18n/messages/settings.ts", import.meta.url), "utf8");
const zhMessagesSource = readFileSync(new URL("../src/i18n/messages/settings.zh.ts", import.meta.url), "utf8");
const stylesSource = readStylesSource();

invariant(
  panelSource.includes("DeliveryIssueCard") &&
    panelSource.includes("settings-delivery-remediation") &&
    panelSource.includes("settings-delivery-doc-anchor"),
  "Delivery readiness issues must render structured remediation cards.",
);
invariant(
  panelSource.includes("localizedDeliverySummary(delivery, t") &&
    !panelSource.includes("delivery?.summary ?? t(\"settingsDeliveryUnavailableDetail\")"),
  "Delivery readiness hero must localize the backend delivery summary.",
);
invariant(
  acceptanceOverviewSource.includes("localizedDeliverySummary(delivery, t)") &&
    !acceptanceOverviewSource.includes("delivery?.summary"),
  "Acceptance overview must localize the backend delivery summary.",
);
invariant(
  acceptanceReportSource.includes("localizedDeliverySummary(delivery, t, readiness.status)") &&
    acceptanceReportSource.includes("localizedRemediationText(row.report.remediation, t)") &&
    !acceptanceReportSource.includes("delivery?.summary"),
  "Acceptance report must localize delivery summary and remediation text.",
);
invariant(
  panelSource.includes("localizedRemediationParts(issue.remediation, t)") && !panelSource.includes("remediationText(issue"),
  "Delivery readiness panel must use localized structured remediation parts rather than backend-only flattened text.",
);
invariant(
  utilsSource.includes("export function localizedRemediationParts") &&
    utilsSource.includes("remediationMessageKeys") &&
    utilsSource.includes("deployment.database") &&
    utilsSource.includes("deployment.litellm"),
  "settingsUtils must expose localized remediation parsing with docs-anchor based overrides.",
);
invariant(
  stylesSource.includes(".settings-delivery-remediation") && stylesSource.includes(".settings-delivery-doc-anchor"),
  "Structured delivery remediation styles are missing.",
);

const enMessages = extractObjectBody(messagesSource, "settingsEn");
const zhMessages = extractObjectBody(zhMessagesSource, "settingsZh");
const requiredMessageKeys = [
  "settingsRemediationSummary",
  "settingsRemediationAction",
  "settingsRemediationDocsAnchor",
  "settingsDeliverySummaryReady",
  "settingsDeliverySummaryReadyWithWarnings",
  "settingsDeliverySummaryBlocked",
  "settingsRemediationDatabaseSummary",
  "settingsRemediationDatabaseAction",
  "settingsRemediationRedisSummary",
  "settingsRemediationRedisAction",
  "settingsRemediationMinIOSummary",
  "settingsRemediationMinIOAction",
  "settingsRemediationLiteLLMSummary",
  "settingsRemediationLiteLLMAction",
  "settingsRemediationPgvectorSummary",
  "settingsRemediationPgvectorAction",
  "settingsRemediationMediaGenerationSummary",
  "settingsRemediationMediaGenerationAction",
  "settingsRemediationMediaWorkerSummary",
  "settingsRemediationMediaWorkerAction",
];

for (const key of requiredMessageKeys) {
  invariant(hasMessageKey(enMessages, key), `Missing English delivery remediation i18n key: ${key}`);
  invariant(hasMessageKey(zhMessages, key), `Missing Chinese delivery remediation i18n key: ${key}`);
}

console.log("Delivery readiness workflow verification passed.");

function extractObjectBody(source, name) {
  const assignment = source.indexOf(`const ${name}`);
  invariant(assignment !== -1, `Unable to find ${name}`);
  const equals = source.indexOf("=", assignment);
  invariant(equals !== -1, `Unable to find ${name} assignment`);
  const start = source.indexOf("{", equals);
  invariant(start !== -1, `Unable to find ${name} object start`);
  let depth = 0;
  for (let index = start; index < source.length; index += 1) {
    const char = source[index];
    if (char === "{") {
      depth += 1;
    }
    if (char === "}") {
      depth -= 1;
      if (depth === 0) {
        return source.slice(start + 1, index);
      }
    }
  }
  throw new Error(`Unable to find ${name} object end`);
}

function hasMessageKey(source, key) {
  return new RegExp(`\\b${key}:`).test(source);
}

function invariant(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}
