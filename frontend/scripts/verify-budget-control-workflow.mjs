import { readFileSync } from "node:fs";
import { readStylesSource } from "./read-styles.mjs";

const componentSource = readFileSync(
  new URL("../src/pages/budgets/BudgetControlLoopPanel.tsx", import.meta.url),
  "utf8",
);
const messagesSource = readFileSync(new URL("../src/i18n/messages/budgets.ts", import.meta.url), "utf8");
const zhMessagesSource = readFileSync(new URL("../src/i18n/messages/budgets.zh.ts", import.meta.url), "utf8");
const stylesSource = readStylesSource();

invariant(
  componentSource.includes("budget-control-loop-workspace") &&
    componentSource.includes("budget-control-loop-steps") &&
    componentSource.includes("budget-control-loop-detail"),
  "Budget control loop must use a staged workspace instead of a flat card wall.",
);
invariant(
  !componentSource.includes("budget-control-loop-card") && !componentSource.includes("budget-control-loop-grid"),
  "Budget control loop must not regress to flat card/grid presentation.",
);
invariant(
  stylesSource.includes(".budget-control-loop-workspace") &&
    stylesSource.includes(".budget-control-loop-step") &&
    stylesSource.includes(".budget-control-loop-detail"),
  "Budget control staged workspace styles are missing.",
);

const requiredMessageKeys = [
  "budgetsLoopReadyCount",
  "budgetsLoopReviewCount",
  "budgetsLoopBlockedCount",
  "budgetsLoopStageTabs",
  "budgetsLoopSelectedStage",
  "budgetsLoopCurrentMetric",
  "budgetsLoopOpenStep",
];
const enMessages = extractObjectBody(messagesSource, "budgetsEn");
const zhMessages = extractObjectBody(zhMessagesSource, "budgetsZh");

for (const key of requiredMessageKeys) {
  invariant(hasMessageKey(enMessages, key), `Missing English budget workflow i18n key: ${key}`);
  invariant(hasMessageKey(zhMessages, key), `Missing Chinese budget workflow i18n key: ${key}`);
}

console.log("Budget control workflow verification passed.");

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
