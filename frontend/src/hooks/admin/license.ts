import { useCallback, useEffect, useState } from "react";
import { useLocale } from "../../i18n-context";
import {
  type ActivationRequestResponse,
  type AuthorizedFeature,
  type AuthorizedModule,
  adminApi,
  type LicenseActivationResponse,
  type LicenseDeactivateResponse,
  type LicenseStatusResponse,
} from "../../lib/api";
import { type AsyncState, errorToMessage, withRetry } from "./shared";

export function useLicenseStatus(options: { fallbackOnError?: boolean } = {}) {
  const fallbackOnError = options.fallbackOnError === true;
  const [state, setState] = useState<AsyncState<LicenseStatusResponse>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      setState({ data: PROTOTYPE_LICENSE_STATUS, error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getLicenseStatus());
      setState({ data, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useLicenseModules(options: { fallbackOnError?: boolean } = {}) {
  const fallbackOnError = options.fallbackOnError === true;
  const [state, setState] = useState<AsyncState<{ modules: AuthorizedModule[]; features: AuthorizedFeature[] }>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      setState({ data: PROTOTYPE_LICENSE_MODULES, error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getLicenseModules());
      setState({ data, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useLicenseActivationActions(options: { fallbackOnError?: boolean } = {}) {
  const { t } = useLocale();
  const fallbackOnError = options.fallbackOnError === true;
  const [exporting, setExporting] = useState(false);
  const [activating, setActivating] = useState(false);
  const [deactivating, setDeactivating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const getActivationRequest = useCallback(async (): Promise<ActivationRequestResponse | null> => {
    setExporting(true);
    setMessage(null);
    setError(null);
    if (fallbackOnError) {
      setExporting(false);
      setMessage(
        t("licenseActivationRequestExported").replace("{{requestId}}", PROTOTYPE_ACTIVATION_REQUEST.request_id),
      );
      return PROTOTYPE_ACTIVATION_REQUEST;
    }
    try {
      const response = await adminApi.getLicenseActivationRequest();
      setMessage(t("licenseActivationRequestExported").replace("{{requestId}}", response.request_id));
      return response;
    } catch (caught) {
      setError(errorToMessage(caught));
      return null;
    } finally {
      setExporting(false);
    }
  }, [fallbackOnError, t]);

  const activateLicense = useCallback(
    async (licenseKey: string): Promise<LicenseActivationResponse | null> => {
      setActivating(true);
      setMessage(null);
      setError(null);
      if (fallbackOnError) {
        setActivating(false);
        const response = {
          license: PROTOTYPE_LICENSE_STATUS,
          message: t("licensePrototypeActivated"),
          status: "active" as const,
          verification: {
            license_id: "00000000-0000-4000-8000-000000009999",
            mode: "offline",
            reason: "prototype_signed_license",
            signature_alg: "Ed25519",
            status: "active" as const,
            valid: true,
          },
        };
        setMessage(response.message);
        return response;
      }
      try {
        const response = await adminApi.activateLicense({ license_key: licenseKey });
        setMessage(response.message || t("licenseActivationStatus").replace("{{status}}", response.status));
        return response;
      } catch (caught) {
        setError(errorToMessage(caught));
        return null;
      } finally {
        setActivating(false);
      }
    },
    [fallbackOnError, t],
  );

  const deactivateLicense = useCallback(async (): Promise<LicenseDeactivateResponse | null> => {
    setDeactivating(true);
    setMessage(null);
    setError(null);
    if (fallbackOnError) {
      setDeactivating(false);
      const response = {
        deactivated_at: new Date().toISOString(),
        message: t("licensePrototypeDeactivated"),
        status: "inactive" as const,
      };
      setMessage(response.message);
      return response;
    }
    try {
      const response = await adminApi.deactivateLicense();
      setMessage(response.message || t("licenseDeactivatedNotice"));
      return response;
    } catch (caught) {
      setError(errorToMessage(caught));
      return null;
    } finally {
      setDeactivating(false);
    }
  }, [fallbackOnError, t]);

  return {
    activateLicense,
    activating,
    deactivateLicense,
    deactivating,
    error,
    exporting,
    getActivationRequest,
    message,
  };
}

const PROTOTYPE_NOW = "2026-01-01T00:00:00.000Z";
const PROTOTYPE_TENANT_ID = "00000000-0000-4000-8000-000000000001";
const PROTOTYPE_DEPLOYMENT_ID = "00000000-0000-4000-8000-000000000501";
const PROTOTYPE_INSTALL_ID = "00000000-0000-4000-8000-000000000502";
const PROTOTYPE_FINGERPRINT = "sha256:88f1e7526a2f8f6314f6a6f7018b8d41dfc4d3b8a1d44b0d0f64f0c6c9a7e1e2";

const PROTOTYPE_LICENSE_STATUS: LicenseStatusResponse = {
  activated_at: PROTOTYPE_NOW,
  allowed_features: [
    "feature.license_offline_activation",
    "feature.model_budget",
    "feature.media_generation",
    "channel.web_widget",
    "channel.wecom",
    "channel.dingtalk",
    "feature.system_diagnostics",
  ],
  allowed_modules: [
    "agent.customer_service",
    "agent.hr_screening",
    "agent.copywriting",
    "agent.image_generation",
    "agent.video_generation",
    "agent.report_writer",
  ],
  customer_name: "AgentHive Demo Customer",
  deployment_id: PROTOTYPE_DEPLOYMENT_ID,
  expires_at: "2027-01-01T00:00:00.000Z",
  feature_count: 7,
  install_id: PROTOTYPE_INSTALL_ID,
  license_type: "enterprise",
  machine_fingerprint_hash: PROTOTYPE_FINGERPRINT,
  maintenance_until: "2026-12-31T00:00:00.000Z",
  max_agents: 50,
  max_kb_size_gb: "500.0",
  max_users: 500,
  module_count: 6,
  runtime_deployment_id: PROTOTYPE_DEPLOYMENT_ID,
  runtime_install_id: PROTOTYPE_INSTALL_ID,
  runtime_machine_fingerprint_hash: PROTOTYPE_FINGERPRINT,
  status: "active",
  verification_issues: [],
};

const PROTOTYPE_LICENSE_MODULES: { modules: AuthorizedModule[]; features: AuthorizedFeature[] } = {
  features: [
    { enabled: true, id: "feature.license_offline_activation", name: "Offline activation" },
    { enabled: true, id: "feature.model_budget", name: "Model budget guard" },
    { enabled: true, id: "feature.media_generation", name: "Media generation" },
    { enabled: true, id: "channel.web_widget", name: "Web Widget channel" },
    { enabled: true, id: "channel.wecom", name: "WeCom channel" },
    { enabled: true, id: "channel.dingtalk", name: "DingTalk channel" },
    { enabled: true, id: "feature.system_diagnostics", name: "Deployment diagnostics" },
  ],
  modules: [
    {
      enabled: true,
      id: "agent.customer_service",
      installed: true,
      licensed: true,
      name: "E-commerce Customer Service Assistant",
      state: "enabled",
    },
    {
      enabled: true,
      id: "agent.hr_screening",
      installed: true,
      licensed: true,
      name: "HR Resume Screening Assistant",
      state: "enabled",
    },
    {
      enabled: false,
      id: "agent.copywriting",
      installed: true,
      licensed: true,
      name: "Copywriting Assistant",
      state: "installed",
    },
    {
      enabled: false,
      id: "agent.image_generation",
      installed: false,
      licensed: true,
      name: "Product Image Generation Assistant",
      state: "not_installed",
    },
    {
      enabled: false,
      id: "agent.video_generation",
      installed: false,
      licensed: true,
      name: "Short Video Generation Assistant",
      state: "not_installed",
    },
    {
      enabled: false,
      id: "agent.finance",
      installed: false,
      licensed: false,
      name: "Finance Efficiency Assistant",
      state: "not_licensed",
    },
  ],
};

const PROTOTYPE_ACTIVATION_REQUEST: ActivationRequestResponse = {
  deployment_id: PROTOTYPE_DEPLOYMENT_ID,
  fingerprint_algorithm: "sha256",
  generated_at: PROTOTYPE_NOW,
  install_id: PROTOTYPE_INSTALL_ID,
  machine_fingerprint_hash: PROTOTYPE_FINGERPRINT,
  product: "AgentHive",
  request_code: "AGENTHIVE-ACTIVATION-REQUEST.demo.eyJwcm9kdWN0IjoiQWdlbnRIaXZlIiwiZGVwbG95bWVudCI6InByb3RvdHlwZSJ9",
  request_format: "agenthive.offline_activation.v1",
  request_hash: "sha256:prototype-activation-request",
  request_id: "proto-activation-20260101",
  tenant_id: PROTOTYPE_TENANT_ID,
};
