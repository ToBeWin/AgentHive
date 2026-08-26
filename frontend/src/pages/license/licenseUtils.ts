import type { Locale } from "../../i18n";
import type { AuthorizedFeature, AuthorizedModule } from "../../lib/api";

export type LicenseScopeSummary = {
  enabledFeatures: number;
  enabledModules: number;
  totalFeatures: number;
  totalModules: number;
};

export function summarizeScope(modules: AuthorizedModule[], features: AuthorizedFeature[]): LicenseScopeSummary {
  return {
    enabledFeatures: features.filter((feature) => feature.enabled).length,
    enabledModules: modules.filter((module) => module.enabled).length,
    totalFeatures: features.length,
    totalModules: modules.length,
  };
}

export function formatDate(value: string | null, locale: Locale, fallback: string) {
  if (!value) {
    return fallback;
  }
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(value));
}

export function shortFingerprint(value: string) {
  if (value.length <= 18) {
    return value;
  }
  return `${value.slice(0, 10)}...${value.slice(-8)}`;
}
