import { MessageSquare, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { ApiNotice, Button, cx, EmptyState, LoadingState, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { agentDisplayName } from "../../lib/agentDisplay";
import type { AgentInstanceResponse, ChannelResponse } from "../../lib/api";
import { getChannelLabel, getChannelStatusLabelKey } from "./channelUtils";

export function ChannelListPanel({
  agentInstances,
  canWrite,
  channels,
  error,
  loading,
  onRetry,
  onSelect,
  onStatusChange,
  selectedChannel,
  statusUpdatingId,
}: {
  agentInstances: AgentInstanceResponse[];
  canWrite: boolean;
  channels: ChannelResponse[];
  error: string | null;
  loading: boolean;
  onRetry: () => void;
  onSelect: (channelId: string) => void;
  onStatusChange: (channel: ChannelResponse) => void;
  selectedChannel: ChannelResponse | null;
  statusUpdatingId: string | null;
}) {
  const { locale, t } = useLocale();
  const agentInstanceById = new Map(agentInstances.map((instance) => [instance.id, instance]));
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "disabled" | "attention">("all");
  const filteredChannels = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return channels.filter((channel) => {
      const matchesQuery = [channel.name, channel.channel_key, channel.channel_type, channel.webhook_path]
        .join(" ")
        .toLocaleLowerCase()
        .includes(normalizedQuery);
      const matchesStatus =
        statusFilter === "all" ||
        channel.status === statusFilter ||
        (statusFilter === "attention" && (channel.status === "error" || channel.status === "testing"));
      return matchesQuery && matchesStatus;
    });
  }, [channels, query, statusFilter]);

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>{t("channelsConnected")}</h2>
        <span>
          {channels.length} {t("channelsConfigured")}
        </span>
      </div>
      {error && (
        <ApiNotice
          title={t("channelsApiUnavailable")}
          message={error}
          action={<Button onClick={onRetry}>{t("commonRetry")}</Button>}
        />
      )}
      <div className="collection-toolbar channel-table-toolbar">
        <label className="collection-search">
          <Search size={16} aria-hidden="true" />
          <span className="visually-hidden">{t("channelsSearchLabel")}</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("channelsSearchPlaceholder")}
            aria-label={t("channelsSearchLabel")}
          />
          {query && (
            <button
              className="collection-search-clear"
              type="button"
              onClick={() => setQuery("")}
              aria-label={t("commonClearSearch")}
              title={t("commonClearSearch")}
            >
              <X size={14} aria-hidden="true" />
            </button>
          )}
        </label>
        <label className="collection-filter">
          <span>{t("channelsFilterLabel")}</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}>
            <option value="all">{t("channelsFilterAll")}</option>
            <option value="active">{t("channelsFilterActive")}</option>
            <option value="disabled">{t("channelsFilterDisabled")}</option>
            <option value="attention">{t("channelsFilterAttention")}</option>
          </select>
        </label>
        <span className="collection-toolbar-meta">
          {t("channelsResults")
            .replace("{{visible}}", String(filteredChannels.length))
            .replace("{{total}}", String(channels.length))}
        </span>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>{t("channelsName")}</th>
            <th>{t("channelsType")}</th>
            <th>{t("channelsAgentInstance")}</th>
            <th>{t("channelsWebhook")}</th>
            <th>{t("channelsStatus")}</th>
            <th>{t("channelsActions")}</th>
          </tr>
        </thead>
        <tbody>
          {loading && (
            <tr>
              <td colSpan={6}>
                <LoadingState lines={3} />
              </td>
            </tr>
          )}
          {!loading && !channels.length && (
            <tr>
              <td className="table-empty-cell" colSpan={6}>
                <EmptyState
                  icon={<MessageSquare />}
                  title={t("emptyTitleChannels")}
                  message={t("emptyMessageChannels")}
                />
              </td>
            </tr>
          )}
          {!loading && channels.length > 0 && !filteredChannels.length && (
            <tr>
              <td className="table-empty-cell" colSpan={6}>
                <EmptyState icon={<Search />} title={t("channelsNoMatches")} message={t("channelsNoMatchesDetail")} />
              </td>
            </tr>
          )}
          {filteredChannels.map((channel) => (
            <tr
              className={cx(selectedChannel?.id === channel.id && "selected-row")}
              key={channel.id}
              onClick={() => onSelect(channel.id)}
            >
              <td>
                <strong>{channel.name}</strong>
                <span className="row-subtitle">{channel.channel_key}</span>
              </td>
              <td>{getChannelLabel(channel.channel_type)}</td>
              <td>{agentLabel(channel, agentInstanceById, t, locale)}</td>
              <td>
                <code>{channel.webhook_path}</code>
              </td>
              <td>
                <StatusBadge label={t(getChannelStatusLabelKey(channel.status))} status={channel.status} />
              </td>
              <td>
                <Button
                  onClick={(event) => {
                    event.stopPropagation();
                    onStatusChange(channel);
                  }}
                  disabled={!canWrite || statusUpdatingId === channel.id}
                >
                  {statusUpdatingId === channel.id
                    ? t("channelsUpdatingStatus")
                    : channel.status === "active"
                      ? t("channelsDisable")
                      : t("channelsEnable")}
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function agentLabel(
  channel: ChannelResponse,
  agentInstanceById: Map<string, AgentInstanceResponse>,
  t: (key: string) => string,
  locale: "en-US" | "zh-CN",
) {
  if (channel.agent_id) {
    const instance = agentInstanceById.get(channel.agent_id);
    return instance ? agentDisplayName(instance, locale) : channel.agent_id;
  }
  const agentKey = channel.config.agent_key ?? channel.config.default_agent;
  return typeof agentKey === "string" ? agentKey : t("channelsDefaultAgentInstance");
}
