import { useLocale } from "../../i18n-context";
import type { ChannelPushMode, ChannelPushResponse, ChannelResponse } from "../../lib/api";
import { type ChannelPushFormState, ChannelPushPanel } from "./ChannelPushPanel";

export function ChannelsPushWorkspace({
  canWrite,
  form,
  onFormChange,
  onPush,
  pushResult,
  pushing,
  selectedChannel,
}: {
  canWrite: boolean;
  form: ChannelPushFormState;
  onFormChange: (form: ChannelPushFormState) => void;
  onPush: (mode: ChannelPushMode) => void;
  pushResult: ChannelPushResponse | null;
  pushing: boolean;
  selectedChannel: ChannelResponse | null;
}) {
  const { t } = useLocale();
  return (
    <div className="nested-workspace">
      <ChannelPushPanel
        canWrite={canWrite}
        form={form}
        onFormChange={onFormChange}
        onPush={onPush}
        pushResult={pushResult}
        pushing={pushing}
        selectedChannel={selectedChannel}
      />
      <p className="panel-subtitle">{t("channelsPushSubtitle")}</p>
    </div>
  );
}
