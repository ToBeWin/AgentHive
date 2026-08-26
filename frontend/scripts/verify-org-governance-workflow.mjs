import { readFileSync } from "node:fs";
import { readStylesSource } from "./read-styles.mjs";

const componentSource = readFileSync(
  new URL("../src/pages/departments/OrgGovernanceLoopPanel.tsx", import.meta.url),
  "utf8",
);
const messagesSource = readFileSync(new URL("../src/i18n/messages/departments.ts", import.meta.url), "utf8");
const zhMessagesSource = readFileSync(new URL("../src/i18n/messages/departments.zh.ts", import.meta.url), "utf8");
const stylesSource = readStylesSource();

invariant(
  componentSource.includes("org-governance-loop-workspace") &&
    componentSource.includes("org-governance-loop-steps") &&
    componentSource.includes("org-governance-loop-detail"),
  "Organization governance loop must use a staged workspace instead of a flat card wall.",
);
invariant(
  !componentSource.includes("org-governance-loop-card") && !componentSource.includes("org-governance-loop-grid"),
  "Organization governance loop must not regress to flat card/grid presentation.",
);
invariant(
  stylesSource.includes(".org-governance-loop-workspace") &&
    stylesSource.includes(".org-governance-loop-step") &&
    stylesSource.includes(".org-governance-loop-detail"),
  "Organization governance staged workspace styles are missing.",
);

const requiredMessageKeys = [
  "departmentsLoopReadyCount",
  "departmentsLoopReviewCount",
  "departmentsLoopBlockedCount",
  "departmentsLoopStageTabs",
  "departmentsLoopSelectedStage",
  "departmentsLoopCurrentMetric",
  "departmentsLoopOpenStep",
];
const enMessages = extractObjectBody(messagesSource, "departmentsEn");
const zhMessages = extractObjectBody(zhMessagesSource, "departmentsZh");

for (const key of requiredMessageKeys) {
  invariant(hasMessageKey(enMessages, key), `Missing English organization governance i18n key: ${key}`);
  invariant(hasMessageKey(zhMessages, key), `Missing Chinese organization governance i18n key: ${key}`);
}

console.log("Organization governance workflow verification passed.");

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
