import { Compass } from "lucide-react";
import { Button } from "../components/app-ui";
import { useLocale } from "../i18n-context";

export function NotFoundPage({ onGoHome }: { onGoHome?: () => void }) {
  const { t } = useLocale();
  return (
    <div className="not-found-page" role="alert">
      <div className="not-found-content">
        <div className="not-found-icon" aria-hidden="true">
          <Compass size={64} />
        </div>
        <h1 className="not-found-code">404</h1>
        <h2 className="not-found-title">{t("commonNotFoundTitle")}</h2>
        <p className="not-found-message">{t("commonNotFoundMessage")}</p>
        <Button
          variant="primary"
          onClick={() => {
            if (onGoHome) {
              onGoHome();
            } else {
              window.location.href = "/";
            }
          }}
        >
          {t("commonBackHome")}
        </Button>
      </div>
    </div>
  );
}
