import { Database, Plus } from "lucide-react";
import { useState } from "react";
import { ApiNotice, Button, cx, Drawer, FormField } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { KnowledgeBaseVisibility, RAGEngineType } from "../../lib/api";
import type { KnowledgeBaseFormState } from "./KnowledgeBaseSidebar";

interface KnowledgeBaseCreateDrawerProps {
  actionError: string | null;
  actionMessage: string | null;
  canWrite: boolean;
  departmentOptions: Array<{ id: string; label: string }>;
  form: KnowledgeBaseFormState;
  onClose: () => void;
  onCreateKnowledgeBase: () => Promise<boolean>;
  saving: boolean;
  setForm: React.Dispatch<React.SetStateAction<KnowledgeBaseFormState>>;
}

export function KnowledgeBaseCreateDrawer({
  actionError,
  actionMessage,
  canWrite,
  departmentOptions,
  form,
  onClose,
  onCreateKnowledgeBase,
  saving,
  setForm,
}: KnowledgeBaseCreateDrawerProps) {
  const { t } = useLocale();
  const [nameError, setNameError] = useState<string | null>(null);
  const [departmentError, setDepartmentError] = useState<string | null>(null);
  const createDisabled =
    !canWrite || saving || !form.name.trim() || (form.visibility === "department" && form.departmentIds.length === 0);

  const validateForm = (): boolean => {
    const name = form.name.trim();
    let valid = true;
    if (!name) {
      setNameError(t("knowledgeNameRequired"));
      valid = false;
    } else if (name.length < 2) {
      setNameError(t("knowledgeNameTooShort"));
      valid = false;
    } else {
      setNameError(null);
    }
    if (form.visibility === "department" && form.departmentIds.length === 0) {
      setDepartmentError(t("knowledgeDepartmentRequired"));
      valid = false;
    } else {
      setDepartmentError(null);
    }
    return valid;
  };

  const handleCreate = async () => {
    if (!validateForm()) return;
    await onCreateKnowledgeBase();
  };

  const toggleDepartment = (departmentId: string) => {
    setForm((current) => ({
      ...current,
      departmentIds: current.departmentIds.includes(departmentId)
        ? current.departmentIds.filter((id) => id !== departmentId)
        : [...current.departmentIds, departmentId],
    }));
  };

  return (
    <Drawer
      open={true}
      title={t("knowledgeCreateBase")}
      subtitle={t("knowledgeCreateDrawerDesc")}
      onClose={onClose}
      ariaLabel={t("knowledgeCreateBase")}
      className="knowledge-create-drawer"
      footer={
        <Button variant="primary" onClick={() => void handleCreate()} disabled={createDisabled}>
          <Plus size={16} /> {saving ? t("knowledgeCreating") : t("knowledgeCreateBaseButton")}
        </Button>
      }
    >
      <div className="knowledge-create-content">
        {!canWrite && (
          <ApiNotice title={t("knowledgeWritePermissionRequired")} message={t("knowledgeWritePermissionDetail")} />
        )}
        {(actionMessage || actionError) && (
          <div className={cx("form-message", actionError ? "error" : false)}>{actionError ?? actionMessage}</div>
        )}
        <section className="knowledge-create-section">
          <div className="knowledge-create-section-title">
            <Database size={18} />
            <div>
              <strong>{t("knowledgeCreateSectionIdentity")}</strong>
              <span>{t("knowledgeCreateSectionIdentityDesc")}</span>
            </div>
          </div>
          <FormField htmlFor="knowledge-base-name" label={t("knowledgeName")} error={nameError}>
            <input
              id="knowledge-base-name"
              disabled={!canWrite}
              placeholder={t("knowledgeNamePlaceholder")}
              value={form.name}
              onChange={(event) => {
                setForm((current) => ({ ...current, name: event.target.value }));
                if (nameError) setNameError(null);
              }}
              className={cx(nameError ? "form-input-error" : undefined)}
              aria-invalid={nameError ? true : undefined}
            />
          </FormField>
          <label>
            {t("knowledgeDescription")}
            <textarea
              disabled={!canWrite}
              placeholder={t("knowledgeDescriptionPlaceholder")}
              value={form.description}
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
            />
          </label>
          <label>
            {t("knowledgeTags")}
            <input
              disabled={!canWrite}
              placeholder={t("knowledgeTagsPlaceholder")}
              value={form.tags}
              onChange={(event) => setForm((current) => ({ ...current, tags: event.target.value }))}
            />
          </label>
        </section>

        <section className="knowledge-create-section">
          <div className="knowledge-create-section-title">
            <Database size={18} />
            <div>
              <strong>{t("knowledgeCreateSectionAccess")}</strong>
              <span>{t("knowledgeCreateSectionAccessDesc")}</span>
            </div>
          </div>
          <div className="knowledge-create-grid">
            <label>
              {t("knowledgeVisibility")}
              <select
                disabled={!canWrite}
                value={form.visibility}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    departmentIds: event.target.value === "department" ? current.departmentIds : [],
                    visibility: event.target.value as KnowledgeBaseVisibility,
                  }))
                }
              >
                <option value="tenant">{t("knowledgeVisibilityTenant")}</option>
                <option value="department">{t("knowledgeVisibilityDepartment")}</option>
                <option value="private">{t("knowledgeVisibilityPrivate")}</option>
              </select>
            </label>
            <label>
              {t("knowledgeRagEngine")}
              <select
                disabled={!canWrite}
                value={form.ragEngine}
                onChange={(event) =>
                  setForm((current) => ({ ...current, ragEngine: event.target.value as RAGEngineType }))
                }
              >
                <option value="ragflow">RAGFlow</option>
                <option value="pgvector">pgvector</option>
              </select>
            </label>
          </div>
          {form.visibility === "department" && (
            <div className="knowledge-department-picker">
              <span>{t("knowledgeDepartments")}</span>
              <div>
                {departmentOptions.length ? (
                  departmentOptions.map((option) => (
                    <button
                      className={cx(form.departmentIds.includes(option.id) && "active")}
                      disabled={!canWrite}
                      key={option.id}
                      onClick={() => {
                        toggleDepartment(option.id);
                        if (departmentError) setDepartmentError(null);
                      }}
                      type="button"
                    >
                      {option.label}
                    </button>
                  ))
                ) : (
                  <p>{t("knowledgeNoDepartments")}</p>
                )}
              </div>
              {departmentError && <span className="form-field-error">{departmentError}</span>}
            </div>
          )}
        </section>
      </div>
    </Drawer>
  );
}
