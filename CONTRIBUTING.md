# Contributing to AgentHive

感谢参与 AgentHive。项目仍处于 `v0.3.0-alpha.2`，欢迎围绕企业 AI 的可治理性、私有化部署、Agent 运行可靠性和用户体验提交改进。

## 开始之前

1. 先阅读 [README](./README.md) 和 [AGENTS.md](./AGENTS.md)。
2. 复杂改动先开 Issue，说明目标、影响范围和验收方式。
3. 不要提交 `.env`、License 私钥、客户数据、诊断包、Playwright 日志或本地模型文件。

## 本地检查

```bash
npm run check
npm run build
cd frontend && npm test -- --run
cd ../backend && uv sync --frozen --dev
uv run ruff check app tests
uv run mypy app
uv run pytest -q
```

## 提交约定

- 保持单体边界和现有 Adapter/Service/Registry 设计，不为单一供应商绕过 Gateway。
- 涉及权限、预算、审计、凭据、文件存储或多租户范围的改动必须补测试。
- UI 改动需要覆盖中英文文案、加载/错误/空状态和移动端布局；必要时更新 `docs/screenshots/`。
- Pull request 请说明行为变化、测试命令和未完成的现场验收项。

## 代码风格

- Python 使用 Ruff 和严格 Mypy。
- TypeScript 使用 Biome 和严格 TypeScript。
- 手工编辑优先保持现有目录、命名和公共组件模式，避免与功能无关的大范围格式化。
