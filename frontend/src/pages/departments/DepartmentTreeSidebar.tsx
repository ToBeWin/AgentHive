import { ApiNotice, Button, cx } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { DepartmentResponse, DepartmentTreeNode } from "../../lib/api";
import { flattenDepartmentTree } from "./departmentUtils";

export function DepartmentTreeSidebar({
  costCenterCount,
  departments,
  error,
  loading,
  onRetry,
  onSelect,
  roleCount,
  selectedDepartment,
  tree,
}: {
  costCenterCount: number;
  departments: DepartmentResponse[];
  error: string | null;
  loading: boolean;
  onRetry: () => void;
  onSelect: (departmentId: string) => void;
  roleCount: number;
  selectedDepartment: DepartmentResponse | null;
  tree: DepartmentTreeNode[];
}) {
  const { t } = useLocale();
  const flatTree = flattenDepartmentTree(tree);

  return (
    <aside className="filters wide">
      <h3>{t("departmentsTree")}</h3>
      {error && (
        <ApiNotice
          title={t("departmentsUnavailable")}
          message={error}
          action={<Button onClick={onRetry}>{t("commonRetry")}</Button>}
        />
      )}
      {loading && <div className="budget-empty-state">{t("departmentsLoading")}</div>}
      {!loading && !flatTree.length && <div className="budget-empty-state">{t("departmentsEmpty")}</div>}
      {flatTree.map(({ depth, node }) => (
        <button
          type="button"
          className={cx("tree-row", selectedDepartment?.id === node.id && "active")}
          key={node.id}
          onClick={() => onSelect(node.id)}
        >
          <span style={{ paddingLeft: `${depth * 14}px` }}>{depth ? "└" : "▾"} </span>
          {node.name}
        </button>
      ))}
      <div className="org-side-summary">
        <strong>{departments.length}</strong>
        <span>{t("departmentsCount")}</span>
        <strong>{costCenterCount}</strong>
        <span>{t("departmentsCostCentersCount")}</span>
        <strong>{roleCount}</strong>
        <span>{t("departmentsRolesCount")}</span>
      </div>
    </aside>
  );
}
