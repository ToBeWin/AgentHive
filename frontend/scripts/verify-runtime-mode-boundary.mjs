import { readFileSync } from "node:fs";
import { readStylesSource } from "./read-styles.mjs";

const appSource = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
const shellSource = readFileSync(new URL("../src/components/layout/AppShell.tsx", import.meta.url), "utf8");
const runtimeModeSource = readFileSync(new URL("../src/lib/runtimeMode.ts", import.meta.url), "utf8");
const messagesSource = readFileSync(new URL("../src/i18n/messages/common.ts", import.meta.url), "utf8");
const zhMessagesSource = readFileSync(new URL("../src/i18n/messages/common.zh.ts", import.meta.url), "utf8");
const stylesSource = readStylesSource();

invariant(
  runtimeModeSource.includes("agenthive.runtime.prototype_mode") &&
    runtimeModeSource.includes("sessionStorage") &&
    runtimeModeSource.includes("import.meta.env.DEV"),
  "Prototype Mode must be explicit, session-scoped, and unavailable outside dev builds.",
);
invariant(
  appSource.includes("getStoredPrototypeMode() ? \"prototype\" : \"checking\"") &&
    appSource.includes("activatePrototypeMode()") &&
    appSource.includes("clearPrototypeMode()"),
  "App auth state must enter and leave Prototype Mode through the runtime mode boundary.",
);
invariant(
  countMatches(appSource, 'setAuthState("prototype")') === 1,
  "Prototype auth state should only be assigned inside the explicit Prototype Mode handler.",
);
invariant(
  shellSource.includes("runtime-mode-banner") &&
    shellSource.includes("runtimePrototypeTitle") &&
    shellSource.includes("runtimePrototypeExit"),
  "Prototype Mode must be visibly labeled in the authenticated shell.",
);
invariant(stylesSource.includes(".runtime-mode-banner"), "Prototype Mode banner styles are missing.");

const enMessages = extractObjectBody(messagesSource, "commonEn");
const zhMessages = extractObjectBody(zhMessagesSource, "commonZh");
for (const key of ["runtimePrototypeTitle", "runtimePrototypeMessage", "runtimePrototypeExit"]) {
  invariant(hasMessageKey(enMessages, key), `Missing English runtime mode i18n key: ${key}`);
  invariant(hasMessageKey(zhMessages, key), `Missing Chinese runtime mode i18n key: ${key}`);
}

console.log("Runtime mode boundary verification passed.");

function countMatches(source, value) {
  return source.split(value).length - 1;
}

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
