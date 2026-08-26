import { readFileSync } from "node:fs";
import { readStylesSource } from "./read-styles.mjs";

const detailsPanelSource = readFileSync(new URL("../src/pages/audit/AuditEventDetailsPanel.tsx", import.meta.url), "utf8");
const auditUtilsSource = readFileSync(new URL("../src/pages/audit/auditUtils.ts", import.meta.url), "utf8");
const auditMessagesSource = readFileSync(new URL("../src/i18n/messages/audit.ts", import.meta.url), "utf8");
const auditZhMessagesSource = readFileSync(new URL("../src/i18n/messages/audit.zh.ts", import.meta.url), "utf8");
const auditPrototypeSource = readFileSync(new URL("../src/hooks/admin/auditPrototype.ts", import.meta.url), "utf8");
const auditApiSource = readFileSync(new URL("../src/lib/api/audit.ts", import.meta.url), "utf8");
const stylesSource = readStylesSource();

for (const token of [
  "adapterMode",
  "auditRuntimeSummary",
  "deploymentId",
  "modelKey",
  "providerKey",
  "routingKey",
  "routeAttempts",
  "status",
]) {
  invariant(auditUtilsSource.includes(token), `Audit runtime utility must expose ${token}.`);
}
invariant(
  auditUtilsSource.includes("details.runtime_summary") && auditUtilsSource.includes("runtimeSummary?.adapter_mode"),
  "Audit runtime utility must parse normalized runtime_summary evidence.",
);
invariant(
  auditUtilsSource.includes("compactDetailValue") && auditUtilsSource.includes("runtime = auditRuntimeSummary"),
  "Audit table details must render nested runtime summaries instead of object strings.",
);
invariant(
  !auditUtilsSource.includes("String(value)}`"),
  "Audit compact details must not stringify nested values into [object Object].",
);

invariant(
  detailsPanelSource.includes("auditRuntimeEvidence") && detailsPanelSource.includes("audit-route-attempt-list"),
  "Audit details panel must render runtime route evidence.",
);
invariant(
  detailsPanelSource.includes("runtimeSummaryLabel") &&
    detailsPanelSource.includes("auditRuntimeRealModelCall") &&
    detailsPanelSource.includes("auditRuntimeRoute"),
  "Audit details panel must render normalized runtime mode labels.",
);
invariant(
  auditPrototypeSource.includes('action: "chat.message.send"') &&
    auditPrototypeSource.includes("runtime_summary") &&
    auditPrototypeSource.includes("selected_route_reason") &&
    auditPrototypeSource.includes("route_attempts"),
  "Prototype audit data must include a chat.message.send runtime route event.",
);
invariant(stylesSource.includes(".audit-runtime-evidence"), "Audit runtime evidence must have dedicated styling.");
invariant(
  auditApiSource.includes("/api/v1/audit/logs/export?") && !auditApiSource.includes("/api/v1/audit-logs/export"),
  "Audit exports must use the canonical /api/v1/audit/logs/export path.",
);

const enMessages = extractObjectBody(auditMessagesSource, "auditEn");
const zhMessages = extractObjectBody(auditZhMessagesSource, "auditZh");
for (const key of [
  "auditRuntimeEvidence",
  "auditRuntimeEvidenceDetail",
  "auditRuntimeLocalRuntime",
  "auditRuntimeMediaGenerationTask",
  "auditRuntimeMockModelCall",
  "auditRuntimeRealModelCall",
  "auditRuntimeRoute",
  "auditRuntimeUnknown",
]) {
  invariant(hasMessageKey(enMessages, key), `Missing English audit runtime i18n key: ${key}`);
  invariant(hasMessageKey(zhMessages, key), `Missing Chinese audit runtime i18n key: ${key}`);
}

console.log("Audit runtime evidence verification passed.");

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
