import { Network } from "lucide-react";
import { cx } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import {
  type ChannelFormState,
  channelTypes,
  getChannelDescriptionKey,
  getChannelLabel,
  isChannelTypeLicensed,
} from "./channelUtils";

export function ChannelTypeSelector({
  channelType,
  enabledFeatures,
  loading,
  onChange,
}: {
  channelType: ChannelFormState["channelType"];
  enabledFeatures: Set<string>;
  loading: boolean;
  onChange: (type: ChannelFormState["channelType"]) => void;
}) {
  const { t } = useLocale();

  return (
    <div className="channel-type-grid">
      {channelTypes.map((type) => {
        const licensed = isChannelTypeLicensed(type, enabledFeatures);
        const disabled = loading || !licensed;
        return (
          <button
            className={cx("channel-type-card", channelType === type && "selected", disabled && "locked")}
            disabled={disabled}
            key={type}
            onClick={() => onChange(type)}
            type="button"
          >
            <Network size={22} />
            <strong>{getChannelLabel(type)}</strong>
            <span>
              {loading
                ? t("channelsTypeLicenseLoading")
                : licensed
                  ? t(getChannelDescriptionKey(type))
                  : t("channelsTypeNotLicensed")}
            </span>
          </button>
        );
      })}
    </div>
  );
}
