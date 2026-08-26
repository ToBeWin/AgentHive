import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LoadingState } from "../app-ui";

// LoadingState 组件：数据加载中时展示骨架屏占位，避免界面跳空
// 覆盖默认行数、自定义行数、可选文案以及无障碍属性。
describe("LoadingState 组件", () => {
  it("渲染 role=status 的加载状态容器", () => {
    render(<LoadingState />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("默认渲染 3 行骨架屏", () => {
    const { container } = render(<LoadingState />);
    // Skeleton 在 lines>1 时输出 .skeleton-lines 容器，每行一个 .skeleton-line
    expect(container.querySelectorAll(".skeleton-line")).toHaveLength(3);
  });

  it("支持通过 lines 自定义骨架屏行数", () => {
    const { container } = render(<LoadingState lines={5} />);
    expect(container.querySelectorAll(".skeleton-line")).toHaveLength(5);
  });

  it("渲染可选的加载提示文案（message）", () => {
    render(<LoadingState message="加载中…" />);
    expect(screen.getByText("加载中…")).toBeInTheDocument();
  });

  it("未传入 message 时不渲染提示段落", () => {
    const { container } = render(<LoadingState />);
    expect(container.querySelector(".loading-state-message")).toBeNull();
  });

  it("骨架屏容器带 aria-hidden，对辅助技术隐藏装饰性占位", () => {
    const { container } = render(<LoadingState />);
    const skeletonLines = container.querySelector(".skeleton-lines");
    expect(skeletonLines).not.toBeNull();
    expect(skeletonLines?.getAttribute("aria-hidden")).not.toBeNull();
  });
});
