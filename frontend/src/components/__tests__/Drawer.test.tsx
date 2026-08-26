import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "../../i18n-context";
import { Drawer } from "../app-ui";

function renderDrawer(open: boolean, onClose = vi.fn()) {
  return render(
    <LocaleProvider locale="zh-CN" setLocale={vi.fn()}>
      <button type="button">打开抽屉</button>
      <Drawer open={open} title="详情" onClose={onClose}>
        <button type="button">内部操作</button>
      </Drawer>
    </LocaleProvider>,
  );
}

describe("Drawer keyboard focus", () => {
  it("moves initial focus into the modal and traps Tab navigation", async () => {
    renderDrawer(true);

    const dialog = screen.getByRole("dialog", { name: "详情" });
    const close = dialog.querySelector("header button");
    expect(close).toBeInstanceOf(HTMLButtonElement);
    await waitFor(() => expect(close).toHaveFocus());

    const action = screen.getByRole("button", { name: "内部操作" });
    action.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(close).toHaveFocus();

    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(action).toHaveFocus();
    expect(dialog).toHaveAttribute("aria-modal", "true");
  });

  it("restores focus to the opener after closing", async () => {
    const onClose = vi.fn();
    const view = renderDrawer(false, onClose);
    const opener = screen.getByRole("button", { name: "打开抽屉" });
    opener.focus();

    view.rerender(
      <LocaleProvider locale="zh-CN" setLocale={vi.fn()}>
        <button type="button">打开抽屉</button>
        <Drawer open title="详情" onClose={onClose}>
          内容
        </Drawer>
      </LocaleProvider>,
    );
    const dialog = screen.getByRole("dialog", { name: "详情" });
    await waitFor(() => expect(dialog.querySelector("header button")).toHaveFocus());

    view.rerender(
      <LocaleProvider locale="zh-CN" setLocale={vi.fn()}>
        <button type="button">打开抽屉</button>
        <Drawer open={false} title="详情" onClose={onClose}>
          内容
        </Drawer>
      </LocaleProvider>,
    );
    expect(screen.getByRole("button", { name: "打开抽屉" })).toHaveFocus();
  });
});
