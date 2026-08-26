// 全局测试设置文件
//
// 在每个测试文件执行前加载 @testing-library/jest-dom，为 expect 扩展 DOM 断言：
//   - toBeInTheDocument / toBeVisible / toBeDisabled / toBeEmptyDOMElement
//   - toHaveTextContent / toHaveAttribute / toHaveClass / toHaveValue
//
// 注意：使用 `@testing-library/jest-dom/vitest` 子路径而非默认入口。
// 该子路径会同时完成两件事：
//   1. 运行时：将匹配器注册到 vitest 的全局 expect；
//   2. 类型：通过模块增强扩展 vitest 的 Assertion / AsymmetricMatchers 类型，
//      使 TypeScript 能识别 toBeInTheDocument 等断言。
// 仅用默认入口只会增强 jest 的 expect 类型，vitest 下仍会报类型错误。
//
// 该文件通过 vitest.config.ts 的 test.setupFiles 自动注入，各测试文件无需手动导入。
// 同时，@testing-library/react 会在检测到全局 afterEach（vitest globals: true 已开启）
// 时自动注册组件清理逻辑，避免测试间 DOM 残留。
import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";

function createMemoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear() {
      values.clear();
    },
    getItem(key) {
      return values.get(key) ?? null;
    },
    key(index) {
      return Array.from(values.keys())[index] ?? null;
    },
    removeItem(key) {
      values.delete(key);
    },
    setItem(key, value) {
      values.set(key, String(value));
    },
  };
}

// Node 25 exposes an experimental global localStorage that can override jsdom's
// implementation and lacks the Web Storage API unless a backing file is supplied.
// Use a deterministic in-memory implementation in every supported Node version.
Object.defineProperty(window, "localStorage", {
  configurable: true,
  value: createMemoryStorage(),
});
Object.defineProperty(window, "sessionStorage", {
  configurable: true,
  value: createMemoryStorage(),
});

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  // biome-ignore lint/suspicious/noDocumentCookie: jsdom has no Cookie Store API.
  document.cookie = "agenthive_csrf=; Max-Age=0; Path=/; SameSite=Lax";
});
