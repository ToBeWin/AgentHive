import { CheckCircle2, CircleDashed, Image, Route, Sparkles } from "lucide-react";
import { Button, cx } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { MediaFormWorkspace } from "./mediaFormTypes";
import type { MediaJobFormState } from "./mediaUtils";

interface MediaCreativeReadinessPanelProps {
  activeModelCount: number;
  activeWorkspace: MediaFormWorkspace;
  canConfigureModelRoute: boolean;
  form: MediaJobFormState;
  onOpenWorkspace: (workspace: MediaFormWorkspace) => void;
  providerHint: string;
  routeReady: boolean;
}

export function MediaCreativeReadinessPanel({
  activeModelCount,
  activeWorkspace,
  canConfigureModelRoute,
  form,
  onOpenWorkspace,
  providerHint,
  routeReady,
}: MediaCreativeReadinessPanelProps) {
  const { t } = useLocale();
  const checks = [
    {
      done: Boolean(form.prompt.trim()),
      icon: Sparkles,
      id: "brief" as const,
      label: t("mediaReadinessBrief"),
      value: form.prompt.trim() ? t("mediaReadinessBriefReady") : t("mediaReadinessBriefMissing"),
    },
    {
      done: Boolean(form.referenceUrl.trim()),
      icon: Image,
      id: "assets" as const,
      label: t("mediaReadinessAssets"),
      value: form.referenceUrl.trim() ? t("mediaReadinessAssetsReady") : t("mediaReadinessAssetsOptional"),
    },
    {
      done: Boolean(form.resolution.trim()) && (form.kind === "image" ? form.imageCount > 0 : form.durationSeconds > 0),
      icon: CircleDashed,
      id: "output" as const,
      label: t("mediaReadinessOutput"),
      value:
        form.kind === "image" ? `${form.imageCount} · ${form.resolution}` : `${form.durationSeconds}s · ${form.fps}fps`,
    },
    {
      done: routeReady,
      icon: Route,
      id: "output" as const,
      label: t(canConfigureModelRoute ? "mediaReadinessRoute" : "mediaReadinessRouteEmployee"),
      value: routeReady
        ? t("mediaReadinessRouteReady").replace("{{count}}", String(activeModelCount))
        : providerHint || t("mediaReadinessRouteMissing"),
    },
  ];

  return (
    <section className="media-readiness-panel" aria-label={t("mediaReadinessTitle")}>
      <div className="media-readiness-heading">
        <div>
          <h3>{t("mediaReadinessTitle")}</h3>
          <p>{t("mediaReadinessSubtitle")}</p>
        </div>
        <strong>
          {checks.filter((check) => check.done).length}/{checks.length}
        </strong>
      </div>
      <div className="media-readiness-list">
        {checks.map((check) => {
          const Icon = check.icon;
          return (
            <button
              className={cx("media-readiness-item", check.done && "done", activeWorkspace === check.id && "selected")}
              key={check.label}
              onClick={() => onOpenWorkspace(check.id)}
              type="button"
            >
              <span>{check.done ? <CheckCircle2 size={16} /> : <Icon size={16} />}</span>
              <div>
                <strong>{check.label}</strong>
                <small>{check.value}</small>
              </div>
            </button>
          );
        })}
      </div>
      <div className="media-readiness-actions">
        <Button onClick={() => onOpenWorkspace("brief")}>{t("mediaReadinessEditBrief")}</Button>
        <Button onClick={() => onOpenWorkspace("output")}>{t("mediaReadinessCheckRoute")}</Button>
      </div>
    </section>
  );
}
