import { Button, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { ChannelCreatePanel } from "./ChannelCreatePanel";
import { ChannelTypeSelector } from "./ChannelTypeSelector";
import { ConnectedChannelList } from "./ConnectedChannelList";
import { type ChannelFormState, getChannelLabel } from "./channelUtils";
import type { ChannelListWorkspaceProps, ChannelsConfigTab, ChannelsCreateStep } from "./channelWorkspaceTypes";

export function ChannelsConfigWorkspace({
  actionError,
  actionMessage,
  agentInstances,
  canWrite,
  channels,
  configTab,
  createStep,
  enabledFeatures,
  error,
  form,
  licenseLoading,
  loading,
  onChannelTypeChange,
  onConfigTabChange,
  onCreate,
  onCreateStepChange,
  onFormChange,
  onRetry,
  onSelect,
  onStatusChange,
  saving,
  selectedChannel,
  selectedTypeLicensed,
  statusUpdatingId,
}: ChannelListWorkspaceProps & {
  actionError: string | null;
  actionMessage: string | null;
  configTab: ChannelsConfigTab;
  createStep: ChannelsCreateStep;
  enabledFeatures: Set<string>;
  form: ChannelFormState;
  licenseLoading: boolean;
  onChannelTypeChange: (channelType: ChannelFormState["channelType"]) => void;
  onConfigTabChange: (tab: ChannelsConfigTab) => void;
  onCreate: () => void;
  onCreateStepChange: (step: ChannelsCreateStep) => void;
  onFormChange: (form: ChannelFormState) => void;
  saving: boolean;
  selectedTypeLicensed: boolean;
}) {
  const { t } = useLocale();

  return (
    <div className="nested-workspace">
      <PageTabs
        active={configTab}
        onChange={onConfigTabChange}
        tabs={[
          {
            id: "create",
            label: t("channelsConfigTabCreate"),
            description: t("channelsConfigTabCreateDesc"),
          },
          {
            id: "connected",
            label: t("channelsConfigTabConnected"),
            description: t("channelsConfigTabConnectedDesc"),
          },
        ]}
      />
      {configTab === "create" && (
        <ChannelCreateWorkspace
          actionError={actionError}
          actionMessage={actionMessage}
          agentInstances={agentInstances}
          canWrite={canWrite}
          createStep={createStep}
          enabledFeatures={enabledFeatures}
          form={form}
          licenseLoading={licenseLoading}
          onChannelTypeChange={onChannelTypeChange}
          onCreate={onCreate}
          onCreateStepChange={onCreateStepChange}
          onFormChange={onFormChange}
          saving={saving}
          selectedTypeLicensed={selectedTypeLicensed}
        />
      )}
      {configTab === "connected" && (
        <ConnectedChannelList
          agentInstances={agentInstances}
          canWrite={canWrite}
          channels={channels}
          error={error}
          loading={loading}
          onRetry={onRetry}
          onSelect={onSelect}
          onStatusChange={onStatusChange}
          selectedChannel={selectedChannel}
          statusUpdatingId={statusUpdatingId}
        />
      )}
    </div>
  );
}

function ChannelCreateWorkspace({
  actionError,
  actionMessage,
  agentInstances,
  canWrite,
  createStep,
  enabledFeatures,
  form,
  licenseLoading,
  onChannelTypeChange,
  onCreate,
  onCreateStepChange,
  onFormChange,
  saving,
  selectedTypeLicensed,
}: {
  actionError: string | null;
  actionMessage: string | null;
  agentInstances: ChannelListWorkspaceProps["agentInstances"];
  canWrite: boolean;
  createStep: ChannelsCreateStep;
  enabledFeatures: Set<string>;
  form: ChannelFormState;
  licenseLoading: boolean;
  onChannelTypeChange: (channelType: ChannelFormState["channelType"]) => void;
  onCreate: () => void;
  onCreateStepChange: (step: ChannelsCreateStep) => void;
  onFormChange: (form: ChannelFormState) => void;
  saving: boolean;
  selectedTypeLicensed: boolean;
}) {
  const { t } = useLocale();

  return (
    <div className="nested-workspace channel-create-workspace">
      <PageTabs
        active={createStep}
        onChange={onCreateStepChange}
        tabs={[
          {
            id: "type",
            label: t("channelsCreateStepType"),
            description: t("channelsCreateStepTypeDesc"),
          },
          {
            id: "binding",
            label: t("channelsCreateStepBinding"),
            description: t("channelsCreateStepBindingDesc"),
          },
        ]}
      />
      {createStep === "type" && (
        <>
          <ChannelTypeSelector
            channelType={form.channelType}
            enabledFeatures={enabledFeatures}
            loading={licenseLoading}
            onChange={onChannelTypeChange}
          />
          <div className="inline-note inline-action-note">
            <span>{t("channelsSelectedTypeReady").replace("{{type}}", getChannelLabel(form.channelType))}</span>
            <Button onClick={() => onCreateStepChange("binding")} disabled={licenseLoading || !selectedTypeLicensed}>
              {t("channelsContinueBinding")}
            </Button>
          </div>
        </>
      )}
      {createStep === "binding" && (
        <ChannelCreatePanel
          actionError={actionError}
          actionMessage={actionMessage}
          agentInstances={agentInstances}
          canWrite={canWrite}
          enabledFeatures={enabledFeatures}
          form={form}
          licenseLoading={licenseLoading}
          onCreate={onCreate}
          onFormChange={onFormChange}
          saving={saving}
        />
      )}
    </div>
  );
}
