import { useState } from "react";
import { Button, cx } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { UserResponse } from "../../lib/api";

export function UserPasswordResetRow({
  onCancel,
  onSave,
  saving,
  user,
}: {
  onCancel: () => void;
  onSave: (userId: string, password: string) => Promise<boolean>;
  saving: boolean;
  user: UserResponse;
}) {
  const { t } = useLocale();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    const trimmedPassword = password.trim();
    if (trimmedPassword.length < 8) {
      setError(t("departmentsPasswordTooShort"));
      return;
    }
    setError(null);
    const saved = await onSave(user.id, trimmedPassword);
    if (saved) {
      onCancel();
    }
  };

  return (
    <div className="user-password-reset-row">
      <div>
        <strong>{t("departmentsResetPassword")}</strong>
        <span>{t("departmentsResetPasswordInlineHint").replace("{{email}}", user.email)}</span>
      </div>
      <label>
        {t("departmentsNewPassword")}
        <input
          autoComplete="new-password"
          type="password"
          value={password}
          onChange={(event) => {
            setPassword(event.target.value);
            if (error) {
              setError(null);
            }
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              void save();
            }
            if (event.key === "Escape") {
              onCancel();
            }
          }}
        />
      </label>
      {error && <div className={cx("form-message", "error")}>{error}</div>}
      <div className="user-edit-actions">
        <Button onClick={() => void save()} disabled={saving}>
          {saving ? t("departmentsResettingPassword") : t("departmentsSavePassword")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={saving}>
          {t("departmentsCancelUserEdit")}
        </Button>
      </div>
    </div>
  );
}
