import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { ApiNotice, Button, FieldLabel } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { authApi, type LoginRequest, saveAuthToken } from "../../lib/api";
import { AuthShell } from "./AuthShell";
import { localizedAuthError } from "./authErrorUtils";

export function LoginPage({
  error,
  onComplete,
  onPrototype,
}: {
  error: string | null;
  onComplete: () => void;
  onPrototype: () => void;
}) {
  const { t } = useLocale();
  const [form, setForm] = useState<LoginRequest>({
    tenant_slug: "demo",
    email: "admin@example.com",
    password: "",
  });
  const [submitError, setSubmitError] = useState<string | null>(error);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setSubmitError(error ? localizedAuthError(error, t("authSignInFailed"), t) : null);
  }, [error, t]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      const response = await authApi.login(form);
      saveAuthToken(response);
      onComplete();
    } catch (caught) {
      setSubmitError(localizedAuthError(caught, t("authSignInFailed"), t));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell>
      <h2>{t("authSignInTitle")}</h2>
      <p>{t("authSignInSubtitle")}</p>
      {submitError && (
        <ApiNotice
          title={t("authSignInUnavailable")}
          message={submitError}
          action={import.meta.env.DEV ? <Button onClick={onPrototype}>{t("authPrototypeMode")}</Button> : undefined}
        />
      )}
      <form className="auth-form" onSubmit={submit}>
        <div>
          <FieldLabel required htmlFor="login-tenant-slug">
            {t("authTenantSlug")}
          </FieldLabel>
          <input
            id="login-tenant-slug"
            autoComplete="organization-title"
            value={form.tenant_slug}
            onChange={(event) => setForm({ ...form, tenant_slug: event.target.value })}
          />
        </div>
        <div>
          <FieldLabel required htmlFor="login-email">
            {t("authEmail")}
          </FieldLabel>
          <input
            id="login-email"
            autoComplete="email"
            type="email"
            value={form.email}
            onChange={(event) => setForm({ ...form, email: event.target.value })}
          />
        </div>
        <div>
          <FieldLabel required htmlFor="login-password">
            {t("authPassword")}
          </FieldLabel>
          <input
            id="login-password"
            autoComplete="current-password"
            type="password"
            placeholder={import.meta.env.DEV ? "AgentHive123!" : undefined}
            value={form.password}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
          />
        </div>
        <Button type="submit" variant="primary" loading={submitting}>
          {submitting ? t("authSigningIn") : t("authSignIn")}
        </Button>
      </form>
    </AuthShell>
  );
}
