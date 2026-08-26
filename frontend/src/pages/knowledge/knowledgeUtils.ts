import type { DepartmentTreeNode, KnowledgeBaseVisibility } from "../../lib/api";

export function formatKnowledgeStatus(status: string) {
  return status.replace(/_/g, " ").toUpperCase();
}

export function formatKnowledgeVisibility(visibility: KnowledgeBaseVisibility) {
  return visibility.replace(/_/g, " ").toUpperCase();
}

export function formatKnowledgeVisibilityLabel(visibility: KnowledgeBaseVisibility, t: (key: string) => string) {
  if (visibility === "tenant") {
    return t("knowledgeVisibilityTenant");
  }
  if (visibility === "department") {
    return t("knowledgeVisibilityDepartment");
  }
  return t("knowledgeVisibilityPrivate");
}

export function formatBytes(value: number | null, pendingLabel = "Size pending") {
  if (value === null) {
    return pendingLabel;
  }
  if (value < 1024) {
    return `${value} B`;
  }
  const units = ["KB", "MB", "GB"];
  let size = value / 1024;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

export function documentFileType(document: { content_type: string | null; filename: string }) {
  const filenameType = document.filename.includes(".") ? document.filename.split(".").pop() : null;
  const contentType = document.content_type?.split("/").pop();
  return (filenameType || contentType || "file").toUpperCase();
}

export function flattenDepartmentTree(
  nodes: DepartmentTreeNode[],
  depth = 0,
): Array<{ depth: number; node: DepartmentTreeNode }> {
  return nodes.flatMap((node) => [{ depth, node }, ...flattenDepartmentTree(node.children, depth + 1)]);
}
