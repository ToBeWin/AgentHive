import { Search, UserPlus, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, cx, useToast } from "../../components/app-ui";
import { useUsers } from "../../hooks/useAdminData";
import { useLocale } from "../../i18n-context";
import { type AgentAssignment, assignUsersToAgent, listAgentAssignments, removeAgentUser } from "../../lib/api";

interface AgentAssignmentPanelProps {
  agentId: string;
  canWrite: boolean;
}

const ASSIGNEE_ROLES: Array<{ value: string; labelKey: string }> = [
  { value: "operator", labelKey: "agentAssignmentsOperator" },
  { value: "viewer", labelKey: "agentAssignmentsViewer" },
];

export function AgentAssignmentPanel({ agentId, canWrite }: AgentAssignmentPanelProps) {
  const { locale, t } = useLocale();
  const { showToast } = useToast();
  const [assignments, setAssignments] = useState<AgentAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [removingUserId, setRemovingUserId] = useState<string | null>(null);
  const [showPicker, setShowPicker] = useState(false);

  const loadAssignments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAgentAssignments(agentId);
      setAssignments(data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t("agentAssignmentsLoadError"));
    } finally {
      setLoading(false);
    }
  }, [agentId, t]);

  useEffect(() => {
    void loadAssignments();
  }, [loadAssignments]);

  const handleRemove = async (userId: string) => {
    setRemovingUserId(userId);
    try {
      await removeAgentUser(agentId, userId);
      setAssignments((current) => current.filter((assignment) => assignment.user_id !== userId));
      showToast(t("agentAssignmentsRemove"), "success");
    } catch (caught) {
      showToast(caught instanceof Error ? caught.message : t("agentAssignmentsRemoveError"), "error");
    } finally {
      setRemovingUserId(null);
    }
  };

  const handleAssign = async (users: Array<{ user_id: string; role: string }>) => {
    try {
      const updated = await assignUsersToAgent(agentId, users);
      setAssignments(updated);
      setShowPicker(false);
      showToast(t("agentAssignmentsAssign"), "success");
    } catch (caught) {
      showToast(caught instanceof Error ? caught.message : t("agentAssignmentsAssignError"), "error");
    }
  };

  const existingUserIds = useMemo(() => new Set(assignments.map((assignment) => assignment.user_id)), [assignments]);

  return (
    <section className="agent-instance-detail-section">
      <div className="agent-instance-detail-title">
        <strong>{t("agentInstancesDetailAssignments")}</strong>
        <span>{t("agentInstancesDetailAssignmentsHint")}</span>
      </div>
      {error && <div className={cx("form-message", "error")}>{error}</div>}
      {loading && <p className="inline-note">{t("agentAssignmentsLoading")}</p>}
      {!loading && (
        <>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("agentAssignmentsUser")}</th>
                  <th>{t("agentAssignmentsRole")}</th>
                  <th>{t("agentAssignmentsAssignedAt")}</th>
                  <th>{t("departmentsActions")}</th>
                </tr>
              </thead>
              <tbody>
                {assignments.length === 0 && (
                  <tr>
                    <td colSpan={4}>{t("agentAssignmentsEmpty")}</td>
                  </tr>
                )}
                {assignments.map((assignment) => {
                  const displayName = assignment.user_full_name ?? assignment.user_username ?? assignment.user_email;
                  return (
                    <tr key={assignment.user_id}>
                      <td>
                        <div>
                          <strong>{displayName}</strong>
                          <span className="row-subtitle">{assignment.user_email}</span>
                        </div>
                      </td>
                      <td>
                        <code>{assignment.role}</code>
                      </td>
                      <td>{formatAssignedAt(assignment.created_at, locale)}</td>
                      <td>
                        <div className="table-action-row">
                          <Button
                            variant="danger"
                            disabled={!canWrite || removingUserId === assignment.user_id}
                            onClick={() => void handleRemove(assignment.user_id)}
                          >
                            {removingUserId === assignment.user_id
                              ? t("agentAssignmentsRemoving")
                              : t("agentAssignmentsRemove")}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {canWrite && (
            <div className="provider-actions">
              <Button onClick={() => setShowPicker((current) => !current)}>
                <UserPlus size={16} /> {t("agentAssignmentsAdd")}
              </Button>
            </div>
          )}
          {showPicker && (
            <AgentUserPicker
              existingUserIds={existingUserIds}
              onCancel={() => setShowPicker(false)}
              onAssign={handleAssign}
            />
          )}
        </>
      )}
    </section>
  );
}

interface AgentUserPickerProps {
  existingUserIds: Set<string>;
  onCancel: () => void;
  onAssign: (users: Array<{ user_id: string; role: string }>) => Promise<void>;
}

function AgentUserPicker({ existingUserIds, onCancel, onAssign }: AgentUserPickerProps) {
  const { t } = useLocale();
  const { data: users, loading } = useUsers({});
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Map<string, string>>(new Map());
  const [assigning, setAssigning] = useState(false);

  const candidateUsers = useMemo(
    () => (users ?? []).filter((user) => !existingUserIds.has(user.id)),
    [existingUserIds, users],
  );

  const filteredUsers = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) {
      return candidateUsers;
    }
    return candidateUsers.filter((user) =>
      `${user.email} ${user.full_name ?? ""} ${user.username ?? ""}`.toLowerCase().includes(query),
    );
  }, [candidateUsers, search]);

  const toggleUser = (userId: string, checked: boolean) => {
    setSelected((current) => {
      const next = new Map(current);
      if (checked) {
        next.set(userId, "operator");
      } else {
        next.delete(userId);
      }
      return next;
    });
  };

  const setRole = (userId: string, role: string) => {
    setSelected((current) => {
      const next = new Map(current);
      if (next.has(userId)) {
        next.set(userId, role);
      }
      return next;
    });
  };

  const handleAssign = async () => {
    if (selected.size === 0) {
      return;
    }
    setAssigning(true);
    try {
      await onAssign(Array.from(selected.entries()).map(([user_id, role]) => ({ user_id, role })));
    } finally {
      setAssigning(false);
    }
  };

  return (
    <div className="agent-assignment-picker">
      <div className="agent-knowledge-search">
        <Search size={15} />
        <input
          placeholder={t("agentAssignmentsSearchPlaceholder")}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      {loading && <p className="inline-note">{t("agentAssignmentsLoading")}</p>}
      {!loading && (
        <div className="agent-assignment-list">
          {filteredUsers.length === 0 && (
            <div className="agent-knowledge-empty">{t("agentAssignmentsNoCandidates")}</div>
          )}
          {filteredUsers.map((user) => {
            const isSelected = selected.has(user.id);
            const displayName = user.full_name ?? user.username ?? user.email;
            return (
              <label key={user.id} className={cx("agent-assignment-option", isSelected && "selected")}>
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={(event) => toggleUser(user.id, event.target.checked)}
                />
                <span className="agent-assignment-user">
                  <strong>{displayName}</strong>
                  <small>{user.email}</small>
                </span>
                <select
                  disabled={!isSelected}
                  title={t("agentAssignmentsRole")}
                  value={selected.get(user.id) ?? "operator"}
                  onChange={(event) => setRole(user.id, event.target.value)}
                >
                  {ASSIGNEE_ROLES.map((role) => (
                    <option key={role.value} value={role.value}>
                      {t(role.labelKey)}
                    </option>
                  ))}
                </select>
              </label>
            );
          })}
        </div>
      )}
      <div className="provider-actions">
        <Button variant="primary" onClick={() => void handleAssign()} disabled={assigning || selected.size === 0}>
          {assigning ? t("agentAssignmentsAssigning") : t("agentAssignmentsAssign")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={assigning}>
          <X size={14} /> {t("commonClose")}
        </Button>
      </div>
    </div>
  );
}

function formatAssignedAt(value: string, locale: string) {
  try {
    return new Intl.DateTimeFormat(locale, {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(new Date(value));
  } catch {
    return value;
  }
}
