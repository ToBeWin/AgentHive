import { useEffect } from "react";

/**
 * 在组件挂载时监听 Escape 键并触发回调。
 * 用于 Drawer / Modal 等需要键盘关闭的场景，提升可访问性。
 *
 * @param onEscape Escape 键回调
 * @param enabled 是否启用监听（默认 true，可在关闭状态下省略监听开销）
 */
export function useEscapeKey(onEscape: () => void, enabled = true): void {
  useEffect(() => {
    if (!enabled) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onEscape();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onEscape, enabled]);
}
