import { useEffect, useMemo, useState } from "react";
import {
  useModelConnectionTests,
  useModelCredentialActions,
  useModelDeployments,
  useModelGovernanceTargets,
  useModelPolicies,
  useModelPolicyActions,
  useModelPriceActions,
  useModelPrices,
  useModelProviders,
  useModelReadiness,
} from "../../hooks/useAdminData";
import { useLocale } from "../../i18n-context";
import type { AuthUser, LLMGovernanceTargetsResponse, LLMPolicyStatus } from "../../lib/api";
import { canAccess } from "../../lib/permissions";
import type {
  ModelCoverageTab,
  ModelCredentialStage,
  ModelDiagnosticsTab,
  ModelGovernanceTab,
} from "./ModelWorkspaces";
import { modelCredentialOwnerOptions, modelPolicyScopeTargetOptions } from "./modelPolicyScopeOptions";
import {
  type CredentialFormState,
  defaultDeploymentNameForProvider,
  defaultModelDisplayNameForProvider,
  defaultModelKeyForProvider,
  defaultModelPolicyForm,
  defaultRoutingKeyForProvider,
  defaultTokenPriceForProvider,
  type ModelPolicyFormState,
  type ModelPriceFormState,
  modelPolicyValidationKey,
  splitPolicyList,
} from "./modelUtils";

export type ModelPageTab = "coverage" | "credentials" | "governance" | "diagnostics";

const EMPTY_GOVERNANCE_TARGETS: LLMGovernanceTargetsResponse = {
  agents: [],
  channels: [],
  cost_centers: [],
  departments: [],
  users: [],
};

const MODEL_TAB_REQUEST_KEY = "agenthive.models.default_tab";

function consumeRequestedModelTab(): ModelPageTab {
  const requested = window.sessionStorage.getItem(MODEL_TAB_REQUEST_KEY);
  if (
    requested === "coverage" ||
    requested === "credentials" ||
    requested === "governance" ||
    requested === "diagnostics"
  ) {
    window.sessionStorage.removeItem(MODEL_TAB_REQUEST_KEY);
    return requested;
  }
  return "coverage";
}

export function useModelsPageController({
  isPrototype = false,
  user = null,
}: {
  isPrototype?: boolean;
  user?: AuthUser | null;
}) {
  const { t } = useLocale();
  const requestedTab = useMemo(consumeRequestedModelTab, []);
  const [activeTab, setActiveTab] = useState<ModelPageTab>(requestedTab);
  const [coverageTab, setCoverageTab] = useState<ModelCoverageTab>("providers");
  const [credentialStage, setCredentialStage] = useState<ModelCredentialStage>("providers");
  const [diagnosticsTab, setDiagnosticsTab] = useState<ModelDiagnosticsTab>("handoff");
  const [governanceTab, setGovernanceTab] = useState<ModelGovernanceTab>("policies");
  const canWriteModels = isPrototype || canAccess(user, ["models:write"]);
  const canWriteGlobalPrices = isPrototype || user?.is_super_admin === true;
  const {
    data: modelProviders,
    error: providersError,
    loading: providersLoading,
    refetch: refetchProviders,
  } = useModelProviders({ fallbackOnError: isPrototype });
  const {
    data: modelDeployments,
    error: deploymentsError,
    loading: deploymentsLoading,
    refetch: refetchDeployments,
  } = useModelDeployments({ fallbackOnError: isPrototype });
  const {
    data: modelPolicies,
    error: policiesError,
    loading: policiesLoading,
    refetch: refetchPolicies,
  } = useModelPolicies({ fallbackOnError: isPrototype });
  const {
    data: modelPrices,
    error: pricesError,
    loading: pricesLoading,
    refetch: refetchPrices,
  } = useModelPrices({ fallbackOnError: isPrototype });
  const {
    data: connectionHistory,
    error: connectionHistoryError,
    loading: connectionHistoryLoading,
    refetch: refetchConnectionHistory,
  } = useModelConnectionTests({ fallbackOnError: isPrototype });
  const {
    data: modelReadiness,
    error: modelReadinessError,
    loading: modelReadinessLoading,
    refetch: refetchModelReadiness,
  } = useModelReadiness({ fallbackOnError: isPrototype });
  const { data: governanceTargets, loading: governanceTargetsLoading } = useModelGovernanceTargets({
    fallbackOnError: isPrototype,
  });
  const {
    error: actionError,
    lastAcceptanceResult,
    lastTestResult,
    message: actionMessage,
    runAcceptanceTest,
    saveCredential,
    saving,
    testConnection,
    testing,
  } = useModelCredentialActions({ fallbackOnError: isPrototype });
  const {
    error: policyError,
    message: policyMessage,
    savePolicy: saveModelPolicy,
    saving: savingPolicy,
    statusUpdatingPolicyId,
    updatePolicyStatus,
  } = useModelPolicyActions({ fallbackOnError: isPrototype });
  const {
    error: priceError,
    message: priceMessage,
    savePrice,
    saving: savingPrice,
  } = useModelPriceActions({ fallbackOnError: isPrototype });
  const providersList = modelProviders ?? [];
  const deploymentsList = modelDeployments ?? [];
  const policiesList = modelPolicies ?? [];
  const pricesList = modelPrices ?? [];
  const [selectedProviderKey, setSelectedProviderKey] = useState<string | null>(null);
  const [localNotice, setLocalNotice] = useState(() => (requestedTab === "coverage" ? t("modelsCoverageFocused") : ""));
  const selectedProvider = providersList.find((provider) => provider.provider_key === selectedProviderKey) ?? null;
  const selectedDeployment =
    deploymentsList.find(
      (deployment) => deployment.provider_key === selectedProviderKey && deployment.status === "active",
    ) ??
    deploymentsList.find((deployment) => deployment.provider_key === selectedProviderKey) ??
    null;
  const selectedProviderDeployments = deploymentsList.filter(
    (deployment) => deployment.provider_key === selectedProviderKey,
  );
  const [credentialForm, setCredentialForm] = useState<CredentialFormState>({
    apiKey: "",
    baseUrl: "",
    deploymentName: selectedDeployment?.deployment_name ?? "",
    displayName: "Default Provider Credential",
    modelKey: selectedDeployment?.model_key ?? "",
    ownerId: "",
    ownerType: "tenant",
    probePath: "/models",
    routingKey: selectedDeployment?.routing_key ?? "",
  });
  const [policyForm, setPolicyForm] = useState<ModelPolicyFormState>(() => defaultModelPolicyForm());
  const [policyValidationError, setPolicyValidationError] = useState<string | null>(null);
  const updatePolicyForm = (value: Parameters<typeof setPolicyForm>[0]) => {
    setPolicyValidationError(null);
    setPolicyForm(value);
  };
  const [priceForm, setPriceForm] = useState<ModelPriceFormState>({
    currency: "USD",
    displayName: selectedDeployment?.display_name ?? "",
    inputPer1k: "0.001",
    modelKey: selectedDeployment?.model_key ?? "",
    outputPer1k: "0.002",
    providerKey: selectedProviderKey ?? "",
  });

  useEffect(() => {
    if (providersList.length) {
      setSelectedProviderKey((current) => current ?? providersList[0].provider_key);
    }
  }, [providersList]);

  useEffect(() => {
    if (!selectedProvider) {
      return;
    }
    const defaultDeploymentName = defaultDeploymentNameForProvider(
      selectedProvider.provider_key,
      selectedProvider.name,
    );
    setCredentialForm({
      apiKey: "",
      baseUrl: selectedProvider.base_url ?? "",
      deploymentName: selectedDeployment?.deployment_name ?? defaultDeploymentName,
      displayName: `${selectedProvider.name} Default Key`,
      modelKey: selectedDeployment?.model_key ?? defaultModelKeyForProvider(selectedProvider.provider_key),
      ownerId: "",
      ownerType: "tenant",
      probePath: "/models",
      routingKey: selectedDeployment?.routing_key ?? defaultRoutingKeyForProvider(selectedProvider.provider_key),
    });
  }, [selectedProvider, selectedDeployment]);

  useEffect(() => {
    if (!selectedProvider) {
      return;
    }
    const defaultPrice = defaultTokenPriceForProvider(selectedProvider.provider_key);
    setPriceForm((current) => ({
      ...current,
      displayName:
        selectedDeployment?.display_name ?? defaultModelDisplayNameForProvider(selectedProvider.provider_key),
      inputPer1k: defaultPrice.inputPer1k,
      modelKey: selectedDeployment?.model_key ?? defaultModelKeyForProvider(selectedProvider.provider_key),
      outputPer1k: defaultPrice.outputPer1k,
      providerKey: selectedProvider.provider_key,
    }));
  }, [selectedProvider, selectedDeployment]);

  const connectedCount = providersList.filter(
    (provider) => provider.credential_configured || provider.status === "active",
  ).length;
  const scopeTargetOptions = useMemo(
    () =>
      modelPolicyScopeTargetOptions({
        scopeType: policyForm.scopeType,
        targets: governanceTargets ?? EMPTY_GOVERNANCE_TARGETS,
      }),
    [governanceTargets, policyForm.scopeType],
  );
  const credentialOwnerOptions = useMemo(
    () =>
      modelCredentialOwnerOptions({
        ownerType: credentialForm.ownerType,
        targets: governanceTargets ?? EMPTY_GOVERNANCE_TARGETS,
      }),
    [credentialForm.ownerType, governanceTargets],
  );
  const scopeTargetLoading = policyForm.scopeType !== "tenant" && governanceTargetsLoading;
  const credentialOwnerLoading = credentialForm.ownerType !== "tenant" && governanceTargetsLoading;

  const handleSaveCredential = async () => {
    if (!canWriteModels || !selectedProvider || !credentialForm.apiKey.trim()) {
      return false;
    }
    const saved = await saveCredential(selectedProvider.provider_key, {
      api_key: credentialForm.apiKey.trim(),
      base_url: credentialForm.baseUrl.trim() || null,
      deployment_name:
        credentialForm.deploymentName.trim() ||
        defaultDeploymentNameForProvider(selectedProvider.provider_key, selectedProvider.name),
      display_name: credentialForm.displayName.trim() || `${selectedProvider.name} Default Key`,
      make_default: true,
      model_key: credentialForm.modelKey.trim() || null,
      owner_id: credentialForm.ownerType === "tenant" ? null : credentialForm.ownerId.trim(),
      owner_type: credentialForm.ownerType,
      routing_key: credentialForm.routingKey.trim() || null,
    });
    if (!saved) {
      return false;
    }
    setCredentialForm((current) => ({
      ...current,
      apiKey: "",
      baseUrl: saved.base_url ?? current.baseUrl,
      modelKey: saved.model_key ?? current.modelKey,
      routingKey: saved.routing_key ?? current.routingKey,
    }));
    await refetchProviders();
    await refetchDeployments();
    await refetchModelReadiness();
    return true;
  };

  const handleTestConnection = async (options: { liveCheck?: boolean } = {}) => {
    if (!canWriteModels || !selectedProvider) {
      return false;
    }
    const result = await testConnection({
      adapter_type: selectedProvider.adapter_type,
      api_key: credentialForm.apiKey.trim() || null,
      base_url: credentialForm.baseUrl.trim() || null,
      deployment_id: credentialForm.apiKey.trim() || credentialForm.baseUrl.trim() ? null : selectedDeployment?.id,
      live_check: Boolean(options.liveCheck),
      model_key: credentialForm.modelKey.trim() || (selectedDeployment?.model_key ?? null),
      probe_path: credentialForm.probePath.trim() || "/models",
      provider_key: selectedProvider.provider_key,
      timeout_seconds: 10,
    });
    if (result) {
      await refetchConnectionHistory();
      await refetchModelReadiness();
      return true;
    }
    return false;
  };

  const handleRunAcceptanceTest = async () => {
    if (!canWriteModels || !selectedDeployment) {
      return false;
    }
    const result = await runAcceptanceTest(selectedDeployment.id);
    if (result) {
      await refetchConnectionHistory();
      await refetchModelReadiness();
      return true;
    }
    return false;
  };

  const handleSavePolicy = async () => {
    if (!canWriteModels) {
      return false;
    }
    const validationKey = modelPolicyValidationKey(policyForm, { scopeTargetLoading, scopeTargetOptions });
    if (validationKey) {
      setPolicyValidationError(t(validationKey));
      return false;
    }
    setPolicyValidationError(null);
    const saved = await saveModelPolicy({
      allowed_models: splitPolicyList(policyForm.allowedModels),
      allowed_routing_keys: splitPolicyList(policyForm.allowedRoutingKeys),
      default_model_key: policyForm.defaultModelKey.trim() || null,
      default_routing_key: policyForm.defaultRoutingKey.trim() || null,
      effect: policyForm.effect,
      max_tokens: policyForm.maxTokens.trim() ? Number(policyForm.maxTokens) : null,
      name: policyForm.name.trim() || "Model policy",
      priority: Number(policyForm.priority || 100),
      scope_id: policyForm.scopeType === "tenant" ? null : policyForm.scopeId.trim() || null,
      scope_type: policyForm.scopeType,
      status: policyForm.status,
    });
    if (saved) {
      await refetchPolicies();
      return true;
    }
    return false;
  };

  const handleUpdatePolicyStatus = async (policyId: string, status: LLMPolicyStatus) => {
    if (!canWriteModels) {
      return;
    }
    const updated = await updatePolicyStatus(policyId, status);
    if (updated) {
      await refetchPolicies();
    }
  };

  const handleSavePrice = async () => {
    if (!canWriteGlobalPrices) {
      return false;
    }
    const saved = await savePrice({
      currency: priceForm.currency.trim().toUpperCase() || "USD",
      display_name: priceForm.displayName.trim() || null,
      input_per_1k_tokens: priceForm.inputPer1k.trim(),
      model_key: priceForm.modelKey.trim(),
      output_per_1k_tokens: priceForm.outputPer1k.trim(),
      provider_key: priceForm.providerKey.trim(),
    });
    if (saved) {
      await refetchPrices();
      return true;
    }
    return false;
  };

  const focusEndpointForm = () => {
    setActiveTab("credentials");
    setCredentialStage("credential");
    setSelectedProviderKey("openai_compatible");
    setLocalNotice(t("modelsEndpointFocused"));
    window.setTimeout(() => setLocalNotice(""), 2600);
    window.setTimeout(() => {
      document.getElementById("model-credential-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
      document.querySelector<HTMLInputElement>("#model-credential-panel input")?.focus();
    }, 80);
  };

  return {
    actionError,
    actionMessage,
    activeTab,
    canWriteGlobalPrices,
    canWriteModels,
    connectedCount,
    connectionHistory,
    connectionHistoryError,
    connectionHistoryLoading,
    coverageTab,
    credentialForm,
    credentialOwnerLoading,
    credentialOwnerOptions,
    credentialStage,
    diagnosticsTab,
    deploymentsError,
    deploymentsList,
    deploymentsLoading,
    focusEndpointForm,
    governanceTab,
    handleSaveCredential,
    handleSavePolicy,
    handleSavePrice,
    handleRunAcceptanceTest,
    handleTestConnection,
    handleUpdatePolicyStatus,
    lastTestResult,
    lastAcceptanceResult,
    localNotice,
    modelReadiness,
    modelReadinessError,
    modelReadinessLoading,
    policiesError,
    policiesList,
    policiesLoading,
    policyError: policyValidationError ?? policyError,
    policyForm,
    policyMessage,
    priceError,
    priceForm,
    priceMessage,
    pricesError,
    pricesList,
    pricesLoading,
    providersError,
    providersList,
    providersLoading,
    refetchConnectionHistory,
    refetchDeployments,
    refetchPolicies,
    refetchPrices,
    refetchProviders,
    saving,
    savingPolicy,
    savingPrice,
    scopeTargetLoading,
    scopeTargetOptions,
    selectedDeployment,
    selectedProvider,
    selectedProviderDeployments,
    selectedProviderKey,
    setActiveTab,
    setCoverageTab,
    setCredentialForm,
    setCredentialStage,
    setDiagnosticsTab,
    setGovernanceTab,
    setPolicyForm: updatePolicyForm,
    setPriceForm,
    setSelectedProviderKey,
    statusUpdatingPolicyId,
    testing,
  };
}
