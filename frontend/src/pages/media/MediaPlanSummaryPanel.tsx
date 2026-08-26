import { Route } from "lucide-react";
import { useLocale } from "../../i18n-context";
import type { MediaGenerationPlan } from "../../lib/api";
import { formatCurrency } from "../../lib/formatters";
import { kindLabelKey, modeLabelKey } from "./mediaUtils";

export function MediaPlanSummaryPanel({
  canInspectRoute,
  plan,
}: {
  canInspectRoute: boolean;
  plan: MediaGenerationPlan;
}) {
  const { t } = useLocale();
  const commandInterpretation = commandInterpretationFromPlan(plan);
  const referenceSummary = referenceSummaryFromPlan(plan);

  return (
    <div className="media-plan-grid">
      {canInspectRoute && (
        <PlanMetric label={t("mediaProvider")} value={plan.provider_key} detail={plan.provider_type} />
      )}
      {canInspectRoute && <PlanMetric label={t("mediaModel")} value={plan.model_key} detail={plan.routing_key} />}
      <PlanMetric
        label={t("mediaEstimatedCost")}
        value={formatCurrency(plan.estimated_cost_usd)}
        detail={`${plan.estimated_output_count} ${t(plan.kind === "video" ? "mediaPriceSecond" : "mediaPriceOutput")}`}
      />
      <PlanMetric
        label={t("mediaReferenceAssets")}
        value={String(plan.reference_asset_count)}
        detail={t(modeLabelKey(plan.mode))}
      />
      <PlanMetric label={t("mediaKind")} value={t(kindLabelKey(plan.kind))} detail={t(modeLabelKey(plan.mode))} />
      {commandInterpretation && (
        <div className="media-command-interpretation">
          <strong>{t("mediaCommandInterpretation")}</strong>
          <span>{commandInterpretation.inferredFields.map((field) => t(commandFieldLabelKey(field))).join(" / ")}</span>
          <small>{t("mediaCommandInterpretationDetail")}</small>
        </div>
      )}
      {referenceSummary && (
        <div className="media-command-interpretation">
          <strong>{t(canInspectRoute ? "mediaReferencePolicy" : "mediaReferenceSummary")}</strong>
          <span>
            {referenceSummary.count} · {referenceSummary.locations} · {referenceSummary.kinds}
          </span>
          <small>{t(canInspectRoute ? "mediaReferencePolicyDetail" : "mediaReferenceSummaryDetail")}</small>
        </div>
      )}
      <div className="media-plan-route">
        <Route size={18} />
        <div>
          <strong>{t(canInspectRoute ? "mediaPlanRouteReady" : "mediaPlanCreativeReady")}</strong>
          <p>{t(canInspectRoute ? "mediaPlanRouteReadyDetail" : "mediaPlanCreativeReadyDetail")}</p>
        </div>
      </div>
    </div>
  );
}

function PlanMetric({ detail, label, value }: { detail: string; label: string; value: string }) {
  return (
    <article className="media-plan-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function commandInterpretationFromPlan(plan: MediaGenerationPlan): { inferredFields: string[] } | null {
  const raw = plan.normalized_parameters.command_interpretation;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return null;
  }
  const inferredFields = (raw as { inferred_fields?: unknown }).inferred_fields;
  if (!Array.isArray(inferredFields)) {
    return null;
  }
  const fields = inferredFields.filter((field): field is string => typeof field === "string");
  return fields.length ? { inferredFields: fields } : null;
}

function commandFieldLabelKey(field: string) {
  const labels: Record<string, string> = {
    aspect_ratio: "mediaAspectRatio",
    duration_seconds: "mediaDuration",
    fps: "mediaFps",
    image_count: "mediaImageCount",
    resolution: "mediaResolution",
  };
  return labels[field] ?? "mediaParameters";
}

function referenceSummaryFromPlan(
  plan: MediaGenerationPlan,
): { count: string; kinds: string; locations: string } | null {
  const raw = plan.normalized_parameters.reference_assets;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return null;
  }
  const record = raw as { by_kind?: unknown; count?: unknown; locations?: unknown };
  const count = String(record.count ?? plan.reference_asset_count);
  const kinds = compactRecord(record.by_kind);
  const locations = compactRecord(record.locations);
  if (count === "0") {
    return null;
  }
  return {
    count,
    kinds,
    locations,
  };
}

function compactRecord(value: unknown) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return "-";
  }
  return Object.entries(value as Record<string, unknown>)
    .map(([key, item]) => `${key}:${String(item)}`)
    .join(" / ");
}
