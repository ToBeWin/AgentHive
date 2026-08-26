import { readFileSync } from "node:fs";
import { readStylesSource } from "./read-styles.mjs";

const pageSource = readFileSync(new URL("../src/pages/DigitalEmployeesPage.tsx", import.meta.url), "utf8");
const conversationSource = readFileSync(
  new URL("../src/pages/digital-employees/EmployeeConversationPanel.tsx", import.meta.url),
  "utf8",
);
const resultSource = readFileSync(
  new URL("../src/pages/digital-employees/EmployeeResultPanel.tsx", import.meta.url),
  "utf8",
);
const quickPromptSource = readFileSync(
  new URL("../src/pages/digital-employees/EmployeeQuickPrompts.tsx", import.meta.url),
  "utf8",
);
const messagesSource = readFileSync(new URL("../src/i18n/messages/common.ts", import.meta.url), "utf8");
const zhMessagesSource = readFileSync(new URL("../src/i18n/messages/common.zh.ts", import.meta.url), "utf8");
const stylesSource = readStylesSource();

invariant(
  pageSource.includes("EmployeeConversationPanel") &&
    pageSource.includes("EmployeeResultPanel") &&
    !pageSource.includes("EmployeeTaskPanel") &&
    !pageSource.includes("EmployeeScenarioLauncherPanel"),
  "Employee page must use the simplified conversation + result layout.",
);
invariant(
  conversationSource.includes("employee-conversation-panel") && conversationSource.includes("EmployeeQuickPrompts"),
  "Employee conversation panel must host quick prompts above the composer.",
);
invariant(
  resultSource.includes("employee-result-panel") && resultSource.includes("employee-result-sources"),
  "Employee result panel must expose copy actions and knowledge sources.",
);
invariant(
  quickPromptSource.includes("employee-quick-prompts") && quickPromptSource.includes("employee-quick-prompt"),
  "Employee quick prompts must use compact chips instead of scenario cards.",
);
invariant(
  stylesSource.includes(".employee-layout.result-open") &&
    stylesSource.includes(".employee-conversation-panel") &&
    stylesSource.includes(".employee-result-panel"),
  "Employee v2 layout styles are missing.",
);

const requiredMessageKeys = [
  "digitalEmployeesQuickPrompts",
  "digitalEmployeesResultPanel",
  "digitalEmployeesRecentChats",
  "digitalEmployeesNewChat",
  "digitalEmployeesShowResult",
  "digitalEmployeesHideResult",
];
const enMessages = extractObjectBody(messagesSource, "commonEn");
const zhMessages = extractObjectBody(zhMessagesSource, "commonZh");

for (const key of requiredMessageKeys) {
  invariant(hasMessageKey(enMessages, key), `Missing English employee v2 i18n key: ${key}`);
  invariant(hasMessageKey(zhMessages, key), `Missing Chinese employee v2 i18n key: ${key}`);
}

console.log("Employee task flow workflow verification passed.");

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
