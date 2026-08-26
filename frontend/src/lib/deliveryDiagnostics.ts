import type { WorkspaceId } from "../data";

/** Delivery handoff / readiness / loop panels are admin-only. */
export function showDeliveryDiagnostics(activeWorkspace: WorkspaceId) {
  return activeWorkspace === "admin";
}
