import { Edit3, ShieldCheck, Trash2, X } from "lucide-react";
import { useState } from "react";
import { Button, ConfirmDialog } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { RoleResponse } from "../../lib/api";
import { parsePermissionInput } from "./departmentUtils";

type RoleEditForm = {
  description: string;
  name: string;
  permissions: string;
};

export function RoleManagementPanel({
  deletingRoleId,
  loading,
  onDeleteRole,
  onUpdateRole,
  roles,
  updatingRoleId,
}: {
  deletingRoleId: string | null;
  loading: boolean;
  onDeleteRole: (roleId: string) => Promise<boolean>;
  onUpdateRole: (roleId: string, form: RoleEditForm) => Promise<boolean>;
  roles: RoleResponse[];
  updatingRoleId: string | null;
}) {
  const { t } = useLocale();
  const [editingRoleId, setEditingRoleId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<RoleEditForm>({
    description: "",
    name: "",
    permissions: "",
  });
  const [pendingDeleteRole, setPendingDeleteRole] = useState<RoleResponse | null>(null);

  const startEditing = (role: RoleResponse) => {
    setEditingRoleId(role.id);
    setEditForm({
      description: role.description ?? "",
      name: role.name,
      permissions: role.permissions.join(","),
    });
  };

  const cancelEditing = () => {
    setEditingRoleId(null);
    setEditForm({ description: "", name: "", permissions: "" });
  };

  const saveRole = async (roleId: string) => {
    const updated = await onUpdateRole(roleId, editForm);
    if (updated) {
      cancelEditing();
    }
  };

  const confirmDeleteRole = async () => {
    const role = pendingDeleteRole;
    setPendingDeleteRole(null);
    if (!role) {
      return;
    }
    const deleted = await onDeleteRole(role.id);
    if (deleted && editingRoleId === role.id) {
      cancelEditing();
    }
  };

  return (
    <section className="mini-panel role-management-panel">
      <div className="panel-title compact">
        <h3>{t("departmentsRoleManagement")}</h3>
        <span>
          {roles.length} {t("departmentsRolesCount")}
        </span>
      </div>
      {loading && <span>{t("departmentsLoadingRoles")}</span>}
      {!loading && !roles.length && <span>{t("departmentsNoRoles")}</span>}
      <div className="role-management-list">
        {roles.map((role) => {
          const isEditing = editingRoleId === role.id;
          const isBusy = updatingRoleId === role.id || deletingRoleId === role.id;
          return (
            <article className="role-card" key={role.id}>
              <div className="role-card-header">
                <div>
                  <strong>{role.name}</strong>
                  <span>{role.description || t("departmentsNoRoleDescription")}</span>
                </div>
                {role.is_system && (
                  <code className="role-system-badge">
                    <ShieldCheck size={13} />
                    {t("departmentsSystemRole")}
                  </code>
                )}
              </div>
              {isEditing ? (
                <div className="role-edit-grid">
                  <label>
                    {t("departmentsRoleName")}
                    <input
                      value={editForm.name}
                      onChange={(event) => setEditForm({ ...editForm, name: event.target.value })}
                    />
                  </label>
                  <label>
                    {t("departmentsRoleDescription")}
                    <input
                      value={editForm.description}
                      onChange={(event) => setEditForm({ ...editForm, description: event.target.value })}
                    />
                  </label>
                  <label className="role-permission-edit">
                    {t("departmentsPermissions")}
                    <textarea
                      value={editForm.permissions}
                      onChange={(event) => setEditForm({ ...editForm, permissions: event.target.value })}
                    />
                  </label>
                  <div className="role-card-actions">
                    <Button onClick={() => saveRole(role.id)} disabled={isBusy || !editForm.name.trim()}>
                      {updatingRoleId === role.id ? t("departmentsSavingRole") : t("departmentsSaveRole")}
                    </Button>
                    <Button variant="ghost" onClick={cancelEditing} disabled={isBusy}>
                      <X size={15} />
                      {t("departmentsCancelRoleEdit")}
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="role-permission-list">
                    {role.permissions.slice(0, 8).map((permission) => (
                      <code key={permission}>{permission}</code>
                    ))}
                    {role.permissions.length > 8 && (
                      <span>
                        {t("departmentsMorePermissions").replace("{{count}}", String(role.permissions.length - 8))}
                      </span>
                    )}
                    {!role.permissions.length && <span>{t("departmentsNoRolePermissions")}</span>}
                  </div>
                  <div className="role-card-actions">
                    <Button variant="ghost" onClick={() => startEditing(role)} disabled={role.is_system || isBusy}>
                      <Edit3 size={15} />
                      {t("departmentsEditRole")}
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => setPendingDeleteRole(role)}
                      disabled={role.is_system || isBusy}
                    >
                      <Trash2 size={15} />
                      {deletingRoleId === role.id ? t("departmentsDeletingRole") : t("departmentsDeleteRole")}
                    </Button>
                  </div>
                </>
              )}
            </article>
          );
        })}
      </div>
      <ConfirmDialog
        open={Boolean(pendingDeleteRole)}
        title={t("departmentsDeleteRole")}
        message={pendingDeleteRole ? t("departmentsDeleteRoleConfirm").replace("{{role}}", pendingDeleteRole.name) : ""}
        confirmLabel={t("departmentsDeleteRole")}
        cancelLabel={t("commonClose")}
        variant="danger"
        onConfirm={confirmDeleteRole}
        onCancel={() => setPendingDeleteRole(null)}
      />
    </section>
  );
}

export function roleEditFormToPayload(form: RoleEditForm) {
  return {
    description: form.description.trim() || null,
    name: form.name.trim(),
    permissions: parsePermissionInput(form.permissions),
  };
}
