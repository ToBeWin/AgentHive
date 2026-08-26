# 前端测试说明

AgentHive 前端测试分为两层：

| 层级 | 工具 | 用途 | 入口脚本 |
| --- | --- | --- | --- |
| 组件 / 单元测试 | Vitest + @testing-library/react + jsdom | 验证组件渲染、交互与纯函数逻辑 | `npm test` |
| E2E 测试 | Playwright (chromium) | 验证真实浏览器下的关键业务流程 | `npm run e2e` |

两类测试相互独立：`npm test` 不会触发 E2E，`npm run e2e` 也不会运行组件测试。

---

## 一、环境准备

首次运行前需安装依赖（含新增的 testing-library 与已有的 vitest / playwright）：

```bash
cd frontend
npm install
```

> Vitest 与 Playwright 的可执行文件随 `npm install` 自动就绪。Playwright 的浏览器二进制需要单独安装（见下文 E2E 部分）。

---

## 二、组件测试（Vitest + Testing Library）

### 2.1 运行命令

```bash
npm test               # 单次运行全部测试（CI 友好，运行后退出）
npm run test:watch     # 监听模式，文件变更自动重跑（本地开发推荐）
npm run test:coverage  # 生成覆盖率报告（v8 provider，输出 text / html / lcov）
```

### 2.2 目录结构

```
frontend/
├── vitest.config.ts                 # Vitest 配置：jsdom 环境 + react 插件 + setupFiles
└── src/
    ├── test/
    │   └── setup.ts                 # 全局设置：注入 @testing-library/jest-dom/vitest 断言
    ├── components/
    │   └── __tests__/
    │       ├── EmptyState.test.tsx  # EmptyState 组件示例测试
    │       └── LoadingState.test.tsx# LoadingState 骨架屏示例测试
    └── lib/
        └── *.test.ts                # 已有的纯函数单元测试
```

### 2.3 配置要点（`vitest.config.ts`）

- `environment: "jsdom"`：在 Node 中模拟 DOM，支持组件渲染。
- `plugins: [react()]`：通过 `@vitejs/plugin-react` 处理 JSX / TSX。
- `globals: true`：`describe` / `it` / `expect` / `beforeEach` 等全局可用；同时使 `@testing-library/react` 的自动清理（`afterEach`）生效。
- `setupFiles: ["./src/test/setup.ts"]`：每个测试文件执行前注入 jest-dom 断言。
- `include: ["src/**/*.{test,spec}.{ts,tsx}"]`：测试文件约定放在 `src` 内，与源码同级或集中于 `__tests__` 目录。
- `exclude` 已排除 `tests/e2e/**`，避免 Playwright 用例被误纳入。

### 2.4 编写规范

- 测试文件统一使用 `.test.tsx`（组件）或 `.test.ts`（纯函数）后缀。
- 显式从 `vitest` 导入 `describe` / `it` / `expect`（与现有测试风格一致）。
- DOM 断言（`toBeInTheDocument`、`toHaveTextContent` 等）由 setup.ts 全局注入，无需在各测试中重复导入。
- 优先使用语义查询（`getByRole` / `getByLabelText` / `getByText`），而非 CSS 类名，以提升可维护性与可访问性校验。
- 代码风格遵循 `biome.json`：双引号、分号、尾随逗号、2 空格缩进。

### 2.5 示例：覆盖的组件契约

`EmptyState.test.tsx` 验证：

- 必填 `title` 渲染为 `h3`；
- 可选 `message` / `icon` / `action` 正确渲染；
- 缺省可选 props 时不渲染对应节点；
- 根节点具备 `role="status"`。

`LoadingState.test.tsx` 验证：

- 默认渲染 3 行骨架屏，`lines` 可自定义行数；
- 可选 `message` 渲染提示文案；
- 根节点 `role="status"`，骨架屏 `aria-hidden` 对辅助技术隐藏装饰性占位。

---

## 三、E2E 测试（Playwright）

### 3.1 前置条件

E2E 测试需要完整运行栈（前端 + 后端 + 演示数据），**不会**随 `npm test` 触发。

```bash
# 1. 启动开发栈（后端 + 演示数据由 compose 自动播种）
docker compose -f docker-compose.dev.yml up -d

# 2. 安装 chromium 浏览器二进制（仅首次）
npm run e2e:install
```

### 3.2 运行命令

```bash
npm run e2e           # 运行全部 E2E 用例
```

如需指向非默认地址，可设置环境变量：

```bash
AGENTHIVE_E2E_BASE_URL=http://localhost:18080 npm run e2e
```

### 3.3 配置要点（`frontend/playwright.config.ts`）

- `testDir: "./tests/e2e"`：用例位于 `frontend/tests/e2e/`。
- `baseURL`：默认 `http://127.0.0.1:18080`（等价于 `localhost:18080`），可通过 `AGENTHIVE_E2E_BASE_URL` 覆盖。
- `projects`：仅 `chromium`。
- `workers: 1` + `fullyParallel: false`：用例共享同一演示租户，串行执行避免状态竞争。
- `locale: "zh-CN"`、`timezoneId: "Asia/Shanghai"`：模拟目标用户环境。
- CI 下自动启用 `retries: 1`、`forbidOnly` 与 `github` / `html` 报告器。

### 3.4 现有冒烟用例（`tests/e2e/smoke.spec.ts`）

- 管理员登录后可见管理工作台与「智能体」导航；
- 错误凭据被拒绝并提示错误；
- 进入 Builder 页面并见表单。

---

## 四、CI 集成

### 4.1 组件测试 Job

直接运行，无需额外服务：

```yaml
- run: npm ci
- run: npm test          # 等价 vitest run，单次执行后退出
# 可选：上传覆盖率
- run: npm run test:coverage
```

`vitest run` 在 CI 下天然友好（非监听、自动退出）。覆盖率产出 `lcov` 供 CI 上传。

### 4.2 E2E Job

需要服务容器或已启动的栈：

```yaml
- run: npm ci
- run: npm run e2e:install
- run: docker compose -f docker-compose.dev.yml up -d
- run: npm run e2e
  env:
    AGENTHIVE_E2E_BASE_URL: http://127.0.0.1:18080
```

`playwright.config.ts` 已依据 `process.env.CI` 自动调整重试与报告器，无需额外参数。

---

## 五、故障排查

| 现象 | 排查方向 |
| --- | --- |
| `Cannot find module '@testing-library/react'` | 未安装依赖，执行 `npm install`。 |
| `toBeInTheDocument` 类型错误 | 确认 `src/test/setup.ts` 使用 `@testing-library/jest-dom/vitest`（而非默认入口）。 |
| 组件测试因缺少 i18n Provider 报错 | 待测组件若依赖 `useLocale`，需用 `LocaleProvider` 包裹；`EmptyState` / `LoadingState` 不依赖该 Provider，可直接渲染。 |
| E2E 连接被拒 | 确认开发栈已启动且监听 18080；必要时设置 `AGENTHIVE_E2E_BASE_URL`。 |
| Playwright 提示缺少浏览器 | 执行 `npm run e2e:install`。 |
| Biome 格式校验失败 | 执行 `npm run format` 自动格式化测试文件。 |
