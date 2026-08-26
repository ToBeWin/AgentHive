import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { authApi } from "./lib/api";

describe("App authentication bootstrap", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    // biome-ignore lint/suspicious/noDocumentCookie: jsdom does not expose the Cookie Store API.
    document.cookie = "agenthive_csrf=test-csrf; Path=/";
  });

  afterEach(() => {
    vi.restoreAllMocks();
    // biome-ignore lint/suspicious/noDocumentCookie: jsdom does not expose the Cookie Store API.
    document.cookie = "agenthive_csrf=; Max-Age=0; Path=/";
  });

  it("fails closed when setup status is unavailable despite cached session hints", async () => {
    window.sessionStorage.setItem(
      "agenthive.auth_user",
      JSON.stringify({
        id: "cached-user",
        tenant_id: "cached-tenant",
        email: "cached@example.com",
        full_name: "Cached User",
        is_tenant_admin: true,
        permissions: ["*"],
      }),
    );
    const getSetupStatus = vi.spyOn(authApi, "getSetupStatus").mockRejectedValue(new Error("offline"));

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("offline");
    expect(screen.queryByText("Cached User")).not.toBeInTheDocument();
    expect(getSetupStatus).toHaveBeenCalledOnce();

    fireEvent.click(screen.getByRole("button", { name: /retry|重试/i }));
    await waitFor(() => expect(getSetupStatus).toHaveBeenCalledTimes(2));
  });
});
