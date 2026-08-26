import { readFileSync } from "node:fs";
import { readStylesSource } from "./read-styles.mjs";

const modelUtilsSource = readFileSync(new URL("../src/pages/models/modelUtils.ts", import.meta.url), "utf8");
const modelControlLoopSource = readFileSync(
  new URL("../src/pages/models/ModelControlLoopPanel.tsx", import.meta.url),
  "utf8",
);
const providerGridSource = readFileSync(new URL("../src/pages/models/ProviderGrid.tsx", import.meta.url), "utf8");
const messagesSource = readFileSync(new URL("../src/i18n/messages/models.ts", import.meta.url), "utf8");
const zhMessagesSource = readFileSync(new URL("../src/i18n/messages/models.zh.ts", import.meta.url), "utf8");
const stylesSource = readStylesSource();

invariant(
  !modelUtilsSource.includes('credential_configured || provider.status === "active"'),
  "Model governance must not treat catalog-active providers as configured credentials.",
);
invariant(
  modelUtilsSource.includes("providerStatusLabelKey"),
  "Provider status labels must be localized instead of hard-coded in model cards.",
);
invariant(
  modelUtilsSource.includes('providerKey === "mimo"') && modelUtilsSource.includes('return "mimo-chat"'),
  "Model governance UI must expose MiMo-specific model defaults instead of generic placeholders.",
);
invariant(
  providerGridSource.includes("providerStatusLabelKey") && providerGridSource.includes("label={statusLabelKey"),
  "Provider grid must render localized provider status labels.",
);
invariant(
  modelControlLoopSource.includes("model-control-loop-workspace") &&
    modelControlLoopSource.includes("model-control-loop-steps") &&
    modelControlLoopSource.includes("model-control-loop-detail"),
  "Model control loop must use a staged workspace instead of a flat card wall.",
);
invariant(
  !modelControlLoopSource.includes("model-control-loop-card") &&
    !modelControlLoopSource.includes("model-control-loop-grid"),
  "Model control loop must not regress to flat card/grid presentation.",
);
invariant(
  stylesSource.includes(".model-control-loop-workspace") &&
    stylesSource.includes(".model-control-loop-step") &&
    stylesSource.includes(".model-control-loop-detail"),
  "Model control loop staged workspace styles are missing.",
);

const requiredMessageKeys = [
  "modelsProviderStatusConfigured",
  "modelsProviderStatusCatalogActive",
  "modelsProviderStatusNotConfigured",
  "modelsLoopReadyCount",
  "modelsLoopReviewCount",
  "modelsLoopBlockedCount",
  "modelsLoopStageTabs",
  "modelsLoopSelectedStage",
  "modelsLoopCurrentMetric",
  "modelsLoopOpenStep",
  "modelsConnectionSummaryAcceptance",
  "modelsOperationDeploymentAcceptance",
  "modelsOperationMediaLiveProbe",
  "modelsOperationMediaConfigCheck",
];
const enMessages = extractObjectBody(messagesSource, "modelsEn");
const zhMessages = extractObjectBody(zhMessagesSource, "modelsZh");

for (const key of requiredMessageKeys) {
  invariant(hasMessageKey(enMessages, key), `Missing English model governance i18n key: ${key}`);
  invariant(hasMessageKey(zhMessages, key), `Missing Chinese model governance i18n key: ${key}`);
}

console.log("Model governance verification passed.");

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
