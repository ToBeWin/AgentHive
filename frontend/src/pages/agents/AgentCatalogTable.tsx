import { StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { agentDisplayDescription, agentDisplayName } from "../../lib/agentDisplay";
import type { AgentCatalogEntryResponse } from "../../lib/api";
import { formatLicenseGate } from "./agentUtils";

export function AgentCatalogTable({
  agents,
  onSelect,
  selectedAgentKey,
}: {
  agents: AgentCatalogEntryResponse[];
  onSelect: (agentKey: string) => void;
  selectedAgentKey: string | null;
}) {
  const { locale, t } = useLocale();

  return (
    <section className="panel table-panel">
      <table className="data-table">
        <thead>
          <tr>
            <th>{t("agentsName")}</th>
            <th>{t("agentsModule")}</th>
            <th>{t("agentsCategory")}</th>
            <th>{t("agentsVersion")}</th>
            <th>{t("agentsStatus")}</th>
            <th>{t("agentsLicenseGate")}</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((agent) => (
            <tr
              key={agent.agent_key}
              onClick={() => onSelect(agent.agent_key)}
              className={selectedAgentKey === agent.agent_key ? "selected-row" : ""}
            >
              <td>
                <span className="avatar">{agentDisplayName(agent, locale).charAt(0)}</span>
                <div>
                  <strong>{agentDisplayName(agent, locale)}</strong>
                  <small>{agentDisplayDescription(agent, locale) || agent.agent_key}</small>
                </div>
              </td>
              <td>
                <code>{agent.required_module}</code>
              </td>
              <td>{agent.category}</td>
              <td>{agent.version}</td>
              <td>
                <StatusBadge status={agent.status} />
              </td>
              <td>
                <StatusBadge label={formatLicenseGate(agent, t)} status={formatLicenseGate(agent, t)} />
              </td>
            </tr>
          ))}
          {agents.length === 0 && (
            <tr>
              <td colSpan={6}>{t("agentsEmptyCatalog")}</td>
            </tr>
          )}
        </tbody>
      </table>
      <footer className="table-footer">{t("agentsShowingCatalog").replace("{{count}}", String(agents.length))}</footer>
    </section>
  );
}
