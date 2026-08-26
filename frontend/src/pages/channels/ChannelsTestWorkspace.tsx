import { PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { ChannelProcessingResult, ChannelResponse, InboundMessageResponse } from "../../lib/api";
import { ChannelTestPanel } from "./ChannelTestPanel";
import type { ChannelFormState } from "./channelUtils";
import type { ChannelsTestTab } from "./channelWorkspaceTypes";
import { WebhookEndpointPanel } from "./WebhookEndpointPanel";

export function ChannelsTestWorkspace({
  canWrite,
  form,
  onFormChange,
  onTest,
  onTestTabChange,
  selectedChannel,
  testProcessing,
  testResult,
  testing,
  testTab,
  webhookUrl,
}: {
  canWrite: boolean;
  form: ChannelFormState;
  onFormChange: (form: ChannelFormState) => void;
  onTest: () => void;
  onTestTabChange: (tab: ChannelsTestTab) => void;
  selectedChannel: ChannelResponse | null;
  testProcessing: ChannelProcessingResult | null;
  testResult: InboundMessageResponse | null;
  testing: boolean;
  testTab: ChannelsTestTab;
  webhookUrl: string;
}) {
  const { t } = useLocale();

  return (
    <div className="nested-workspace">
      <PageTabs
        active={testTab}
        onChange={onTestTabChange}
        tabs={[
          {
            id: "endpoint",
            label: t("channelsTestTabEndpoint"),
            description: t("channelsTestTabEndpointDesc"),
          },
          {
            id: "message",
            label: t("channelsTestTabMessage"),
            description: t("channelsTestTabMessageDesc"),
          },
        ]}
      />
      {testTab === "endpoint" && <WebhookEndpointPanel selectedChannel={selectedChannel} webhookUrl={webhookUrl} />}
      {testTab === "message" && (
        <ChannelTestPanel
          canWrite={canWrite}
          form={form}
          onFormChange={onFormChange}
          onTest={onTest}
          selected={Boolean(selectedChannel)}
          testProcessing={testProcessing}
          testResult={testResult}
          testing={testing}
        />
      )}
    </div>
  );
}
