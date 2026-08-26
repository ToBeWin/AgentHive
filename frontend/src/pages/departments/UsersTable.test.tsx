import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { UserResponse } from "../../lib/api";
import { UsersTable } from "./UsersTable";

vi.mock("../../i18n-context", () => ({
  useLocale: () => ({
    locale: "en-US",
    setLocale: vi.fn(),
    t: (key: string) => key,
  }),
}));

const user: UserResponse = {
  avatar_url: null,
  created_at: "2026-01-01T00:00:00Z",
  departments: [],
  email: "reader@example.com",
  full_name: "Read Only User",
  id: "user-1",
  is_active: false,
  is_super_admin: false,
  is_tenant_admin: false,
  last_login_at: null,
  permissions: ["users:read"],
  phone: null,
  roles: [],
  tenant_id: "tenant-1",
  updated_at: "2026-01-01T00:00:00Z",
  username: null,
};

function renderTable(canWriteUsers: boolean) {
  const callbacks = {
    onResetUserPassword: vi.fn(async () => true),
    onToggleUserStatus: vi.fn(),
    onUpdateUser: vi.fn(async () => true),
  };
  render(
    <UsersTable
      canWriteUsers={canWriteUsers}
      costCenters={[]}
      departments={[]}
      loading={false}
      passwordResettingUserId={null}
      roles={[]}
      selectedDepartment={null}
      showCostCenter={false}
      statusUpdatingUserId={null}
      updatingUserId={null}
      users={[user]}
      {...callbacks}
    />,
  );
  return callbacks;
}

describe("UsersTable write controls", () => {
  it("renders a read-only row without an action surface", () => {
    const callbacks = renderTable(false);

    expect(screen.getByText("Read Only User")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "departmentsActions" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "departmentsEditUser" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "departmentsActivateUser" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "departmentsResetPassword" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Read Only User"));
    expect(callbacks.onUpdateUser).not.toHaveBeenCalled();
    expect(callbacks.onToggleUserStatus).not.toHaveBeenCalled();
    expect(callbacks.onResetUserPassword).not.toHaveBeenCalled();
  });

  it("retains the existing write action behavior when allowed", () => {
    const callbacks = renderTable(true);

    fireEvent.click(screen.getByRole("button", { name: "departmentsActivateUser" }));

    expect(callbacks.onToggleUserStatus).toHaveBeenCalledOnce();
    expect(callbacks.onToggleUserStatus).toHaveBeenCalledWith("user-1", true);
    expect(screen.getByRole("button", { name: "departmentsEditUser" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "departmentsResetPassword" })).toBeInTheDocument();
  });
});
