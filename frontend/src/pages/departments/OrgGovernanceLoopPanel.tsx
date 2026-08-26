import { Building2, ClipboardCheck, type LucideIcon, ShieldCheck, UsersRound, WalletCards } from "lucide-react";
import { useState } from "react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  CostCenterResponse,
  DepartmentResponse,
  PermissionCatalogItem,
  RoleResponse,
  UserResponse,
} from "../../lib/api";
import type { DepartmentsGovernanceTab, DepartmentsPageTab } from "./departmentsWorkspaceTypes";
import type { OrgSetupTab } from "./OrgQuickActionsPanel";

interface OrgGovernanceLoopPanelProps {
  activeTab: DepartmentsPageTab;
  costCenters: CostCenterResponse[];
  departments: DepartmentResponse[];
  governanceTab: DepartmentsGovernanceTab;
  onOpenCostGovernance: () => void;
  onOpenDepartmentGovernance: () => void;
  onOpenPeople: () => void;
  onOpenRoleSetup: () => void;
  onOpenUserSetup: () => void;
  rolePermissions: PermissionCatalogItem[];
  roles: RoleResponse[];
  selectedDepartment: DepartmentResponse | null;
  setupTab: OrgSetupTab;
  users: UserResponse[];
}

type OrgGovernanceStageId = "org" | "people" | "roles" | "costs" | "review";

function activeStageId(
  activeTab: DepartmentsPageTab,
  governanceTab: DepartmentsGovernanceTab,
  setupTab: OrgSetupTab,
): OrgGovernanceStageId {
  if (activeTab === "people") {
    return "people";
  }
  if (activeTab === "setup") {
    if (setupTab === "role") {
      return "roles";
    }
    if (setupTab === "cost") {
      return "costs";
    }
    if (setupTab === "user") {
      return "people";
    }
    return "org";
  }
  if (activeTab === "governance") {
    if (governanceTab === "roles") {
      return "roles";
    }
    if (governanceTab === "costs") {
      return "costs";
    }
    return "org";
  }
  return "review";
}

export function OrgGovernanceLoopPanel({
  activeTab,
  costCenters,
  departments,
  governanceTab,
  onOpenCostGovernance,
  onOpenDepartmentGovernance,
  onOpenPeople,
  onOpenRoleSetup,
  onOpenUserSetup,
  rolePermissions,
  roles,
  selectedDepartment,
  setupTab,
  users,
}: OrgGovernanceLoopPanelProps) {
  const { t } = useLocale();
  const [selectedStageId, setSelectedStageId] = useState<OrgGovernanceStageId>(() =>
    activeStageId(activeTab, governanceTab, setupTab),
  );
  const activeUsers = users.filter((user) => user.is_active).length;
  const usersWithDepartment = users.filter((user) => user.departments.length > 0).length;
  const usersWithRole = users.filter((user) => user.roles.length > 0 || user.is_tenant_admin).length;
  const usersWithCostCenter = users.filter((user) =>
    user.departments.some((department) => Boolean(department.cost_center_id)),
  ).length;
  const activeCostCenters = costCenters.filter((costCenter) => costCenter.is_active).length;
  const departmentCostCenters = costCenters.filter((costCenter) => Boolean(costCenter.department_id)).length;
  const ready =
    departments.length > 0 &&
    users.length > 0 &&
    roles.length > 0 &&
    costCenters.length > 0 &&
    usersWithDepartment === users.length &&
    usersWithRole === users.length &&
    usersWithCostCenter === users.length;

  const stages: Array<{
    action: () => void;
    detail: string;
    icon: LucideIcon;
    id: OrgGovernanceStageId;
    metric: string;
    status: string;
    title: string;
    tone: "ok" | "warning" | "blocked";
  }> = [
    {
      action: onOpenDepartmentGovernance,
      detail: selectedDepartment
        ? t("departmentsLoopOrgDetailSelected").replace("{{department}}", selectedDepartment.name)
        : t("departmentsLoopOrgDetailEmpty"),
      icon: Building2,
      id: "org",
      metric: t("departmentsLoopOrgMetric").replace("{{count}}", String(departments.length)),
      status: departments.length ? t("departmentsLoopReady") : t("departmentsLoopNeedsDepartment"),
      title: t("departmentsLoopOrg"),
      tone: departments.length ? "ok" : "blocked",
    },
    {
      action: users.length ? onOpenPeople : onOpenUserSetup,
      detail: t("departmentsLoopPeopleDetail")
        .replace("{{active}}", String(activeUsers))
        .replace("{{bound}}", String(usersWithDepartment)),
      icon: UsersRound,
      id: "people",
      metric: t("departmentsLoopPeopleMetric").replace("{{count}}", String(users.length)),
      status: users.length
        ? usersWithDepartment === users.length
          ? t("departmentsLoopReady")
          : t("departmentsLoopNeedsUserScope")
        : t("departmentsLoopNeedsUser"),
      title: t("departmentsLoopPeople"),
      tone: users.length ? (usersWithDepartment === users.length ? "ok" : "warning") : "blocked",
    },
    {
      action: onOpenRoleSetup,
      detail: t("departmentsLoopRolesDetail")
        .replace("{{permissions}}", String(rolePermissions.length))
        .replace("{{bound}}", String(usersWithRole)),
      icon: ShieldCheck,
      id: "roles",
      metric: t("departmentsLoopRolesMetric").replace("{{count}}", String(roles.length)),
      status: roles.length
        ? usersWithRole === users.length
          ? t("departmentsLoopReady")
          : t("departmentsLoopNeedsRoleBinding")
        : t("departmentsLoopNeedsRole"),
      title: t("departmentsLoopRoles"),
      tone: roles.length ? (users.length === 0 || usersWithRole === users.length ? "ok" : "warning") : "blocked",
    },
    {
      action: onOpenCostGovernance,
      detail: t("departmentsLoopCostsDetail")
        .replace("{{active}}", String(activeCostCenters))
        .replace("{{department}}", String(departmentCostCenters)),
      icon: WalletCards,
      id: "costs",
      metric: t("departmentsLoopCostsMetric").replace("{{count}}", String(costCenters.length)),
      status: costCenters.length
        ? usersWithCostCenter === users.length
          ? t("departmentsLoopReady")
          : t("departmentsLoopNeedsCostBinding")
        : t("departmentsLoopNeedsCostCenter"),
      title: t("departmentsLoopCosts"),
      tone: costCenters.length
        ? users.length === 0 || usersWithCostCenter === users.length
          ? "ok"
          : "warning"
        : "blocked",
    },
    {
      action: onOpenPeople,
      detail: ready ? t("departmentsLoopReviewDetailReady") : t("departmentsLoopReviewDetailPending"),
      icon: ClipboardCheck,
      id: "review",
      metric: ready ? t("departmentsLoopReviewReady") : t("departmentsLoopReviewPending"),
      status: ready ? t("departmentsLoopReady") : t("departmentsLoopNeedsReview"),
      title: t("departmentsLoopReview"),
      tone: ready ? "ok" : "warning",
    },
  ];
  const defaultStageId = activeStageId(activeTab, governanceTab, setupTab);
  const preferredStage =
    stages.find((stage) => stage.tone === "blocked") ??
    stages.find((stage) => stage.tone === "warning") ??
    stages.find((stage) => stage.id === defaultStageId) ??
    stages[0];
  const selectedStage = stages.find((stage) => stage.id === selectedStageId) ?? preferredStage;
  const SelectedIcon = selectedStage.icon;
  const readyCount = stages.filter((stage) => stage.tone === "ok").length;
  const reviewCount = stages.filter((stage) => stage.tone === "warning").length;
  const blockedCount = stages.filter((stage) => stage.tone === "blocked").length;

  return (
    <details className="org-governance-loop" aria-label={t("departmentsLoopTitle")}>
      <summary className="org-governance-loop-summary">
        <div>
          <span>{t("departmentsLoopEyebrow")}</span>
          <strong>{t("departmentsLoopTitle")}</strong>
          <small>{t("departmentsLoopCollapseHint")}</small>
        </div>
        <div className="org-governance-loop-summary-status">
          <StatusBadge label={t("departmentsLoopReadyCount").replace("{{count}}", String(readyCount))} status="ok" />
          <StatusBadge
            label={t("departmentsLoopReviewCount").replace("{{count}}", String(reviewCount))}
            status="warning"
          />
          <StatusBadge
            label={t("departmentsLoopBlockedCount").replace("{{count}}", String(blockedCount))}
            status="blocked"
          />
        </div>
      </summary>
      <p className="org-governance-loop-description">{t("departmentsLoopDescription")}</p>
      <div className="org-governance-loop-workspace">
        <div className="org-governance-loop-steps" role="tablist" aria-label={t("departmentsLoopStageTabs")}>
          {stages.map((stage, index) => {
            const Icon = stage.icon;
            const selected = selectedStage.id === stage.id;
            return (
              <button
                aria-selected={selected}
                className={cx("org-governance-loop-step", stage.tone, selected && "selected")}
                key={stage.id}
                onClick={() => setSelectedStageId(stage.id)}
                role="tab"
                type="button"
              >
                <span className="org-governance-loop-index">{String(index + 1).padStart(2, "0")}</span>
                <span className="org-governance-loop-icon">
                  <Icon size={18} />
                </span>
                <span>
                  <strong>{stage.title}</strong>
                  <small>{stage.status}</small>
                </span>
              </button>
            );
          })}
        </div>
        <section
          aria-label={t("departmentsLoopSelectedStage")}
          className={cx("org-governance-loop-detail", selectedStage.tone)}
        >
          <div className="org-governance-loop-detail-head">
            <span className="org-governance-loop-icon">
              <SelectedIcon size={20} />
            </span>
            <div>
              <span>{t("departmentsLoopCurrentMetric")}</span>
              <strong>{selectedStage.title}</strong>
            </div>
            <StatusBadge label={selectedStage.status} status={selectedStage.tone} />
          </div>
          <strong className="org-governance-loop-detail-metric">{selectedStage.metric}</strong>
          <p>{selectedStage.detail}</p>
          <button className="button" onClick={selectedStage.action} type="button">
            {t("departmentsLoopOpenStep")}
          </button>
        </section>
      </div>
    </details>
  );
}
