export function runtimePair(providerKey: string, modelKey: string) {
  if (providerKey === "-" && modelKey === "-") {
    return "-";
  }
  if (providerKey === "-") {
    return modelKey;
  }
  if (modelKey === "-") {
    return providerKey;
  }
  return `${providerKey} / ${modelKey}`;
}

export function numericValue(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function formatRuntimeCost(value: string) {
  if (value === "-") {
    return value;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return `$${parsed.toFixed(6)}`;
}
