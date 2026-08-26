import { readFileSync } from "node:fs";
import { readStylesSource } from "./read-styles.mjs";

const quickPromptSource = readFileSync(
  new URL("../src/pages/digital-employees/EmployeeQuickPrompts.tsx", import.meta.url),
  "utf8",
);
const pageSource = readFileSync(new URL("../src/pages/DigitalEmployeesPage.tsx", import.meta.url), "utf8");
const messagesSource = readFileSync(new URL("../src/i18n/messages/common.ts", import.meta.url), "utf8");
const zhMessagesSource = readFileSync(new URL("../src/i18n/messages/common.zh.ts", import.meta.url), "utf8");
const stylesSource = readStylesSource();

invariant(
  quickPromptSource.includes("employee-quick-prompts") && quickPromptSource.includes("employee-quick-prompt"),
  "Employee quick prompts must use compact chips instead of a scenario card wall.",
);
invariant(
  !pageSource.includes("EmployeeScenarioLauncherPanel"),
  "Employee main page must not mount the legacy scenario launcher panel.",
);
invariant(
  stylesSource.includes(".employee-quick-prompts") && stylesSource.includes(".employee-quick-prompt"),
  "Employee quick prompt styles are missing.",
);

const requiredMessageKeys = ["digitalEmployeesQuickPrompts"];
const enMessages = extractObjectBody(messagesSource, "commonEn");
const zhMessages = extractObjectBody(zhMessagesSource, "commonZh");

for (const key of requiredMessageKeys) {
  invariant(hasMessageKey(enMessages, key), `Missing English employee quick prompt i18n key: ${key}`);
  invariant(hasMessageKey(zhMessages, key), `Missing Chinese employee quick prompt i18n key: ${key}`);
}

console.log("Employee scenario workflow verification passed.");

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
