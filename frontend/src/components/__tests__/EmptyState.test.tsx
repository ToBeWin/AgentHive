import { render, screen } from "@testing-library/react";
import { Inbox } from "lucide-react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "../app-ui";

// EmptyState 组件：在无数据场景下展示占位状态
// 覆盖其全部 props（icon / title / message / action）的渲染行为，
// 确保后续重构不会破坏与业务页面的 UI 契约。
describe("EmptyState 组件", () => {
  it("渲染必填的标题（title）", () => {
    render(<EmptyState title="暂无数据" />);
    // 标题以 h3 形式渲染，便于辅助技术与文档大纲识别
    expect(screen.getByRole("heading", { level: 3, name: "暂无数据" })).toBeInTheDocument();
  });

  it("渲染可选的描述文案（message）", () => {
    render(<EmptyState title="暂无数据" message="请先创建一个智能体" />);
    expect(screen.getByText("请先创建一个智能体")).toBeInTheDocument();
  });

  it("渲染可选的图标（icon）", () => {
    const { container } = render(<EmptyState title="暂无数据" icon={<Inbox />} />);
    // lucide 图标渲染为 <svg>，应被放入 .empty-state-icon 容器
    const iconSlot = container.querySelector(".empty-state-icon");
    expect(iconSlot).not.toBeNull();
    expect(iconSlot?.querySelector("svg")).not.toBeNull();
  });

  it("渲染可选的操作区（action）", () => {
    render(<EmptyState title="暂无数据" action={<button type="button">新建智能体</button>} />);
    expect(screen.getByRole("button", { name: "新建智能体" })).toBeInTheDocument();
  });

  it("未传入 icon/message/action 时仅渲染标题", () => {
    const { container } = render(<EmptyState title="空空如也" />);
    expect(container.querySelector(".empty-state-icon-wrapper")).toBeNull();
    expect(container.querySelector(".empty-state-message")).toBeNull();
    expect(container.querySelector(".empty-state-action")).toBeNull();
  });

  it("根节点具备 role=status，便于屏幕阅读器识别为状态信息", () => {
    render(<EmptyState title="暂无数据" />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
