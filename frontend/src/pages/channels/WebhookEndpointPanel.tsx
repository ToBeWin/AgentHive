import { Copy } from "lucide-react";
import { Button } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { ChannelResponse } from "../../lib/api";

export function WebhookEndpointPanel({
  selectedChannel,
  webhookUrl,
}: {
  selectedChannel: ChannelResponse | null;
  webhookUrl: string;
}) {
  const { t } = useLocale();

  return (
    <section className="panel">
      <h2>{t("channelsWebhookEndpoint")}</h2>
      {selectedChannel ? (
        <div className="webhook-box">
          <div>
            <strong>{selectedChannel.name}</strong>
            <span>
              {selectedChannel.secret_configured ? t("channelsSecretConfigured") : t("channelsNoSigningSecret")}
            </span>
          </div>
          <code>{webhookUrl}</code>
          <Button onClick={() => void navigator.clipboard?.writeText(webhookUrl)}>
            <Copy size={16} /> {t("channelsCopyUrl")}
          </Button>
        </div>
      ) : (
        <div className="budget-empty-state">{t("channelsNoEndpoint")}</div>
      )}
    </section>
  );
}
