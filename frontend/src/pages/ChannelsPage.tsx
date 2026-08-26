import { Megaphone, Plus, SendHorizontal } from "lucide-react";
import { useEffect } from "react";
import { Button, PageHeader, PageTabs } from "../components/app-ui";
import type { WorkspaceId } from "../data";
import { useLocale } from "../i18n-context";
import type { AuthUser } from "../lib/api";
import { showDeliveryDiagnostics } from "../lib/deliveryDiagnostics";
import { ChannelHandoffLoopPanel } from "./channels/ChannelHandoffLoopPanel";
import {
  ChannelsConfigWorkspace,
  ChannelsOverviewWorkspace,
  ChannelsPushWorkspace,
  ChannelsTestWorkspace,
} from "./channels/ChannelWorkspaces";
import { useChannelsPageController } from "./channels/useChannelsPageController";

export function ChannelsPage({
  activeWorkspace = "admin",
  user = null,
  isPrototype = false,
}: {
  activeWorkspace?: WorkspaceId;
  user?: AuthUser | null;
  isPrototype?: boolean;
}) {
  const { t } = useLocale();
  const showDiagnostics = showDeliveryDiagnostics(activeWorkspace);
  const channels = useChannelsPageController({ user, isPrototype });

  useEffect(() => {
    if (!showDiagnostics && channels.activeTab === "overview") {
      channels.setActiveTab("config");
    }
  }, [channels.activeTab, channels.setActiveTab, showDiagnostics]);
  const openChannelReadiness = () => {
    channels.setActiveTab("overview");
    channels.setOverviewTab("readiness");
  };
  const openChannelConfig = () => {
    channels.setActiveTab("config");
    channels.setConfigTab(channels.channelList.length ? "connected" : "create");
    channels.setCreateStep(channels.channelList.length ? "binding" : "type");
  };
  const openChannelRouteReview = () => {
    channels.setActiveTab("config");
    channels.setConfigTab(channels.channelList.length ? "connected" : "create");
    channels.setCreateStep("binding");
  };
  const openChannelTest = () => {
    channels.setActiveTab("test");
    channels.setTestTab(channels.selectedChannel ? "message" : "endpoint");
  };
  const openChannelPush = () => {
    channels.setActiveTab("push");
  };

  return (
    <section className="page">
      <PageHeader
        title={t("channelsTitle")}
        subtitle={t("channelsSubtitle")}
        actions={
          <>
            <Button
              onClick={channels.handlePrimaryTestAction}
              disabled={
                !channels.canWriteChannels ||
                (channels.activeTab === "test" && (!channels.selectedChannel || channels.testing))
              }
            >
              <SendHorizontal size={16} /> {channels.testing ? t("channelsTesting") : t("channelsTest")}
            </Button>
            <Button
              onClick={openChannelPush}
              disabled={
                !channels.canWriteChannels ||
                (channels.activeTab === "push" && (!channels.selectedChannel || channels.pushing))
              }
            >
              <Megaphone size={16} /> {channels.pushing ? t("channelsPushSending") : t("channelsPushTitle")}
            </Button>
            <Button
              variant="primary"
              onClick={channels.handlePrimaryCreateAction}
              disabled={
                !channels.canWriteChannels ||
                (channels.activeTab === "config" &&
                  (channels.saving || channels.licenseScopeLoading || !channels.selectedTypeLicensed))
              }
            >
              <Plus size={16} /> {channels.saving ? t("channelsCreating") : t("channelsCreate")}
            </Button>
          </>
        }
      />
      {showDiagnostics ? (
        <ChannelHandoffLoopPanel
          activeTab={channels.activeTab}
          agentInstances={channels.agentInstances}
          channels={channels.channelList}
          enabledFeatures={channels.enabledChannelFeatures}
          licenseLoading={channels.licenseScopeLoading}
          onOpenConfig={openChannelConfig}
          onOpenReadiness={openChannelReadiness}
          onOpenRouteReview={openChannelRouteReview}
          onOpenTest={openChannelTest}
          selectedChannel={channels.selectedChannel}
          testProcessing={channels.testProcessing}
        />
      ) : null}
      <PageTabs
        active={channels.activeTab}
        onChange={channels.setActiveTab}
        tabs={[
          ...(showDiagnostics
            ? [{ id: "overview" as const, label: t("channelsTabOverview"), description: t("channelsTabOverviewDesc") }]
            : []),
          { id: "config", label: t("channelsTabConfig"), description: t("channelsTabConfigDesc") },
          { id: "test", label: t("channelsTabTest"), description: t("channelsTabTestDesc") },
          { id: "push", label: t("channelsPushTitle"), description: t("channelsPushSubtitle") },
        ]}
      />
      {channels.activeTab === "overview" && (
        <ChannelsOverviewWorkspace
          agentInstances={channels.agentInstances}
          canWrite={channels.canWriteChannels}
          channels={channels.channelList}
          enabledFeatures={channels.enabledChannelFeatures}
          error={channels.channelsError}
          licenseLoading={channels.licenseScopeLoading}
          loading={channels.channelsLoading}
          onOpenConfig={openChannelConfig}
          onOpenReadiness={openChannelReadiness}
          onOpenRouteReview={openChannelRouteReview}
          onOpenTest={openChannelTest}
          onOverviewTabChange={channels.setOverviewTab}
          onRetry={channels.refetchChannels}
          onSelect={channels.setSelectedChannelId}
          onStatusChange={channels.handleChannelStatusChange}
          overviewTab={channels.overviewTab}
          selectedChannel={channels.selectedChannel}
          statusUpdatingId={channels.statusUpdatingId}
          testProcessing={channels.testProcessing}
        />
      )}
      {channels.activeTab === "config" && (
        <ChannelsConfigWorkspace
          actionError={channels.actionError}
          actionMessage={channels.actionMessage}
          agentInstances={channels.agentInstances}
          canWrite={channels.canWriteChannels}
          channels={channels.channelList}
          configTab={channels.configTab}
          createStep={channels.createStep}
          enabledFeatures={channels.enabledChannelFeatures}
          error={channels.channelsError}
          form={channels.form}
          licenseLoading={channels.licenseScopeLoading}
          loading={channels.channelsLoading}
          onChannelTypeChange={channels.handleChannelTypeChange}
          onConfigTabChange={channels.setConfigTab}
          onCreate={channels.handleCreateChannel}
          onCreateStepChange={channels.setCreateStep}
          onFormChange={channels.setForm}
          onRetry={channels.refetchChannels}
          onSelect={channels.setSelectedChannelId}
          onStatusChange={channels.handleChannelStatusChange}
          saving={channels.saving}
          selectedChannel={channels.selectedChannel}
          selectedTypeLicensed={channels.selectedTypeLicensed}
          statusUpdatingId={channels.statusUpdatingId}
        />
      )}
      {channels.activeTab === "test" && (
        <ChannelsTestWorkspace
          canWrite={channels.canWriteChannels}
          form={channels.form}
          onFormChange={channels.setForm}
          onTest={channels.handleTestChannel}
          onTestTabChange={channels.setTestTab}
          selectedChannel={channels.selectedChannel}
          testProcessing={channels.testProcessing}
          testResult={channels.testResult}
          testing={channels.testing}
          testTab={channels.testTab}
          webhookUrl={channels.webhookUrl}
        />
      )}
      {channels.activeTab === "push" && (
        <ChannelsPushWorkspace
          canWrite={channels.canWriteChannels}
          form={channels.pushForm}
          onFormChange={channels.setPushForm}
          onPush={channels.handlePushToChannel}
          pushResult={channels.pushResult}
          pushing={channels.pushing}
          selectedChannel={channels.selectedChannel}
        />
      )}
    </section>
  );
}
