import { fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "../../i18n-context";
import { AppShell } from "./AppShell";

function renderAppShell() {
  return render(
    <LocaleProvider locale="zh-CN" setLocale={vi.fn()}>
      <AppShell
        active="overview"
        activeWorkspace="admin"
        authUser={null}
        isPrototype
        locale="zh-CN"
        onLogout={vi.fn()}
        setActive={vi.fn()}
        setActiveWorkspace={vi.fn()}
        setLocale={vi.fn()}
      >
        <div>内容</div>
      </AppShell>
    </LocaleProvider>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AppShell accessibility", () => {
  it("does not move focus to the mobile menu toggle when Escape closes a search on desktop", async () => {
    const { container } = renderAppShell();
    const search = container.querySelector<HTMLInputElement>(".searchbox input");
    const mobileToggle = container.querySelector<HTMLButtonElement>(".mobile-navigation-toggle");

    expect(search).toBeInstanceOf(HTMLInputElement);
    expect(mobileToggle).toBeInstanceOf(HTMLButtonElement);

    search?.focus();
    fireEvent.keyDown(search as HTMLInputElement, { key: "Escape" });
    await new Promise((resolve) => window.setTimeout(resolve, 10));

    expect(mobileToggle).not.toHaveFocus();
  });

  it("connects the notifications trigger to its dialog", () => {
    const { container } = renderAppShell();
    const notificationTrigger = container.querySelector<HTMLButtonElement>(".top-action-item > .icon-button");

    expect(notificationTrigger).toHaveAttribute("aria-controls", "notifications-panel");
    fireEvent.click(notificationTrigger as HTMLButtonElement);
    expect(container.querySelector("#notifications-panel")).toHaveAttribute("role", "dialog");
  });

  it("exposes the active workspace selection state", () => {
    const { container } = renderAppShell();
    const activeWorkspace = container.querySelector<HTMLButtonElement>(".workspace-tab.active");

    expect(activeWorkspace).toHaveAttribute("aria-pressed", "true");
  });

  it("connects the sidebar toggle to the navigation it controls", () => {
    const { container } = renderAppShell();
    const sidebarToggle = container.querySelector<HTMLButtonElement>(".sidebar-collapse-button");

    expect(sidebarToggle).toHaveAttribute("aria-controls", "primary-navigation");
  });
});
