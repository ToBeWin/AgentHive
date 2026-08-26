import type { ChannelProcessingResult, ChannelResponse, ChannelType } from "../../lib/api";

export const channelTypes: ChannelType[] = ["wecom", "dingtalk", "feishu", "web_widget", "rest_api"];

export const channelFeatureKeys: Record<ChannelType, string> = {
  dingtalk: "channel.dingtalk",
  feishu: "channel.feishu",
  rest_api: "channel.rest_api",
  web_widget: "channel.web_widget",
  wecom: "channel.wecom",
};

export type ChannelFormState = {
  channelKey: string;
  channelType: ChannelType;
  configValue: string;
  agentId: string;
  name: string;
  secret: string;
  testText: string;
};

const channelLabels: Record<ChannelType, string> = {
  dingtalk: "DingTalk",
  feishu: "Feishu",
  rest_api: "REST API",
  web_widget: "Web Widget",
  wecom: "WeCom",
};

const channelDescriptionKeys: Record<ChannelType, string> = {
  dingtalk: "channelsDescriptionDingtalk",
  feishu: "channelsDescriptionFeishu",
  rest_api: "channelsDescriptionRestApi",
  web_widget: "channelsDescriptionWebWidget",
  wecom: "channelsDescriptionWecom",
};

const channelStatusKeys: Record<ChannelResponse["status"], string> = {
  active: "channelsStatusActive",
  disabled: "channelsStatusDisabled",
  error: "channelsStatusError",
  testing: "channelsStatusTesting",
};

export function getChannelLabel(type: ChannelType) {
  return channelLabels[type] ?? type;
}

export function isChannelTypeLicensed(type: ChannelType, enabledFeatures: Set<string>) {
  return enabledFeatures.has(channelFeatureKeys[type]);
}

export function getChannelDescriptionKey(type: ChannelType) {
  return channelDescriptionKeys[type];
}

export function getChannelStatusLabelKey(status: ChannelResponse["status"]) {
  return channelStatusKeys[status] ?? "channelsStatus";
}

export function getDefaultChannelDraft(
  type: ChannelType,
): Pick<ChannelFormState, "channelKey" | "channelType" | "name"> {
  return {
    channelKey: type === "web_widget" ? "web-demo" : `${type}-main`,
    channelType: type,
    name: `${getChannelLabel(type)} Channel`,
  };
}

export function formatProcessingMessage(result: ChannelProcessingResult, t: (key: string) => string) {
  if (result.response_text) {
    return t("channelsAgentReplied")
      .replace("{{agent}}", result.agent_key ?? "unknown")
      .replace("{{text}}", result.response_text);
  }

  const base = result.routed ? t("channelsRoutingCompleted") : t("channelsRoutingSkipped");
  return result.error ? `${base} ${result.error}` : base;
}
