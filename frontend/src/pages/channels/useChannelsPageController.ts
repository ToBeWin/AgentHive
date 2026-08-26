import { useCallback, useEffect, useMemo, useState } from "react";
import { useAgentInstances, useChannelActions, useChannels, useLicenseModules } from "../../hooks/useAdminData";
import { useLocale } from "../../i18n-context";
import type {
  AuthUser,
  ChannelProcessingResult,
  ChannelPushMode,
  ChannelPushResponse,
  InboundMessageResponse,
} from "../../lib/api";
import { canAccess } from "../../lib/permissions";
import { type ChannelPushFormState, initialPushForm } from "./ChannelPushPanel";
import type {
  ChannelsConfigTab,
  ChannelsCreateStep,
  ChannelsOverviewTab,
  ChannelsPageTab,
  ChannelsTestTab,
} from "./ChannelWorkspaces";
import {
  type ChannelFormState,
  channelTypes,
  getChannelDescriptionKey,
  getDefaultChannelDraft,
  isChannelTypeLicensed,
} from "./channelUtils";

const initialForm: ChannelFormState = {
  ...getDefaultChannelDraft("web_widget"),
  agentId: "",
  configValue: "*",
  secret: "",
  testText: "hello from AgentHive channel test",
};

export function useChannelsPageController({
  user = null,
  isPrototype = false,
}: {
  user?: AuthUser | null;
  isPrototype?: boolean;
}) {
  const { t } = useLocale();
  const canWriteChannels = isPrototype || canAccess(user, ["channels:write"]);
  const [activeTab, setActiveTab] = useState<ChannelsPageTab>("config");
  const [overviewTab, setOverviewTab] = useState<ChannelsOverviewTab>("connected");
  const [configTab, setConfigTab] = useState<ChannelsConfigTab>("create");
  const [createStep, setCreateStep] = useState<ChannelsCreateStep>("type");
  const [testTab, setTestTab] = useState<ChannelsTestTab>("endpoint");
  const {
    data: channels,
    error: channelsError,
    loading: channelsLoading,
    refetch: refetchChannels,
  } = useChannels({
    fallbackOnError: isPrototype,
  });
  const { data: agentInstances } = useAgentInstances({ fallbackOnError: isPrototype });
  const { data: licenseScope, loading: licenseScopeLoading } = useLicenseModules({ fallbackOnError: isPrototype });
  const {
    createChannel,
    error: actionError,
    message: actionMessage,
    pushToChannel,
    pushing,
    saving,
    statusUpdatingId,
    testChannel,
    testing,
    updateChannelStatus,
  } = useChannelActions({ fallbackOnError: isPrototype });
  const channelList = channels ?? [];
  const [selectedChannelId, setSelectedChannelId] = useState<string | null>(null);
  const selectedChannel = channelList.find((channel) => channel.id === selectedChannelId) ?? channelList[0] ?? null;
  const [testResult, setTestResult] = useState<InboundMessageResponse | null>(null);
  const [testProcessing, setTestProcessing] = useState<ChannelProcessingResult | null>(null);
  const [form, setForm] = useState<ChannelFormState>(initialForm);
  const [pushForm, setPushForm] = useState<ChannelPushFormState>(initialPushForm);
  const [pushResult, setPushResult] = useState<ChannelPushResponse | null>(null);
  const enabledChannelFeatures = useMemo(
    () => new Set((licenseScope?.features ?? []).filter((feature) => feature.enabled).map((feature) => feature.id)),
    [licenseScope],
  );
  const licensedChannelTypes = useMemo(
    () => channelTypes.filter((type) => isChannelTypeLicensed(type, enabledChannelFeatures)),
    [enabledChannelFeatures],
  );
  const selectedTypeLicensed = isChannelTypeLicensed(form.channelType, enabledChannelFeatures);

  const handleChannelTypeChange = useCallback((channelType: ChannelFormState["channelType"]) => {
    setForm((current) => ({
      ...current,
      ...getDefaultChannelDraft(channelType),
      agentId: current.agentId,
    }));
  }, []);

  useEffect(() => {
    if (!channelList.length) {
      setSelectedChannelId(null);
      return;
    }
    setSelectedChannelId((current) => current ?? channelList[0].id);
  }, [channelList]);

  useEffect(() => {
    if (licenseScopeLoading || selectedTypeLicensed || !licensedChannelTypes.length) {
      return;
    }
    handleChannelTypeChange(licensedChannelTypes[0]);
  }, [handleChannelTypeChange, licenseScopeLoading, licensedChannelTypes, selectedTypeLicensed]);

  const handleCreateChannel = async () => {
    if (!canWriteChannels || licenseScopeLoading || !selectedTypeLicensed) {
      return;
    }
    const selectedAgent =
      (agentInstances ?? []).find((instance) => instance.id === form.agentId && instance.status === "active") ?? null;
    const created = await createChannel({
      channel_key: form.channelKey.trim(),
      channel_type: form.channelType,
      agent_id: selectedAgent?.id ?? null,
      config: {
        ...(selectedAgent
          ? {
              agent_key: selectedAgent.agent_key,
              default_agent: selectedAgent.agent_key,
            }
          : {}),
        note: t(getChannelDescriptionKey(form.channelType)),
        value: form.configValue.trim(),
      },
      name: form.name.trim(),
      secret: form.secret.trim() || null,
      status: "active",
    });
    if (created) {
      setSelectedChannelId(created.channel.id);
      setConfigTab("connected");
      await refetchChannels();
    }
  };

  const handlePrimaryCreateAction = () => {
    if (activeTab !== "config") {
      setActiveTab("config");
      setConfigTab("create");
      return;
    }
    if (configTab !== "create") {
      setConfigTab("create");
      return;
    }
    void handleCreateChannel();
  };

  const handleTestChannel = async () => {
    if (!canWriteChannels || !selectedChannel) {
      return;
    }
    const response = await testChannel(selectedChannel.id, {
      conversation_key: `test:${selectedChannel.channel_key}`,
      external_user_id: "agenthive-test-user",
      raw_payload: {
        source: "agenthive-admin",
      },
      text: form.testText,
    });
    if (response) {
      setTestResult(response.normalized_message);
      setTestProcessing(response.processing);
    }
  };

  const handlePushToChannel = async (mode: ChannelPushMode) => {
    if (!canWriteChannels || !selectedChannel) {
      return;
    }
    const response = await pushToChannel(selectedChannel.id, {
      external_user_id: pushForm.recipient.trim(),
      text: pushForm.text,
      mode,
      agent_key: pushForm.agentKey.trim() || null,
      conversation_key: pushForm.conversationKey.trim() || null,
      metadata: { source: "agenthive-admin-ui" },
      model_key: pushForm.modelKey.trim() || null,
    });
    if (response) {
      setPushResult(response);
    }
  };

  const handlePrimaryTestAction = () => {
    if (activeTab !== "test") {
      setActiveTab("test");
      return;
    }
    void handleTestChannel();
  };

  const handleChannelStatusChange = async (channel: (typeof channelList)[number]) => {
    if (!canWriteChannels) {
      return;
    }
    const nextStatus = channel.status === "active" ? "disabled" : "active";
    const updated = await updateChannelStatus(channel.id, nextStatus);
    if (updated) {
      await refetchChannels();
    }
  };

  const webhookOrigin = typeof window === "undefined" ? "" : window.location.origin;
  const webhookUrl = selectedChannel ? `${webhookOrigin}${selectedChannel.webhook_path}` : "";

  return {
    actionError,
    actionMessage,
    activeTab,
    agentInstances: agentInstances ?? [],
    canWriteChannels,
    channelList,
    channelsError,
    channelsLoading,
    configTab,
    createStep,
    enabledChannelFeatures,
    form,
    handleChannelStatusChange,
    handleChannelTypeChange,
    handleCreateChannel,
    handlePrimaryCreateAction,
    handlePrimaryTestAction,
    handlePushToChannel,
    handleTestChannel,
    licenseScopeLoading,
    overviewTab,
    pushForm,
    pushResult,
    pushing,
    refetchChannels,
    saving,
    selectedChannel,
    selectedTypeLicensed,
    setActiveTab,
    setConfigTab,
    setCreateStep,
    setForm,
    setOverviewTab,
    setPushForm,
    setSelectedChannelId,
    setTestTab,
    statusUpdatingId,
    testProcessing,
    testResult,
    testing,
    testTab,
    webhookUrl,
  };
}
