import { RotateCcw, Sparkles } from "lucide-react";
import { useState } from "react";
import { Button, ConfirmDialog } from "../../components/app-ui";
import { resetPrototypeState, usePrototypeSnapshot } from "../../hooks/admin/prototypeState";
import { useLocale } from "../../i18n-context";

export function PrototypeDemoPanel() {
  const { t } = useLocale();
  const snapshot = usePrototypeSnapshot();
  const [message, setMessage] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const enabledModules = snapshot.agentModules.filter((module) => module.enabled).length;
  const activeChannels = snapshot.channels.filter((channel) => channel.status === "active").length;
  const indexedDocuments = snapshot.knowledgeDocuments.filter((document) => document.status === "indexed").length;
  const metrics = [
    { label: t("settingsPrototypeModules"), value: `${enabledModules}/${snapshot.agentModules.length}` },
    { label: t("settingsPrototypeAgents"), value: String(snapshot.agentInstances.length) },
    { label: t("settingsPrototypeKnowledgeBases"), value: String(snapshot.knowledgeBases.length) },
    { label: t("settingsPrototypeDocuments"), value: String(indexedDocuments) },
    { label: t("settingsPrototypeChannels"), value: `${activeChannels}/${snapshot.channels.length}` },
  ];

  const confirmResetPrototype = () => {
    setConfirmReset(false);
    resetPrototypeState();
    setMessage(t("settingsPrototypeResetDone"));
  };

  return (
    <section className="panel settings-prototype-panel">
      <div className="settings-support-heading">
        <Sparkles size={18} />
        <div>
          <h3>{t("settingsPrototypeDemoState")}</h3>
          <p>{t("settingsPrototypeDemoHelp")}</p>
        </div>
      </div>
      <div className="settings-prototype-grid">
        {metrics.map((metric) => (
          <span key={metric.label}>
            <strong>{metric.value}</strong>
            {metric.label}
          </span>
        ))}
      </div>
      {message && <div className="form-message">{message}</div>}
      <Button onClick={() => setConfirmReset(true)}>
        <RotateCcw size={16} /> {t("settingsPrototypeReset")}
      </Button>
      <ConfirmDialog
        open={confirmReset}
        title={t("settingsPrototypeReset")}
        message={t("settingsPrototypeResetConfirm")}
        confirmLabel={t("settingsPrototypeReset")}
        cancelLabel={t("commonClose")}
        variant="danger"
        onConfirm={confirmResetPrototype}
        onCancel={() => setConfirmReset(false)}
      />
    </section>
  );
}
