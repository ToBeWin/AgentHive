# AgentHive 模型费用治理

AgentHive 的模型费用治理目标是让企业能按租户、部门、人员、Agent、Channel 和成本中心精细化控制模型使用，而不是只统计总账。

## 调用链路

```text
Agent / Chat / Channel
  → LLM Gateway
  → Policy Resolver
  → Budget Guard
  → Model Router
  → Budget Ledger
  → Usage Collector
  → LLM Usage Ledger
```

所有模型调用必须经过 LLM Gateway。业务模块不得绕过网关直接调用供应商 SDK。

## 预算控制

预算策略存储在 `llm_budgets`，当前支持：

- `tenant`
- `department`
- `cost_center`
- `user`
- `agent`
- `channel`

创建或更新非租户级预算策略时，后端必须校验 `scope_id` 属于当前租户：部门、成本中心、用户、Agent、Channel 都要按租户过滤查询，用户目标还要排除已软删除用户。前端下拉选择只用于体验优化，不能作为安全边界；直接调用 API 传入不存在或跨租户的 `scope_id` 必须返回 404，且不得写入预算策略或审计副作用。

调用前 `BudgetGuard` 会根据上下文匹配 hard-limit 策略，估算 Token 和费用，超过硬限制时直接拒绝调用。`cost_center` 策略使用与用量账本一致的成本中心解析逻辑：显式上下文优先，其次按用户部门绑定和主部门成本中心解析。

预算周期支持 `daily`、`monthly` 和 `custom`。自定义周期必须持久化到 `llm_budgets.custom_period_start` / `llm_budgets.custom_period_end`，运行时预算拦截和管理端用量统计都必须使用该策略自己的周期窗口，而不是只使用页面查询窗口。

预算类型支持：

- `hard`：调用前强拦截，预计费用或 Token 超过额度时返回预算拒绝。
- `soft`：调用不拦截，首次从低于告警阈值跨过阈值时写入 `alert` 账本事件，用于企业管理员和财务复核。

预算策略支持启用和停用。停用策略不会参与运行时 `BudgetGuard` 匹配，也不会计入有效额度汇总；状态变更会写入审计日志 `budget.policy.status.update`，保留策略历史用于复核。

预算事件写入 `llm_budget_ledger`，采用不可变事件流：

- `reserve`：调用前预算预占，记录匹配预算、估算 Token 和估算费用。
- `deny`：调用前预算拒绝，记录触发拒绝的预算策略和原因。
- `settle`：调用成功后结算，记录实际 Token 和实际费用。
- `release`：调用失败或路由异常后释放预占，记录释放原因。
- `alert`：软预算首次跨过阈值，记录阈值、额度、跨线后的费用/Token 和策略周期。

## 用量归因

每次调用完成后写入 `llm_usage`，包含：

- `user_id`
- `department_id`
- `cost_center_id`
- `agent_id`
- `channel_id`
- `conversation_id`
- `model_key`
- Token、费用、状态、错误码和路由元数据

如果调用上下文没有显式传入 `cost_center_id`，系统会尝试从用户部门绑定关系解析默认成本中心。解析顺序为：显式上下文 `cost_center_id` > 当前用户在本次 `department_id` 下的成本中心 > 当前用户主部门成本中心 > `unresolved`。`llm_usage` 和 `llm_budget_ledger` 必须使用同一套解析逻辑，并在 metadata 中写入 `cost_center_source`，保证预算预占/结算/释放事件与最终用量明细可以按同一成本中心对账。

自动解析成本中心时必须同时校验 `user_departments` 绑定部门属于当前租户、`cost_centers.tenant_id == context.tenant_id`，并且成本中心处于 active 状态。不能只凭 `user_id` 或 `cost_center_id` 命中绑定行，否则异常导入、迁移残留或跨租户脏数据会污染费用归属和预算命中结果。

## 管理接口

| API | 用途 |
| --- | --- |
| `GET /api/v1/budgets/summary` | 预算总览，含策略数量、总额度、已用费用、Token 和按策略范围汇总。 |
| `GET /api/v1/budgets/policies` | 查询预算策略。 |
| `POST /api/v1/budgets/policies` | 创建或更新预算策略。 |
| `PATCH /api/v1/budgets/policies/{policy_id}/status` | 启用或停用预算策略，并记录审计事件。 |
| `GET /api/v1/budgets/budget-ledger` | 查询预算事件账本，包含预占、结算、释放和拒绝事件。 |
| `GET /api/v1/budgets/budget-ledger/export` | 导出预算事件账本，支持 `format=csv/json`。 |
| `GET /api/v1/budgets/usage-ledger` | 查询模型调用明细账本。 |
| `GET /api/v1/budgets/usage-ledger/export` | 导出模型调用明细账本，支持 `format=csv/json`。 |
| `GET /api/v1/budgets/usage-breakdown` | 按维度聚合费用、Token、请求数、成功/失败次数。 |

`budget-ledger` 支持按 `event_type`、`budget_id`、`reservation_id`、`request_id`、`scope_type`、`scope_id`、`user_id`、`department_id`、`cost_center_id`、`agent_id`、`channel_id` 和时间范围过滤。

`usage-ledger/export` 和 `budget-ledger/export` 默认导出 CSV，适合财务审阅和表格处理；传入 `format=json` 时导出结构化 JSON，适合二次集成和自动化对账。

`usage-breakdown` 支持的维度：

- `department`
- `user`
- `cost_center`
- `agent`
- `channel`
- `model`
- `status`

`GET /api/v1/analytics/overview` 使用独立的 `analytics:read` 权限，并基于 `llm_usage` 聚合模型、日期、部门、人员和 Agent 维度的请求数、Token 和费用。该接口用于管理后台经营/用量看板，不应复用预算读写权限，也不应暴露原始 prompt、模型回答或账本明细行。

## 交付验收

生产交付前至少验证：

1. 创建租户级 hard-limit 后，超过金额或 Token 上限的请求会被拒绝。
2. 部门、人员、Agent、Channel 维度策略只影响对应范围。
3. 成功调用会产生 `reserve` 和 `settle` 预算事件。
4. 失败调用会产生 `reserve` 和 `release` 预算事件。
5. 超额调用会产生 `deny` 预算事件，且不会进入模型供应商调用。
6. 成功和失败调用都会进入用量账本，成功调用计入费用统计。
7. 预算页可以看到最近用量账本和按部门聚合的用量分布。
8. 财务可以通过 `usage-ledger/export` 和 `budget-ledger/export` 导出 CSV/JSON 明细。
9. 停用预算策略后，该策略不再拦截模型调用；重新启用后立即恢复治理。
10. 自定义周期预算会按持久化周期窗口统计和拦截，不受页面默认月度窗口影响。
11. 软预算首次跨过 `alert_threshold_pct` 时写入 `alert` 账本事件，已经超过阈值后的后续调用不会重复刷屏。
