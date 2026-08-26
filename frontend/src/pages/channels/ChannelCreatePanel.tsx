import { ApiNotice, Button, cx } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { agentDisplayName } from "../../lib/agentDisplay";
import type { AgentInstanceResponse } from "../../lib/api";
import { type ChannelFormState, channelTypes, getChannelLabel, isChannelTypeLicensed } from "./channelUtils";

export function ChannelCreatePanel({
  actionError,
  actionMessage,
  agentInstances,
  canWrite,
  enabledFeatures,
  form,
  licenseLoading,
  onCreate,
  onFormChange,
  saving,
}: {
  actionError: string | null;
  actionMessage: string | null;
  agentInstances: AgentInstanceResponse[];
  canWrite: boolean;
  enabledFeatures: Set<string>;
  form: ChannelFormState;
  licenseLoading: boolean;
  onCreate: () => void;
  onFormChange: (form: ChannelFormState) => void;
  saving: boolean;
}) {
  const { locale, t } = useLocale();
  const activeAgentInstances = agentInstances.filter((instance) => instance.status === "active");
  const selectedTypeLicensed = isChannelTypeLicensed(form.channelType, enabledFeatures);
  const createDisabled =
    !canWrite || saving || licenseLoading || !selectedTypeLicensed || !form.name.trim() || !form.channelKey.trim();

  return (
    <section className="panel budget-form-panel">
      <h2>{t("channelsCreate")}</h2>
      {!canWrite && (
        <ApiNotice title={t("channelsWritePermissionRequired")} message={t("channelsWritePermissionRequiredDetail")} />
      )}
      <label>
        {t("channelsChannelName")}
        <input
          disabled={!canWrite}
          value={form.name}
          onChange={(event) => onFormChange({ ...form, name: event.target.value })}
        />
      </label>
      <div className="budget-form-grid">
        <label>
          {t("channelsType")}
          <select
            disabled={!canWrite}
            value={form.channelType}
            onChange={(event) =>
              onFormChange({ ...form, channelType: event.target.value as ChannelFormState["channelType"] })
            }
          >
            {channelTypes.map((type) => (
              <option
                disabled={licenseLoading || !isChannelTypeLicensed(type, enabledFeatures)}
                key={type}
                value={type}
              >
                {getChannelLabel(type)}
                {licenseLoading
                  ? ` - ${t("channelsTypeLicenseLoading")}`
                  : isChannelTypeLicensed(type, enabledFeatures)
                    ? ""
                    : ` - ${t("channelsTypeNotLicensed")}`}
              </option>
            ))}
          </select>
          {(licenseLoading || !selectedTypeLicensed) && (
            <span className="field-help">
              {licenseLoading ? t("channelsTypeLicenseLoadingHelp") : t("channelsTypeNotLicensedHelp")}
            </span>
          )}
        </label>
        <label>
          {t("channelsChannelKey")}
          <input
            disabled={!canWrite}
            value={form.channelKey}
            onChange={(event) => onFormChange({ ...form, channelKey: event.target.value })}
          />
        </label>
      </div>
      <label>
        {t("channelsConfigValue")}
        <input
          disabled={!canWrite}
          placeholder={t("channelsConfigValuePlaceholder")}
          value={form.configValue}
          onChange={(event) => onFormChange({ ...form, configValue: event.target.value })}
        />
      </label>
      <label>
        {t("channelsAgentInstance")}
        <select
          disabled={!canWrite}
          value={form.agentId}
          onChange={(event) => onFormChange({ ...form, agentId: event.target.value })}
        >
          <option value="">{t("channelsDefaultAgentInstance")}</option>
          {activeAgentInstances.map((instance) => (
            <option key={instance.id} value={instance.id}>
              {agentDisplayName(instance, locale)} · {instance.agent_key}
            </option>
          ))}
        </select>
        <span className="field-help">{t("channelsAgentInstanceHelp")}</span>
      </label>
      <label>
        {t("channelsSharedSecret")}
        <input
          autoComplete="off"
          disabled={!canWrite}
          placeholder={t("channelsSharedSecretPlaceholder")}
          type="password"
          value={form.secret}
          onChange={(event) => onFormChange({ ...form, secret: event.target.value })}
        />
      </label>
      <Button onClick={onCreate} disabled={createDisabled}>
        {saving ? t("channelsCreating") : t("channelsCreate")}
      </Button>
      {(actionMessage || actionError) && (
        <div className={cx("form-message", actionError ? "error" : false)}>{actionError ?? actionMessage}</div>
      )}
    </section>
  );
}
