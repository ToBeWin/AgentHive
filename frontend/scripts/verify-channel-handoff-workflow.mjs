import { readFileSync } from "node:fs";
import { readStylesSource } from "./read-styles.mjs";

const componentSource = readFileSync(
  new URL("../src/pages/channels/ChannelHandoffLoopPanel.tsx", import.meta.url),
  "utf8",
);
const messagesSource = readFileSync(new URL("../src/i18n/messages/channels.ts", import.meta.url), "utf8");
const zhMessagesSource = readFileSync(new URL("../src/i18n/messages/channels.zh.ts", import.meta.url), "utf8");
const stylesSource = readStylesSource();

invariant(
  componentSource.includes("channel-handoff-loop-workspace") &&
    componentSource.includes("channel-handoff-loop-steps") &&
    componentSource.includes("channel-handoff-loop-detail"),
  "Channel handoff loop must use a staged workspace instead of a flat card wall.",
);
invariant(
  !componentSource.includes("channel-handoff-loop-card") && !componentSource.includes("channel-handoff-loop-grid"),
  "Channel handoff loop must not regress to flat card/grid presentation.",
);
invariant(
  stylesSource.includes(".channel-handoff-loop-workspace") &&
    stylesSource.includes(".channel-handoff-loop-step") &&
    stylesSource.includes(".channel-handoff-loop-detail"),
  "Channel handoff staged workspace styles are missing.",
);

const requiredMessageKeys = [
  "channelsLoopReadyCount",
  "channelsLoopReviewCount",
  "channelsLoopBlockedCount",
  "channelsLoopStageTabs",
  "channelsLoopSelectedStage",
  "channelsLoopCurrentMetric",
  "channelsLoopOpenStep",
];
const enMessages = extractObjectBody(messagesSource, "channelsEn");
const zhMessages = extractObjectBody(zhMessagesSource, "channelsZh");

for (const key of requiredMessageKeys) {
  invariant(hasMessageKey(enMessages, key), `Missing English channel workflow i18n key: ${key}`);
  invariant(hasMessageKey(zhMessages, key), `Missing Chinese channel workflow i18n key: ${key}`);
}

console.log("Channel handoff workflow verification passed.");

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
