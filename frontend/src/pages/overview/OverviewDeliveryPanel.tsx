import { Check } from "lucide-react";
import { PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { OverviewDeliveryTab } from "./overviewAnalysisTypes";

export function OverviewDeliveryPanel({
  deliveryTab,
  onDeliveryTabChange,
  onOpenLicenseScope,
}: {
  deliveryTab: OverviewDeliveryTab;
  onDeliveryTabChange: (tab: OverviewDeliveryTab) => void;
  onOpenLicenseScope: () => void;
}) {
  const { t } = useLocale();

  return (
    <div className="grid one lower">
      <section className="panel overview-delivery-panel">
        <PageTabs
          active={deliveryTab}
          onChange={onDeliveryTabChange}
          tabs={[
            {
              id: "license",
              label: t("overviewDeliveryLicenseTab"),
              description: t("overviewDeliveryLicenseTabDesc"),
            },
            {
              id: "activity",
              label: t("overviewDeliveryActivityTab"),
              description: t("overviewDeliveryActivityTabDesc"),
            },
          ]}
        />
        {deliveryTab === "license" && (
          <div className="overview-delivery-body">
            <h2>
              {t("overviewLicenseStatus")} <span>{t("overviewLicenseStatusAlt")}</span>
            </h2>
            <p>{t("overviewLicenseEdition")}</p>
            <div className="license-mini">
              <Check size={18} /> <strong>{t("overviewLicenseActive")}</strong>
              <code>{t("overviewLicenseExpires")}</code>
            </div>
            <div className="split-line">
              <span>{t("overviewSeats")}</span>
              <button type="button" className="text-button" onClick={onOpenLicenseScope}>
                {t("overviewManage")}
              </button>
            </div>
          </div>
        )}
        {deliveryTab === "activity" && (
          <div className="overview-delivery-body">
            <h3>{t("overviewRecentActivity")}</h3>
            <ul className="activity-list">
              <li>
                <i /> {t("overviewActivityPromptUpdated")} <span>{t("overviewActivityPromptMeta")}</span>
              </li>
              <li>
                <i className="red" /> {t("overviewActivityFallbackTriggered")}{" "}
                <span>{t("overviewActivityFallbackMeta")}</span>
              </li>
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}
