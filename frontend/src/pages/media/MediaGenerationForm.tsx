import { Plus } from "lucide-react";
import { useState } from "react";
import { Button, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { MediaModelCapability } from "../../lib/api";
import { MediaAssetsSection } from "./MediaAssetsSection";
import { MediaBriefSection } from "./MediaBriefSection";
import { MediaCreativeReadinessPanel } from "./MediaCreativeReadinessPanel";
import { MediaOutputSettingsSection } from "./MediaOutputSettingsSection";
import type { MediaFormWorkspace } from "./mediaFormTypes";
import type { MediaJobFormState } from "./mediaUtils";

export function MediaGenerationForm({
  canConfigureModelRoute,
  form,
  models,
  onChange,
  onPlan,
  onSubmit,
  planning,
  saving,
}: {
  canConfigureModelRoute: boolean;
  form: MediaJobFormState;
  models: MediaModelCapability[];
  onChange: (form: MediaJobFormState) => void;
  onPlan: () => void;
  onSubmit: () => void;
  planning: boolean;
  saving: boolean;
}) {
  const { t } = useLocale();
  const [activeWorkspace, setActiveWorkspace] = useState<MediaFormWorkspace>("brief");
  const modelOptions = models.filter((model) => model.kind === form.kind);
  const activeModelOptions = modelOptions.filter((model) => model.status === "active");
  const selectedModel = modelOptions.find((model) => model.model_key === form.modelKey);
  const routeReady = form.modelKey ? selectedModel?.status === "active" : activeModelOptions.length > 0;
  const providerIssues =
    selectedModel?.status === "not_configured"
      ? selectedModel.configuration_issues
      : activeModelOptions.length === 0
        ? Array.from(new Set(modelOptions.flatMap((model) => model.configuration_issues)))
        : [];
  const providerHint = providerIssues.length
    ? t(
        canConfigureModelRoute
          ? form.modelKey
            ? "mediaSelectedProviderMissingConfig"
            : "mediaNoConfiguredProviderForKind"
          : "mediaNoAvailableProviderForKindEmployee",
      ).replace("{{items}}", providerIssues.join(", "))
    : activeModelOptions.length === 0
      ? t(canConfigureModelRoute ? "mediaNoAvailableProviderForKind" : "mediaNoAvailableProviderForKindEmployee")
      : "";
  const createDisabled = saving || !form.prompt.trim() || !routeReady;
  const planDisabled = planning || !form.prompt.trim() || !routeReady;

  return (
    <section className="panel media-form-panel">
      <h2>{t("mediaFormTitle")}</h2>
      <MediaCreativeReadinessPanel
        activeModelCount={activeModelOptions.length}
        activeWorkspace={activeWorkspace}
        canConfigureModelRoute={canConfigureModelRoute}
        form={form}
        onOpenWorkspace={setActiveWorkspace}
        providerHint={providerHint}
        routeReady={Boolean(routeReady)}
      />
      <div className="nested-workspace media-form-workspace">
        <PageTabs
          active={activeWorkspace}
          onChange={setActiveWorkspace}
          tabs={[
            {
              id: "brief",
              label: t("mediaFormTabBrief"),
              description: t(canConfigureModelRoute ? "mediaFormTabBriefDesc" : "mediaFormTabBriefDescEmployee"),
            },
            { id: "assets", label: t("mediaFormTabAssets"), description: t("mediaFormTabAssetsDesc") },
            { id: "output", label: t("mediaFormTabOutput"), description: t("mediaFormTabOutputDesc") },
          ]}
        />
        {activeWorkspace === "brief" && <MediaBriefSection form={form} onChange={onChange} />}
        {activeWorkspace === "assets" && <MediaAssetsSection form={form} onChange={onChange} />}
        {activeWorkspace === "output" && (
          <MediaOutputSettingsSection
            activeModelOptions={activeModelOptions}
            canConfigureModelRoute={canConfigureModelRoute}
            form={form}
            modelOptions={modelOptions}
            onChange={onChange}
            providerHint={providerHint}
          />
        )}
      </div>
      {providerHint && activeWorkspace !== "output" && <div className="form-message error">{providerHint}</div>}
      <div className="media-form-actions">
        <Button onClick={onPlan} disabled={planDisabled}>
          {planning ? t("mediaPlanningJob") : t("mediaPreviewPlan")}
        </Button>
        <Button variant="primary" onClick={onSubmit} disabled={createDisabled}>
          <Plus size={16} /> {saving ? t("mediaCreatingJob") : t("mediaCreateJob")}
        </Button>
      </div>
    </section>
  );
}
