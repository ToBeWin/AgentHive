import { Megaphone } from "lucide-react";
import { useState } from "react";
import { Button, cx, PageTabs, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { ChannelPushMode, ChannelPushResponse, ChannelResponse } from "../../lib/api";

type PushModeTab = "direct" | "agent";

export interface ChannelPushFormState {
  recipient: string;
  text: string;
  conversationKey: string;
  agentKey: string;
  modelKey: string;
}

export const initialPushForm: ChannelPushFormState = {
  agentKey: "",
  conversationKey: "",
  modelKey: "",
  recipient: "",
  text: "",
};

const VENDOR_API_UNSUPPORTED: ChannelResponse["channel_type"][] = ["web_widget", "rest_api"];

export function ChannelPushPanel({
  canWrite,
  form,
  onFormChange,
  onPush,
  pushing,
  pushResult,
  selectedChannel,
}: {
  canWrite: boolean;
  form: ChannelPushFormState;
  onFormChange: (form: ChannelPushFormState) => void;
  onPush: (mode: ChannelPushMode) => void;
  pushing: boolean;
  pushResult: ChannelPushResponse | null;
  selectedChannel: ChannelResponse | null;
}) {
  const { t } = useLocale();
  const [modeTab, setModeTab] = useState<PushModeTab>("direct");
  const isVendorApiSupported = selectedChannel ? !VENDOR_API_UNSUPPORTED.includes(selectedChannel.channel_type) : true;
  const isActive = selectedChannel?.status === "active";
  const canSend = canWrite && Boolean(selectedChannel) && isActive && isVendorApiSupported && !pushing;
  const mode: ChannelPushMode = modeTab === "agent" ? "agent" : "direct";

  return (
    <section className="panel channel-push-panel">
      <h2>
        <Megaphone size={18} /> {t("channelsPushTitle")}
      </h2>
      <p className="panel-subtitle">{t("channelsPushSubtitle")}</p>
      <PageTabs
        active={modeTab}
        onChange={setModeTab}
        tabs={[
          { id: "direct", label: t("channelsPushTabDirect"), description: t("channelsPushTabDirectDesc") },
          { id: "agent", label: t("channelsPushTabAgent"), description: t("channelsPushTabAgentDesc") },
        ]}
      />
      {!selectedChannel && <div className="form-message info">{t("channelsPushNoChannel")}</div>}
      {selectedChannel && !isActive && <div className="form-message info">{t("channelsPushInactive")}</div>}
      {selectedChannel && isActive && !isVendorApiSupported && (
        <div className="form-message info">{t("channelsPushNotSupported")}</div>
      )}
      <div className="form-grid">
        <label>
          {t("channelsPushRecipient")}
          <input
            disabled={!canSend}
            value={form.recipient}
            placeholder={t("channelsPushRecipientPlaceholder")}
            onChange={(event) => onFormChange({ ...form, recipient: event.target.value })}
          />
          <small className="hint">{t("channelsPushRecipientHelp")}</small>
        </label>
        <label>
          {t("channelsPushConversationKey")}
          <input
            disabled={!canSend}
            value={form.conversationKey}
            placeholder={t("channelsPushConversationKeyPlaceholder")}
            onChange={(event) => onFormChange({ ...form, conversationKey: event.target.value })}
          />
        </label>
        {modeTab === "agent" && (
          <>
            <label>
              {t("channelsPushAgentOverride")}
              <input
                disabled={!canSend}
                value={form.agentKey}
                placeholder={t("channelsPushAgentOverridePlaceholder")}
                onChange={(event) => onFormChange({ ...form, agentKey: event.target.value })}
              />
            </label>
            <label>
              {t("channelsPushModelOverride")}
              <input
                disabled={!canSend}
                value={form.modelKey}
                placeholder={t("channelsPushModelOverridePlaceholder")}
                onChange={(event) => onFormChange({ ...form, modelKey: event.target.value })}
              />
            </label>
          </>
        )}
        <label className="form-grid-full">
          {t("channelsPushText")}
          <textarea
            disabled={!canSend}
            value={form.text}
            placeholder={t("channelsPushTextPlaceholder")}
            rows={4}
            onChange={(event) => onFormChange({ ...form, text: event.target.value })}
          />
        </label>
      </div>
      <div className="provider-actions">
        <Button variant="primary" onClick={() => onPush(mode)} disabled={!canSend || !form.recipient || !form.text}>
          {pushing ? t("channelsPushSending") : t("channelsPushRun")}
        </Button>
      </div>
      {pushResult && <PushResultCard result={pushResult} t={t} />}
    </section>
  );
}

function PushResultCard({ result, t }: { result: ChannelPushResponse; t: (key: string) => string }) {
  const delivery = result.outbound_delivery;
  return (
    <section className="nested-workspace push-result">
      <h3>{t("channelsPushResult")}</h3>
      <div className={cx("form-message", result.delivered ? "success" : "error")}>
        {result.delivered ? t("channelsPushDelivered") : t("channelsPushNotDelivered")}
        {result.error ? ` · ${result.error}` : ""}
      </div>
      <div className="channel-test-metrics">
        <PushMetric label={t("channelsPushMode")} value={result.mode} />
        <PushMetric
          label={t("channelsPushAgentKey")}
          value={result.agent_key ?? "-"}
          status={result.agent_invoked ? "active" : "disabled"}
        />
        <PushMetric
          label={t("channelsPushAgentInvoked")}
          value={result.agent_invoked ? t("channelsPushAgentInvoked") : t("channelsPushAgentSkipped")}
        />
        <PushMetric label={t("channelsPushChannelType")} value={result.channel_type} />
        <PushMetric label={t("channelsPushChannelKey")} value={result.channel_key} />
        <PushMetric label={t("channelsPushConversation")} value={result.conversation_key} />
        <PushMetric label={t("channelsPushRequestId")} value={result.request_id ?? "-"} />
        {delivery && (
          <>
            <PushMetric label={t("channelsPushOutboundMode")} value={delivery.mode} />
            <PushMetric label={t("channelsPushStatusCode")} value={String(delivery.status_code ?? "-")} />
            <PushMetric label={t("channelsPushTarget")} value={delivery.target ?? "-"} />
            {delivery.error && (
              <PushMetric label={t("channelsPushOutboundError")} value={delivery.error} status="error" />
            )}
          </>
        )}
      </div>
      {result.response_text && (
        <div className="push-result-response">
          <strong>{t("channelsPushResponseText")}</strong>
          <p>{result.response_text}</p>
        </div>
      )}
    </section>
  );
}

function PushMetric({ label, status, value }: { label: string; status?: string; value: string }) {
  return (
    <article className="channel-test-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {status && <StatusBadge status={status} />}
    </article>
  );
}
