import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AuthUser } from "../lib/api";
import { UsersPage } from "./UsersPage";

const actionMocks = vi.hoisted(() => ({
  createUser: vi.fn(),
  refetch: vi.fn(),
  resetUserPassword: vi.fn(),
  updateUser: vi.fn(),
  updateUserStatus: vi.fn(),
}));

vi.mock("../i18n-context", () => ({
  useLocale: () => ({
    locale: "en-US",
    setLocale: vi.fn(),
    t: (key: string) => key,
  }),
}));

vi.mock("../hooks/useAdminData", () => ({
  useCostCenters: () => ({ data: [], error: null, loading: false, refetch: actionMocks.refetch }),
  useDepartments: () => ({
    data: { departments: [], total: 0, tree: [] },
    error: null,
    loading: false,
    refetch: actionMocks.refetch,
  }),
  useOrgAdminActions: () => ({
    createUser: actionMocks.createUser,
    error: null,
    message: null,
    passwordResettingUserId: null,
    resetUserPassword: actionMocks.resetUserPassword,
    saving: false,
    statusUpdatingUserId: null,
    updateUser: actionMocks.updateUser,
    updateUserStatus: actionMocks.updateUserStatus,
    userUpdatingId: null,
  }),
  useRoles: () => ({ data: [], error: null, loading: false, refetch: actionMocks.refetch }),
  useUsers: () => ({
    data: [
      {
        avatar_url: null,
        created_at: "2026-01-01T00:00:00Z",
        departments: [],
        email: "reader@example.com",
        full_name: "Read Only User",
        id: "user-1",
        is_active: true,
        is_super_admin: false,
        is_tenant_admin: false,
        last_login_at: null,
        permissions: ["users:read"],
        phone: null,
        roles: [],
        tenant_id: "tenant-1",
        updated_at: "2026-01-01T00:00:00Z",
        username: null,
      },
    ],
    error: null,
    loading: false,
    refetch: actionMocks.refetch,
  }),
}));

function storeAuthUser(permissions: string[], overrides: Partial<AuthUser> = {}) {
  const user: AuthUser = {
    email: "operator@example.com",
    full_name: "Operator",
    id: "operator-1",
    is_tenant_admin: false,
    is_super_admin: false,
    permissions,
    tenant_id: "tenant-1",
    ...overrides,
  };
  window.sessionStorage.setItem("agenthive.auth_user", JSON.stringify(user));
}

describe("UsersPage users:write permission gate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("keeps user data readable but removes every write control for users:read", () => {
    storeAuthUser(["users:read"]);

    render(<UsersPage />);

    expect(screen.getByRole("heading", { name: "usersPageTitle" })).toBeInTheDocument();
    expect(screen.getByText("Read Only User")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "usersCreate" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "departmentsActions" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "departmentsEditUser" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "departmentsDeactivateUser" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "departmentsResetPassword" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Read Only User"));
    expect(actionMocks.createUser).not.toHaveBeenCalled();
    expect(actionMocks.updateUser).not.toHaveBeenCalled();
    expect(actionMocks.updateUserStatus).not.toHaveBeenCalled();
    expect(actionMocks.resetUserPassword).not.toHaveBeenCalled();
  });

  it("shows user mutation controls when users:write is present", () => {
    storeAuthUser(["users:read", "users:write"]);

    render(<UsersPage />);

    expect(screen.getByRole("button", { name: "usersCreate" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "departmentsActions" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "departmentsEditUser" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "departmentsDeactivateUser" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "departmentsResetPassword" })).toBeInTheDocument();
  });

  it("preserves write controls for tenant administrators", () => {
    storeAuthUser(["users:read"], { is_tenant_admin: true });

    render(<UsersPage />);

    expect(screen.getByRole("button", { name: "usersCreate" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "departmentsEditUser" })).toBeInTheDocument();
  });
});
