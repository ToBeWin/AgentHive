import { readFileSync } from "node:fs";
import { readStylesSource } from "./read-styles.mjs";

const componentSource = readFileSync(
  new URL("../src/pages/media/MediaGenerationLoopPanel.tsx", import.meta.url),
  "utf8",
);
const mediaPageSource = readFileSync(new URL("../src/pages/MediaPage.tsx", import.meta.url), "utf8");
const mediaControllerSource = readFileSync(
  new URL("../src/pages/media/useMediaPageController.ts", import.meta.url),
  "utf8",
);
const messagesSource = readFileSync(new URL("../src/i18n/messages/media.ts", import.meta.url), "utf8");
const zhMessagesSource = readFileSync(new URL("../src/i18n/messages/media.zh.ts", import.meta.url), "utf8");
const stylesSource = readStylesSource();

invariant(
  componentSource.includes("media-generation-loop-workspace") &&
    componentSource.includes("media-generation-loop-steps") &&
    componentSource.includes("media-generation-loop-detail"),
  "Media generation loop must use a staged workspace instead of a flat card wall.",
);
invariant(
  !componentSource.includes("media-generation-loop-card") && !componentSource.includes("media-generation-loop-grid"),
  "Media generation loop must not regress to flat card/grid presentation.",
);
invariant(
  stylesSource.includes(".media-generation-loop-workspace") &&
    stylesSource.includes(".media-generation-loop-step") &&
    stylesSource.includes(".media-generation-loop-detail"),
  "Media generation staged workspace styles are missing.",
);
invariant(
  mediaControllerSource.includes('export type MediaNoticeTone = "info" | "error"') &&
    mediaControllerSource.includes("noticeTone") &&
    mediaControllerSource.includes('showNotice(errorMessage(caught), "error")'),
  "Media generation notices must carry explicit tone instead of inferring errors from localized text.",
);
invariant(
  mediaControllerSource.includes("autoEnqueueOnCreate") &&
    mediaControllerSource.includes("mediaApi.enqueueGenerationJob(created.id)") &&
    mediaControllerSource.includes("mediaJobCreatedQueueFailed"),
  "Employee media generation jobs must auto-enqueue after creation and surface queue failures.",
);
invariant(
  mediaPageSource.includes("autoEnqueueOnCreate: isUserWorkspace"),
  "Employee media workspace must submit created generation jobs to the queue automatically.",
);
invariant(
  mediaPageSource.includes('media.noticeTone === "error"') && !mediaPageSource.includes('includes("failed")'),
  "Media page must not infer error styling from English notice text.",
);

const requiredMessageKeys = [
  "mediaLoopReadyCount",
  "mediaLoopReviewCount",
  "mediaLoopBlockedCount",
  "mediaLoopStageTabs",
  "mediaLoopSelectedStage",
  "mediaLoopCurrentMetric",
  "mediaLoopOpenStep",
  "mediaJobCreatedAndEnqueued",
  "mediaJobCreatedQueueFailed",
];
const enMessages = extractObjectBody(messagesSource, "mediaEn");
const zhMessages = extractObjectBody(zhMessagesSource, "mediaZh");

for (const key of requiredMessageKeys) {
  invariant(hasMessageKey(enMessages, key), `Missing English media workflow i18n key: ${key}`);
  invariant(hasMessageKey(zhMessages, key), `Missing Chinese media workflow i18n key: ${key}`);
}

console.log("Media generation workflow verification passed.");

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
