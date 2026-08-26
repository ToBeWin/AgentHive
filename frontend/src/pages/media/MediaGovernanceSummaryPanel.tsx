import { Gauge, ReceiptText, Route, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { useLocale } from "../../i18n-context";
import type { MediaGenerationJobResponse } from "../../lib/api";
import { formatCurrency } from "../../lib/formatters";

export function MediaGovernanceSummaryPanel({ job }: { job: MediaGenerationJobResponse }) {
  const { t } = useLocale();
  const pricing = objectValue(job.metadata.pricing);
  const reservation = objectValue(job.metadata.budget_reservation);
  const releaseReason = terminalReleaseReason(job);
  const currency = stringValue(pricing.currency) || "USD";

  return (
    <article className="media-governance-summary">
      <div className="media-governance-heading">
        <div>
          <span>{t("mediaGovernanceEyebrow")}</span>
          <strong>{t("mediaGovernanceTitle")}</strong>
        </div>
        <p>{t("mediaGovernanceSubtitle")}</p>
      </div>
      <div className="media-governance-grid">
        <GovernanceItem
          icon={<ShieldCheck size={17} />}
          label={t("mediaGovernanceBudget")}
          value={budgetValue(reservation, job.metadata.estimated_cost_usd, currency)}
          detail={budgetDetail(reservation, releaseReason, t)}
        />
        <GovernanceItem
          icon={<ReceiptText size={17} />}
          label={t("mediaGovernancePricing")}
          value={pricingValue(pricing, currency, t)}
          detail={pricingDetail(pricing, t)}
        />
        <GovernanceItem
          icon={<Gauge size={17} />}
          label={t("mediaGovernanceParameters")}
          value={parameterValue(job.normalized_parameters, t)}
          detail={parameterDetail(job.normalized_parameters, t)}
        />
        <GovernanceItem
          icon={<Route size={17} />}
          label={t("mediaGovernanceAssets")}
          value={assetValue(job, t)}
          detail={storageDetail(job.output_storage, t)}
        />
      </div>
    </article>
  );
}

function GovernanceItem({
  detail,
  icon,
  label,
  value,
}: {
  detail: string;
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <section className="media-governance-item">
      <span className="media-governance-icon">{icon}</span>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </section>
  );
}

function budgetValue(reservation: Record<string, unknown>, estimatedCost: unknown, currency: string) {
  const reservedCost = stringOrNumberValue(reservation.estimated_cost_usd) ?? stringOrNumberValue(estimatedCost);
  return reservedCost === null ? "-" : formatCurrency(reservedCost, currency);
}

function budgetDetail(reservation: Record<string, unknown>, releaseReason: string, t: (key: string) => string) {
  const approved = booleanValue(reservation.approved);
  const reason = stringValue(reservation.reason);
  if (releaseReason) {
    return t("mediaGovernanceBudgetReleased").replace("{{reason}}", releaseReason);
  }
  if (approved === true) {
    return reason || t("mediaGovernanceBudgetApproved");
  }
  if (approved === false) {
    return reason || t("mediaGovernanceBudgetDenied");
  }
  return t("mediaGovernanceBudgetEstimated");
}

function pricingValue(pricing: Record<string, unknown>, currency: string, t: (key: string) => string) {
  const unitPrice = stringOrNumberValue(pricing.unit_price_usd);
  if (unitPrice === null) {
    return "-";
  }
  return `${formatCurrency(unitPrice, currency)} / ${priceUnitLabel(stringValue(pricing.unit), t)}`;
}

function pricingDetail(pricing: Record<string, unknown>, t: (key: string) => string) {
  const source = stringValue(pricing.source);
  const note = stringValue(pricing.note);
  return source || note || t("mediaGovernancePricingEstimated");
}

function parameterValue(parameters: Record<string, unknown>, t: (key: string) => string) {
  const resolution = stringValue(parameters.resolution) || "-";
  const aspectRatio = stringValue(parameters.aspect_ratio);
  return aspectRatio ? `${resolution} · ${aspectRatio}` : resolution || t("mediaGovernanceParametersDefault");
}

function parameterDetail(parameters: Record<string, unknown>, t: (key: string) => string) {
  const imageCount = stringOrNumberValue(parameters.image_count);
  const duration = stringOrNumberValue(parameters.duration_seconds);
  const fps = stringOrNumberValue(parameters.fps);
  if (duration !== null || fps !== null) {
    return t("mediaGovernanceVideoParameters")
      .replace("{{duration}}", String(duration ?? "-"))
      .replace("{{fps}}", String(fps ?? "-"));
  }
  if (imageCount !== null) {
    return t("mediaGovernanceImageParameters").replace("{{count}}", String(imageCount));
  }
  return t("mediaGovernanceParametersDefault");
}

function assetValue(job: MediaGenerationJobResponse, t: (key: string) => string) {
  const referenceCount = referenceAssetCount(job);
  return t("mediaGovernanceAssetCounts")
    .replace("{{references}}", String(referenceCount))
    .replace("{{outputs}}", String(job.outputs.length));
}

function storageDetail(storage: Record<string, unknown>, t: (key: string) => string) {
  const driver = stringValue(storage.driver);
  const prefix = stringValue(storage.prefix);
  if (driver || prefix) {
    return [driver, prefix].filter(Boolean).join(" / ");
  }
  return t("mediaStorageEmpty");
}

function referenceAssetCount(job: MediaGenerationJobResponse) {
  const metadataCount = stringOrNumberValue(job.metadata.reference_asset_count);
  if (metadataCount !== null) {
    return Number(metadataCount);
  }
  return job.reference_assets.length;
}

function terminalReleaseReason(job: MediaGenerationJobResponse) {
  if (job.status === "canceled") {
    return "media_generation_canceled";
  }
  if (job.status === "failed") {
    return "media_generation_failed";
  }
  return "";
}

function priceUnitLabel(unit: string, t: (key: string) => string) {
  if (unit === "second") {
    return t("mediaPriceSecond");
  }
  if (unit === "output") {
    return t("mediaPriceOutput");
  }
  return unit || "-";
}

function objectValue(value: unknown) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value : "";
}

function booleanValue(value: unknown) {
  return typeof value === "boolean" ? value : null;
}

function stringOrNumberValue(value: unknown) {
  if (typeof value === "string" || typeof value === "number") {
    return value;
  }
  return null;
}
