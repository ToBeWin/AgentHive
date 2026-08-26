import { readFileSync } from "node:fs";
import { readStylesSource } from "./read-styles.mjs";

const runDetailsSource = readFileSync(new URL("../src/pages/chat/chatRunDetails.ts", import.meta.url), "utf8");
const runPanelSource = readFileSync(new URL("../src/pages/chat/ChatRunDetailsPanel.tsx", import.meta.url), "utf8");
const employeeRuntimeSource = readFileSync(
  new URL("../src/pages/digital-employees/EmployeeMessageRuntimeMeta.tsx", import.meta.url),
  "utf8",
);
const commonMessagesSource = readFileSync(new URL("../src/i18n/messages/common.ts", import.meta.url), "utf8");
const commonZhMessagesSource = readFileSync(new URL("../src/i18n/messages/common.zh.ts", import.meta.url), "utf8");
const chatMessagesSource = readFileSync(new URL("../src/i18n/messages/chat.ts", import.meta.url), "utf8");
const chatZhMessagesSource = readFileSync(new URL("../src/i18n/messages/chat.zh.ts", import.meta.url), "utf8");
const stylesSource = readStylesSource();

const requiredDetailFields = [
  "deploymentId",
  "runtimeErrorCode",
  "runtimeErrorMessage",
  "runtimeFailureCandidateCount",
  "runtimeFailureDetail",
  "runtimeFailureOperation",
  "runtimeHttpStatus",
  "runtimeMissingProviderKeys",
  "runtimeSummaryMode",
  "runtimeSummaryStatus",
  "routingKey",
];

for (const field of requiredDetailFields) {
  invariant(runDetailsSource.includes(field), `Chat run details must expose ${field}.`);
}

invariant(
  runDetailsSource.includes("runtime?.detail") && runDetailsSource.includes("missing_provider_keys"),
  "Chat run details must parse structured LLM route failure detail.",
);
invariant(
  runDetailsSource.includes("metadata.runtime_summary") && runDetailsSource.includes("adapter_mode"),
  "Chat run details must parse runtime summary from backend messages.",
);
invariant(
  runPanelSource.includes("hasRuntimeFailure") && runPanelSource.includes("chatRunRouteFailure"),
  "Chat run details panel must render route failure diagnostics.",
);
invariant(
  runPanelSource.includes("runtimeMissingProviderKeys") && runPanelSource.includes("runtimeFailureCandidateCount"),
  "Chat run details panel must show missing providers and candidate count.",
);
invariant(
  runPanelSource.includes("chatRunRoutingKey") && runPanelSource.includes("chatRunDeploymentId"),
  "Chat route timeline must show routing key and deployment id for operator diagnostics.",
);
invariant(
  stylesSource.includes(".chat-run-section.route-failure"),
  "Route failure diagnostics must have a distinct visual state.",
);
invariant(
  employeeRuntimeSource.includes("runtimeModeLabel") && employeeRuntimeSource.includes("runtimeSummaryStatus"),
  "Employee result cards must surface whether the response used live, mock, media, or local runtime.",
);

const enMessages = extractObjectBody(chatMessagesSource, "chatEn");
const zhMessages = extractObjectBody(chatZhMessagesSource, "chatZh");
const commonEnMessages = extractObjectBody(commonMessagesSource, "commonEn");
const commonZhMessages = extractObjectBody(commonZhMessagesSource, "commonZh");
const requiredMessageKeys = [
  "chatRunDeploymentId",
  "chatRunRouteFailure",
  "chatRunRouteFailureDetail",
  "chatRunRouteFailureUnknown",
  "chatRunRoutingKey",
];

for (const key of requiredMessageKeys) {
  invariant(hasMessageKey(enMessages, key), `Missing English chat evidence i18n key: ${key}`);
  invariant(hasMessageKey(zhMessages, key), `Missing Chinese chat evidence i18n key: ${key}`);
}

const requiredRuntimeModeKeys = [
  "digitalEmployeesRuntimeRealModelCall",
  "digitalEmployeesRuntimeMockModelCall",
  "digitalEmployeesRuntimeMediaGateway",
  "digitalEmployeesRuntimeLocalRuntime",
];

for (const key of requiredRuntimeModeKeys) {
  invariant(hasMessageKey(commonEnMessages, key), `Missing English employee runtime i18n key: ${key}`);
  invariant(hasMessageKey(commonZhMessages, key), `Missing Chinese employee runtime i18n key: ${key}`);
}

console.log("Chat run evidence verification passed.");

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
