import type { ChatMessageResponse } from "../../lib/api";

export function isStreamingAssistantMessage(message: ChatMessageResponse) {
  if (message.role !== "assistant") {
    return false;
  }
  const localState = message.metadata?.local_state;
  return localState === "streaming_response" || localState === "stream_status" || localState === "streaming";
}

export function hasActiveStreamMessage(messages: ChatMessageResponse[]) {
  const last = messages.at(-1);
  return Boolean(last && isStreamingAssistantMessage(last));
}
