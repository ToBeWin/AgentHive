import { BadgeDollarSign } from "lucide-react";
import { useState } from "react";
import { ApiNotice, Button, cx, EmptyState, PageTabs, Panel } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { LLMModelPriceResponse } from "../../lib/api";
import { formatDate, formatNumber } from "../../lib/formatters";
import type { ModelPriceFormState } from "./modelUtils";

interface ModelPricesPanelProps {
  canWrite: boolean;
  onSavePrice: () => Promise<boolean>;
  priceError: string | null;
  priceForm: ModelPriceFormState;
  priceMessage: string | null;
  pricesError: string | null;
  pricesList: LLMModelPriceResponse[];
  pricesLoading: boolean;
  refetchPrices: () => void;
  savingPrice: boolean;
  setPriceForm: React.Dispatch<React.SetStateAction<ModelPriceFormState>>;
}

type ModelPriceWorkspaceTab = "list" | "create";

export function ModelPricesPanel({
  canWrite,
  onSavePrice,
  priceError,
  priceForm,
  priceMessage,
  pricesError,
  pricesList,
  pricesLoading,
  refetchPrices,
  savingPrice,
  setPriceForm,
}: ModelPricesPanelProps) {
  const { locale, t } = useLocale();
  const [workspaceTab, setWorkspaceTab] = useState<ModelPriceWorkspaceTab>("list");
  const savePriceAndShowList = async () => {
    const saved = await onSavePrice();
    if (saved) {
      setWorkspaceTab("list");
    }
  };
  return (
    <Panel
      title={t("modelsPrices")}
      subtitle={`${pricesList.length} ${t("modelsPriceOverrides")}`}
      className="model-prices-panel"
    >
      {pricesError && (
        <ApiNotice
          title={t("modelsPriceApiUnavailable")}
          message={pricesError}
          action={<Button onClick={refetchPrices}>{t("commonRetry")}</Button>}
        />
      )}
      {!canWrite && (
        <ApiNotice
          title={t("modelsGlobalPricePermissionRequired")}
          message={t("modelsGlobalPricePermissionRequiredDetail")}
        />
      )}
      {(priceMessage || priceError) && (
        <div className={cx("form-message", priceError ? "error" : false)}>{priceError ?? priceMessage}</div>
      )}
      <PageTabs
        active={workspaceTab}
        onChange={setWorkspaceTab}
        tabs={[
          {
            id: "list",
            label: t("modelsPriceWorkspaceList").replace("{{count}}", String(pricesList.length)),
            description: t("modelsPriceWorkspaceListDesc"),
          },
          {
            id: "create",
            label: t("modelsPriceWorkspaceCreate"),
            description: t("modelsPriceWorkspaceCreateDesc"),
          },
        ]}
      />
      {workspaceTab === "create" && (
        <>
          <div className="policy-form-grid">
            <label>
              {t("modelsProviderKey")}
              <input
                disabled={!canWrite}
                value={priceForm.providerKey}
                onChange={(event) => updatePrice(setPriceForm, "providerKey", event.target.value)}
              />
            </label>
            <label>
              {t("modelsModelKey")}
              <input
                disabled={!canWrite}
                value={priceForm.modelKey}
                onChange={(event) => updatePrice(setPriceForm, "modelKey", event.target.value)}
              />
            </label>
            <label>
              {t("modelsDisplayName")}
              <input
                disabled={!canWrite}
                value={priceForm.displayName}
                onChange={(event) => updatePrice(setPriceForm, "displayName", event.target.value)}
              />
            </label>
            <label>
              {t("modelsCurrency")}
              <input
                disabled={!canWrite}
                value={priceForm.currency}
                onChange={(event) => updatePrice(setPriceForm, "currency", event.target.value.toUpperCase())}
              />
            </label>
            <label>
              {t("modelsInputPer1k")}
              <input
                disabled={!canWrite}
                min="0"
                step="0.000001"
                type="number"
                value={priceForm.inputPer1k}
                onChange={(event) => updatePrice(setPriceForm, "inputPer1k", event.target.value)}
              />
            </label>
            <label>
              {t("modelsOutputPer1k")}
              <input
                disabled={!canWrite}
                min="0"
                step="0.000001"
                type="number"
                value={priceForm.outputPer1k}
                onChange={(event) => updatePrice(setPriceForm, "outputPer1k", event.target.value)}
              />
            </label>
          </div>
          <div className="provider-actions">
            <Button
              onClick={() => void savePriceAndShowList()}
              disabled={
                savingPrice ||
                !canWrite ||
                !priceForm.providerKey.trim() ||
                !priceForm.modelKey.trim() ||
                !priceForm.inputPer1k.trim() ||
                !priceForm.outputPer1k.trim()
              }
            >
              <BadgeDollarSign size={16} /> {savingPrice ? t("modelsSaving") : t("modelsSavePrice")}
            </Button>
          </div>
        </>
      )}
      {workspaceTab === "list" && (
        <div className="table-scroll">
          <table className="data-table compact-table">
            <thead>
              <tr>
                <th>{t("modelsModelName")}</th>
                <th>{t("modelsProviderKey")}</th>
                <th>{t("modelsInputPer1k")}</th>
                <th>{t("modelsOutputPer1k")}</th>
                <th>{t("modelsEffectiveFrom")}</th>
              </tr>
            </thead>
            <tbody>
              {pricesLoading && (
                <tr>
                  <td colSpan={5}>{t("modelsLoadingPrices")}</td>
                </tr>
              )}
              {!pricesLoading && !pricesList.length && (
                <tr>
                  <td className="table-empty-cell" colSpan={5}>
                    <EmptyState
                      icon={<BadgeDollarSign />}
                      title={t("modelsNoPrices")}
                      action={
                        canWrite && (
                          <Button onClick={() => setWorkspaceTab("create")}>{t("modelsPriceWorkspaceCreate")}</Button>
                        )
                      }
                    />
                  </td>
                </tr>
              )}
              {pricesList.slice(0, 8).map((price) => (
                <tr key={price.id}>
                  <td>
                    <code>{price.model_key}</code>
                  </td>
                  <td>{price.provider_key}</td>
                  <td>
                    {price.currency} {formatPrice(price.input_per_1k_tokens, locale)}
                  </td>
                  <td>
                    {price.currency} {formatPrice(price.output_per_1k_tokens, locale)}
                  </td>
                  <td>{formatDate(price.effective_from, locale)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function updatePrice<K extends keyof ModelPriceFormState>(
  setPriceForm: React.Dispatch<React.SetStateAction<ModelPriceFormState>>,
  key: K,
  value: ModelPriceFormState[K],
) {
  setPriceForm((current) => ({ ...current, [key]: value }));
}

function formatPrice(value: string | number, locale: string) {
  return formatNumber(
    value,
    {
      maximumFractionDigits: 8,
      minimumFractionDigits: 0,
    },
    locale,
  );
}
