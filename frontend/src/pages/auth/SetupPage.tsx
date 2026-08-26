import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { ApiNotice, Button } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { authApi, type BootstrapRequest, type SetupStatusResponse, saveAuthToken } from "../../lib/api";
import { AuthShell } from "./AuthShell";
import { localizedAuthError } from "./authErrorUtils";
import { SetupPreflightPanel } from "./SetupPreflightPanel";

export function SetupPage({
  error,
  onComplete,
  onPrototype,
  setupStatus,
}: {
  error: string | null;
  onComplete: () => void;
  onPrototype: () => void;
  setupStatus: SetupStatusResponse | null;
}) {
  const { t } = useLocale();
  const [form, setForm] = useState<BootstrapRequest>({
    tenant_name: "AgentHive Demo Company",
    tenant_slug: "demo",
    admin_email: "admin@example.com",
    admin_password: import.meta.env.DEV ? "AgentHive123!" : "",
    admin_full_name: "AgentHive Admin",
  });
  const [submitError, setSubmitError] = useState<string | null>(error);
  const [submitting, setSubmitting] = useState(false);
  const setupCanSubmit = Boolean(setupStatus?.setup_available && !setupStatus.initialized);

  useEffect(() => {
    setSubmitError(error ? localizedAuthError(error, t("authInitializeFailed"), t) : null);
  }, [error, t]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!setupCanSubmit) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const response = await authApi.bootstrap(form);
      saveAuthToken(response.auth);
      onComplete();
    } catch (caught) {
      setSubmitError(localizedAuthError(caught, t("authInitializeFailed"), t));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell>
      <h2>{t("authSetupTitle")}</h2>
      <p>{t("authSetupSubtitle")}</p>
      <SetupPreflightPanel error={submitError} setupStatus={setupStatus} />
      {submitError && (
        <ApiNotice
          title={t("authSetupUnavailable")}
          message={submitError}
          action={import.meta.env.DEV ? <Button onClick={onPrototype}>{t("authPrototypeMode")}</Button> : undefined}
        />
      )}
      <form className="auth-form" onSubmit={submit}>
        <label>
          {t("authCompanyName")}
          <input
            autoComplete="organization"
            value={form.tenant_name}
            onChange={(event) => setForm({ ...form, tenant_name: event.target.value })}
          />
        </label>
        <label>
          {t("authTenantSlug")}
          <input
            autoComplete="organization-title"
            value={form.tenant_slug}
            onChange={(event) => setForm({ ...form, tenant_slug: event.target.value })}
          />
        </label>
        <label>
          {t("authAdminName")}
          <input
            autoComplete="name"
            value={form.admin_full_name}
            onChange={(event) => setForm({ ...form, admin_full_name: event.target.value })}
          />
        </label>
        <label>
          {t("authAdminEmail")}
          <input
            autoComplete="email"
            type="email"
            value={form.admin_email}
            onChange={(event) => setForm({ ...form, admin_email: event.target.value })}
          />
        </label>
        <label>
          {t("authAdminPassword")}
          <input
            autoComplete="new-password"
            type="password"
            value={form.admin_password}
            onChange={(event) => setForm({ ...form, admin_password: event.target.value })}
          />
        </label>
        <Button type="submit" variant="primary" disabled={submitting || !setupCanSubmit}>
          {submitting ? t("authInitializing") : t("authInitialize")}
        </Button>
      </form>
    </AuthShell>
  );
}
