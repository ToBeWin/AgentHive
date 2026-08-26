import { readFileSync } from "node:fs";

const profileSource = readFileSync(new URL("../src/pages/digital-employees/agentCategory.ts", import.meta.url), "utf8");
const messagesSource = readFileSync(new URL("../src/i18n/messages/common.ts", import.meta.url), "utf8");
const zhMessagesSource = readFileSync(new URL("../src/i18n/messages/common.zh.ts", import.meta.url), "utf8");
const apiSource = readFileSync(new URL("../src/lib/api/agents.ts", import.meta.url), "utf8");

const requiredAgentKeys = [
  "customer_service",
  "hr_screening",
  "copywriting",
  "image_generation",
  "video_generation",
  "content_analysis",
  "report_writer",
  "product_design",
  "finance",
  "store_operations",
  "data_analyst",
];

for (const agentKey of requiredAgentKeys) {
  invariant(profileSource.includes(`${agentKey}: {`), `Missing explicit workbench profile for ${agentKey}`);
}
invariant(apiSource.includes("category?: string"), "WorkbenchAgentInstanceResponse must include category");
invariant(apiSource.includes("workflow_profile?: string"), "WorkbenchAgentInstanceResponse must include workflow_profile");

const profileObject = extractObjectBody(profileSource, "PROFILE_BY_AGENT_KEY");
const referencedMessageKeys = [
  ...new Set([...profileObject.matchAll(/"((?:agentWorkflow|agentStep|agentInput|agentOutput)[^"]+)"/g)].map((match) => match[1])),
].sort();
const categoryKeys = [
  ...new Set([...profileSource.matchAll(/"(digitalEmployeesCategory[^"]+)"/g)].map((match) => match[1])),
].sort();
const enMessages = extractObjectBody(messagesSource, "commonEn");
const zhMessages = extractObjectBody(zhMessagesSource, "commonZh");

for (const key of [...categoryKeys, ...referencedMessageKeys]) {
  invariant(hasMessageKey(enMessages, key), `Missing English i18n key: ${key}`);
  invariant(hasMessageKey(zhMessages, key), `Missing Chinese i18n key: ${key}`);
}

console.log("Agent workbench profile verification passed.");

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
