import { ChevronDown } from "lucide-react";
import { cx } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { LLMDeploymentResponse } from "../../lib/api";

export function CredentialRoutesPanel({ deploymentsList }: { deploymentsList: LLMDeploymentResponse[] }) {
  const { t } = useLocale();

  return (
    <div className="route-stack">
      <h3>{t("modelsRoutingPreview")}</h3>
      {[...deploymentsList]
        .sort((left, right) => left.priority - right.priority)
        .slice(0, 3)
        .map((route, index) => (
          <div className={cx("route-card", route.status !== "active" && "disabled-route")} key={route.id}>
            <strong>{index + 1}</strong>
            <span>
              {route.display_name} ({route.provider_name})
            </span>
            <ChevronDown size={16} />
          </div>
        ))}
      {!deploymentsList.length && <div className="inline-note">{t("modelsNoRoutes")}</div>}
    </div>
  );
}
