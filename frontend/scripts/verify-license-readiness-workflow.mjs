import { readFileSync } from "node:fs";
import { readStylesSource } from "./read-styles.mjs";

const componentSource = readFileSync(
  new URL("../src/pages/license/LicenseReadinessPanel.tsx", import.meta.url),
  "utf8",
);
const messagesSource = readFileSync(new URL("../src/i18n/messages/license.ts", import.meta.url), "utf8");
const zhMessagesSource = readFileSync(new URL("../src/i18n/messages/license.zh.ts", import.meta.url), "utf8");
const stylesSource = readStylesSource();

invariant(
  componentSource.includes("license-readiness-workspace") &&
    componentSource.includes("license-readiness-steps") &&
    componentSource.includes("license-readiness-detail"),
  "License readiness must use a staged handover workspace instead of a flat checklist.",
);
invariant(
  !componentSource.includes("license-readiness-list") && !componentSource.includes("license-readiness-item"),
  "License readiness must not regress to flat list/item presentation.",
);
invariant(
  stylesSource.includes(".license-readiness-workspace") &&
    stylesSource.includes(".license-readiness-step") &&
    stylesSource.includes(".license-readiness-detail") &&
    stylesSource.includes(".status-attention"),
  "License readiness staged workspace styles are missing.",
);

const requiredMessageKeys = [
  "licenseReadinessReady",
  "licenseReadinessAttention",
  "licenseReadinessReadyCount",
  "licenseReadinessAttentionCount",
  "licenseReadinessStageTabs",
  "licenseReadinessSelectedStage",
  "licenseReadinessCurrentStage",
  "licenseReadinessReadyMetric",
  "licenseReadinessAttentionMetric",
  "licenseReadinessIssueMetric",
];
const enMessages = extractObjectBody(messagesSource, "licenseEn");
const zhMessages = extractObjectBody(zhMessagesSource, "licenseZh");

for (const key of requiredMessageKeys) {
  invariant(hasMessageKey(enMessages, key), `Missing English license readiness i18n key: ${key}`);
  invariant(hasMessageKey(zhMessages, key), `Missing Chinese license readiness i18n key: ${key}`);
}

console.log("License readiness workflow verification passed.");

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
