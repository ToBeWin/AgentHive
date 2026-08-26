# AgentHive 模型治理与接入

AgentHive 的模型接入必须经过 LLM Gateway。供应商 SDK、Agent、Channel、RAG 和 Skill 不得绕过网关直接调用模型。

## 供应商目录

默认模型目录覆盖以下类型：

| 类型 | Provider Key |
| --- | --- |
| 国际主流 | `openai`、`anthropic`、`gemini`、`azure_openai`、`bedrock`、`vertex_ai`、`mistral`、`cohere`、`xai` |
| 国内主流 | `qwen`、`deepseek`、`kimi`、`minimax`、`glm`、`doubao`、`baidu_qianfan`、`hunyuan`、`spark` |
| 聚合平台 | `litellm`、`openrouter`、`together`、`fireworks`、`groq`、`novita`、`siliconflow`、`ai302` |
| 私有/本地 | `openai_compatible`、`ollama`、`vllm`、`sglang`、`lmstudio`、`xinference`、`localai` |

除 `litellm` 使用 LiteLLM Adapter 外，其它默认通过 OpenAI-compatible Adapter 接入。供应商原生 SDK 只在 LiteLLM/OpenAI-compatible 无法表达能力时再增加。

## 连接测试

模型管理员可以在保存凭据前测试当前表单里的临时配置：

- `provider_key`：供应商标识，如 `qwen`、`deepseek`、`openai_compatible`。
- `adapter_type`：`litellm` 或 `openai_compatible`。
- `api_key`：本次测试使用的临时密钥，只在内存中参与探测，不写入数据库。
- `base_url`：本次测试使用的临时 OpenAI-compatible Endpoint。
- `model_key`：本次测试使用的模型标识。

如果请求包含临时 `api_key`、`base_url`、`adapter_type` 或 `model_key`，Gateway 会构造一次性的 `temporary_connection_test` 路由。该路由不会持久化部署，不会改变供应商状态，也不会把明文密钥写入用量账本或审计 metadata。

每次连接测试都会写入 `llm.connection_test` 审计事件。测试成功时记录为 `success`；返回 `ok=false`、策略拒绝、预算拒绝或部署不存在等情况记录为 `failure`。审计详情只保留 provider、model、deployment、routing、延迟、fallback 次数和诊断摘要；临时 API Key、临时 `base_url` 原文和底层错误中的敏感片段会被替换为占位符。

环境约束：

- `development` 环境允许 LiteLLM/OpenAI-compatible Adapter 返回 mock 响应，用于本地演示、前端联调和离线开发。
- 非 `development` 环境禁止 mock 模型响应。未配置真实 `base_url`/`api_key` 或部署显式 `mock=true` 时，真实对话会失败，连接测试返回 `ok=false`，并在 `diagnostics.mock_allowed=false` 中说明原因。
- 生产交付前必须完成至少一个真实模型部署的连接测试，确认 `live_network_call=true`，再启用对应 Agent 或 Channel。

安全约束：

- 保存和临时测试的 `base_url` 只允许 `http://` 或 `https://`，并会去除首尾空白和尾部 `/`。
- `owner_type` 只允许 `tenant`、`department`、`user`。`tenant` 凭据不得带 `owner_id`；`department` 和 `user` 凭据必须带 `owner_id`，用于后续部门/人员级模型密钥隔离。
- 保存部门或人员级凭据时，后端必须验证 `owner_id` 属于当前租户；用户归属还必须排除已软删除账号。前端下拉只改善体验，不能替代服务端租户校验。
- 模型 API Key 使用 Fernet 加密后存入 `llm_credentials.secret_ref`，该字段为 `TEXT`，避免长密钥加密后被截断。
- 审计日志只记录 provider、owner_type、价格、策略和连接测试诊断摘要等元数据，不记录明文 API Key、临时连接测试密钥或临时私有 Endpoint 原文。

运行时凭据选择优先级为：`user` 精确匹配 > `department` 精确匹配 > `tenant` 默认凭据。其它部门或其它用户的凭据不会作为 fallback 参与当前请求，避免密钥跨部门串用。

## 运行时治理上下文

所有进入 LLM Gateway 的 `tenant_id`、`user_id`、`department_id`、`agent_id`、`channel_id` 和 `conversation_id` 都必须由服务端生成或校验，不能信任客户端请求体、Agent metadata 或 Channel 原始 payload 中的同名字段。

- Chat 会话创建时会校验 Channel、Agent 实例和部门均属于当前租户；非租户管理员只能绑定自己所属部门。
- Channel 绑定 Agent 时，Chat/Agent 运行不得传入不一致的 `agent_id`；Agent 实例绑定部门时，运行上下文不得传入不一致的 `department_id`。
- Agent runtime 会在执行前规范化治理上下文，并在最终调用官方 Agent 前重写 canonical `agent_id`、`department_id`、`channel_id`，防止 `metadata.agent_context` 覆盖治理字段。
- LLM Gateway 的凭据选择、模型策略、预算匹配和用量账本只能使用 canonical context；自由文本 metadata 只作为诊断补充，不作为权限或费用归属依据。

## Fallback 诊断

未显式指定 `provider_key` 或 `deployment_id` 时，连接测试会按当前路由优先级逐个探测候选部署，直到第一个成功或全部失败。响应 `diagnostics` 中包含：

- `route_attempts`：每次尝试的供应商、模型、部署、路由、状态、延迟或错误。
- `fallback_attempt_count`：成功前经过的 fallback 次数。
- `selected_route_reason`：最终路由原因，如 `priority_route` 或 `temporary_connection_test`。

显式指定供应商或部署时，连接测试只在该范围内执行，不跨供应商降级。这可以避免管理员测试某个供应商失败时被其他备用模型掩盖。

## 费用与审计

真实模型调用、连接测试、失败、预算拒绝都会进入统一用量收集链路。业务费用以 AgentHive 数据库中的用量账本为准，LiteLLM 日志只作为底层协议与供应商调用的辅助来源。

模型用量账本和预算账本导出属于企业成本治理敏感操作。导出 `/api/v1/budgets/usage-ledger/export` 时写入 `budget.usage_ledger.export` 审计事件；导出 `/api/v1/budgets/budget-ledger/export` 时写入 `budget.budget_ledger.export` 审计事件。审计详情只记录导出格式、导出行数、limit 和筛选条件，例如用户、部门、成本中心、Agent、Channel、模型、状态、预算、事件类型和时间范围；不得复制导出的账本行、metadata、模型响应内容或错误明细。导出的 CSV/JSON 仍按租户过滤，并要求独立的 `budgets:export` 权限，不能只凭 `budgets:read` 批量导出费用明细。

模型策略支持启用和停用。停用策略不会进入运行时 Policy Engine 匹配，不会影响模型路由；状态变更会写入 `llm.policy.status.update` 审计事件，记录前后状态、作用范围和策略效果，便于现场回溯。

模型策略的作用范围支持 `tenant`、`department`、`cost_center`、`channel`、`agent` 和 `user`。`cost_center` 策略使用与预算和用量账本相同的归属解析逻辑：请求显式携带 `cost_center_id` 时优先使用；否则按用户部门绑定或主部门映射到成本中心。这样模型可用范围、预算控制和费用结算会落到同一个成本治理口径。

保存非租户级模型策略时，后端必须验证 `scope_id` 属于当前租户。校验范围包括部门、成本中心、人员、Agent 实例和 Channel；人员策略不得绑定已软删除账号。前端对象选择器只用于降低配置错误率，服务端仍是权限边界。

模型策略采用分阶段 fail-closed 语义：如果当前请求命中了任意策略作用范围，则必须命中一个允许当前模型或路由的 `allow` 策略才能继续；只命中 `deny` 或 allowlist 不匹配时会被拒绝并写入 `DENIED` 用量记录。未配置任何策略的开发/演示环境仍可使用默认路由，方便本地联调。

策略给出的 `default_routing_key` 或请求显式 `routing_key` 必须匹配真实 active deployment。策略路由键拼写错误、部署停用或不存在时，Router 返回错误，不会回退到其它候选部署，避免企业管理员误以为模型边界已生效。

内置价格目录覆盖默认模型部署，用于预算预估、调用前硬限制和调用后的基础费用计算。未知模型会落到保守默认价，生产交付时应在客户配置阶段确认实际合同价格；后续可由 `llm_model_prices` 或等价配置表覆盖内置价目表。

本地模型和私有运行时（如 `ollama`、`vllm`、`sglang`、`lmstudio`、`xinference`、`localai`）默认 token 单价为 0，因为模型调用不产生外部 API 账单。客户若希望核算 GPU、服务器或托管成本，应通过成本中心或自定义模型价目表补充内部成本。

模型价格管理 API：

- `GET /api/v1/models/prices`：列出当前模型价格表。
- `PUT /api/v1/models/prices`：按 `provider_key` + `model_key` 写入 USD 单价，字段为 `input_per_1k_tokens`、`output_per_1k_tokens`、`effective_from`、`effective_to`。

管理后台的“LLM 模型与供应商”页面提供价格覆盖表单，默认跟随当前选中的供应商和部署模型。交付现场可先配置供应商凭据，再录入客户合同价，最后通过预算页面验证部门/人员/Agent 的费用限制。

Gateway 构建时会读取当前生效的数据库价格，并优先于内置价目表。调用前预算预估和调用后用量入账都使用同一份价格目录。
