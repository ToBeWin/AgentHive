import { Check, Database, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { cx } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AgentKnowledgeBaseOption } from "./agentInstanceUtils";

interface AgentKnowledgeBindingPickerProps {
  disabled?: boolean;
  help?: string;
  knowledgeBases: AgentKnowledgeBaseOption[];
  label: string;
  onChange: (ids: string[]) => void;
  value: string[];
}

export function AgentKnowledgeBindingPicker({
  disabled = false,
  help,
  knowledgeBases,
  label,
  onChange,
  value,
}: AgentKnowledgeBindingPickerProps) {
  const { t } = useLocale();
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLowerCase();
  const selectedIds = useMemo(() => new Set(value), [value]);
  const selectedBases = value.map(
    (id) => knowledgeBases.find((base) => base.id === id) ?? { id, name: id, rag_engine: "" },
  );
  const visibleBases = knowledgeBases.filter((base) => {
    if (!normalizedQuery) {
      return true;
    }
    return `${base.name} ${base.rag_engine}`.toLowerCase().includes(normalizedQuery);
  });

  const toggle = (id: string) => {
    if (disabled) {
      return;
    }
    if (selectedIds.has(id)) {
      onChange(value.filter((item) => item !== id));
      return;
    }
    onChange([...value, id]);
  };

  return (
    <div className="agent-knowledge-picker">
      <div className="agent-knowledge-picker-head">
        <div>
          <span>{label}</span>
          {help ? <small>{help}</small> : null}
        </div>
        <strong>{t("agentInstancesKnowledgeSelected").replace("{{count}}", String(value.length))}</strong>
      </div>

      <div className="agent-knowledge-search">
        <Search size={15} />
        <input
          disabled={disabled || knowledgeBases.length === 0}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("agentInstancesKnowledgeSearch")}
          value={query}
        />
      </div>

      <div className="agent-knowledge-selected-list">
        {selectedBases.length ? (
          selectedBases.map((base) => (
            <button disabled={disabled} key={base.id} onClick={() => toggle(base.id)} title={base.name} type="button">
              <span>{base.name}</span>
              <X size={13} />
            </button>
          ))
        ) : (
          <span>{t("agentInstancesKnowledgeNoneSelected")}</span>
        )}
      </div>

      <div className="agent-knowledge-option-list">
        {visibleBases.map((base) => {
          const selected = selectedIds.has(base.id);
          return (
            <button
              className={cx(selected && "selected")}
              disabled={disabled}
              key={base.id}
              onClick={() => toggle(base.id)}
              type="button"
            >
              <Database className="agent-knowledge-option-icon" size={16} />
              <span>
                <strong>{base.name}</strong>
                <small>{base.rag_engine || base.id}</small>
              </span>
              {selected ? <Check size={16} /> : null}
            </button>
          );
        })}
        {!visibleBases.length && (
          <div className="agent-knowledge-empty">
            {knowledgeBases.length ? t("agentInstancesKnowledgeNoMatch") : t("agentInstancesKnowledgeNoOptions")}
          </div>
        )}
      </div>
    </div>
  );
}
