export function decimalToNumber(value: string | number | null | undefined) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

export type SupportedLocale = "zh-CN" | "en-US";

export function resolveFormatterLocale(locale?: string | null): SupportedLocale {
  const requested = locale || (typeof document !== "undefined" ? document.documentElement.lang : "");
  return requested.toLowerCase().startsWith("en") ? "en-US" : "zh-CN";
}

export function formatNumber(
  value: string | number | null | undefined,
  options: Intl.NumberFormatOptions = {},
  locale?: string,
) {
  return new Intl.NumberFormat(resolveFormatterLocale(locale), options).format(decimalToNumber(value));
}

export function formatCurrency(value: string | number | null | undefined, currency = "USD", locale?: string) {
  return new Intl.NumberFormat(resolveFormatterLocale(locale), {
    currency,
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
    style: "currency",
  }).format(decimalToNumber(value));
}

export function formatCompactCurrency(value: string | number | null | undefined, currency = "USD", locale?: string) {
  return new Intl.NumberFormat(resolveFormatterLocale(locale), {
    currency,
    maximumFractionDigits: 1,
    minimumFractionDigits: 1,
    notation: "compact",
    style: "currency",
  }).format(decimalToNumber(value));
}

export function formatDate(value: string | number | Date, locale?: string) {
  return new Intl.DateTimeFormat(resolveFormatterLocale(locale), {
    day: "numeric",
    month: resolveFormatterLocale(locale) === "zh-CN" ? "long" : "short",
    year: "numeric",
  }).format(new Date(value));
}

export function formatDateTime(value: string | number | Date, locale?: string) {
  return new Intl.DateTimeFormat(resolveFormatterLocale(locale), {
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    month: resolveFormatterLocale(locale) === "zh-CN" ? "long" : "short",
    second: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

export function budgetUsagePct(spent: string | number, limit: string | number) {
  const limitValue = decimalToNumber(limit);
  if (limitValue <= 0) {
    return 0;
  }
  return Math.min(100, Math.round((decimalToNumber(spent) / limitValue) * 100));
}
