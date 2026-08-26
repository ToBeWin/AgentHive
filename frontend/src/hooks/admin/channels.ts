import { useCallback, useEffect, useState } from "react";
import { useToast } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import {
  adminApi,
  type ChannelCreateRequest,
  type ChannelPushRequest,
  type ChannelPushResponse,
  type ChannelResponse,
  type ChannelStatus,
  type ChannelTestRequest,
} from "../../lib/api";
import { prototypeChannelPush, prototypeChannelTest } from "./prototypeData";
import {
  createPrototypeChannel,
  getPrototypeSnapshot,
  updatePrototypeChannelStatus,
  usePrototypeSnapshot,
} from "./prototypeState";
import { type AsyncState, errorToMessage, withRetry } from "./shared";

export function useChannels(options: { fallbackOnError?: boolean } = {}) {
  const fallbackOnError = options.fallbackOnError === true;
  const prototypeSnapshot = usePrototypeSnapshot();
  const [state, setState] = useState<AsyncState<ChannelResponse[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      setState({ data: getPrototypeSnapshot().channels, error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getChannels());
      setState({ data: data.channels, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  if (fallbackOnError) {
    return { data: prototypeSnapshot.channels, error: null, loading: false, refetch: load };
  }

  return { ...state, refetch: load };
}

export function useChannelActions(options: { fallbackOnError?: boolean } = {}) {
  const { t } = useLocale();
  const { showToast } = useToast();
  const fallbackOnError = options.fallbackOnError === true;
  const [saving, setSaving] = useState(false);
  const [statusUpdatingId, setStatusUpdatingId] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const createChannel = useCallback(
    async (payload: ChannelCreateRequest) => {
      setSaving(true);
      setMessage(null);
      setError(null);
      if (fallbackOnError) {
        const response = createPrototypeChannel(payload);
        setSaving(false);
        const successMessage = t("channelsCreated").replace("{{name}}", response.channel.name);
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      }
      try {
        const response = await adminApi.createChannel(payload);
        const successMessage = t("channelsCreated").replace("{{name}}", response.channel.name);
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setSaving(false);
      }
    },
    [fallbackOnError, showToast, t],
  );

  const testChannel = useCallback(
    async (channelId: string, payload: ChannelTestRequest) => {
      setTesting(true);
      setMessage(null);
      setError(null);
      if (fallbackOnError) {
        const response = prototypeChannelTest(channelId, payload);
        setTesting(false);
        const successMessage = response.message;
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      }
      try {
        const response = await adminApi.testChannel(channelId, payload);
        const successMessage = response.message;
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setTesting(false);
      }
    },
    [fallbackOnError, showToast],
  );

  const updateChannelStatus = useCallback(
    async (channelId: string, status: ChannelStatus) => {
      setStatusUpdatingId(channelId);
      setMessage(null);
      setError(null);
      if (fallbackOnError) {
        const response = updatePrototypeChannelStatus(channelId, status);
        setStatusUpdatingId(null);
        const successMessage = response.status === "active" ? t("channelsEnabled") : t("channelsDisabled");
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      }
      try {
        const response = await adminApi.updateChannelStatus(channelId, { status });
        const successMessage = response.status === "active" ? t("channelsEnabled") : t("channelsDisabled");
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setStatusUpdatingId(null);
      }
    },
    [fallbackOnError, showToast, t],
  );

  const pushToChannel = useCallback(
    async (channelId: string, payload: ChannelPushRequest): Promise<ChannelPushResponse | null> => {
      setPushing(true);
      setMessage(null);
      setError(null);
      if (fallbackOnError) {
        const response = prototypeChannelPush(channelId, payload);
        setPushing(false);
        const successMessage = response.message;
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      }
      try {
        const response = await adminApi.pushToChannel(channelId, payload);
        const successMessage = response.message;
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setPushing(false);
      }
    },
    [fallbackOnError, showToast],
  );

  return {
    createChannel,
    error,
    message,
    pushToChannel,
    pushing,
    saving,
    statusUpdatingId,
    testChannel,
    testing,
    updateChannelStatus,
  };
}
