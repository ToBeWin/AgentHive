# AgentHive 权限与安全基线

本文档记录当前 AgentHive 私有化交付中的权限控制基线。完整产品规范仍以根目录 `AGENTS.md` 为准。

## 权限模型

AgentHive 使用租户内 RBAC 作为第一阶段权限模型：

- 用户登录后，JWT 中携带 `tenant_id`、`user_id` 和权限列表。
- 角色表 `roles.permissions` 是权限来源，租户管理员自动拥有全部权限。
- 后端接口必须通过 `require_permission`、`require_any_permission` 或 `require_all_permissions` 声明权限要求。
- `GET /api/v1/roles/permissions` 提供当前版本可分配权限目录，角色创建页面应从该接口读取权限值，避免前端和文档硬编码漂移。
- 前端导航根据登录用户权限隐藏不可访问模块；原型模式保留全量导航，便于设计和演示。

当前权限粒度覆盖用户、部门、Agent、知识库、模型、预算、审计、License 和系统诊断。后续资源级权限、部门级数据范围和 ABAC 条件应接入同一依赖入口，不应在业务代码里分散硬编码。

组织治理列表（部门、用户、角色、成本中心）读取失败时必须返回服务不可用错误，不得把数据库或迁移故障伪装为空列表。管理后台应展示 API notice 并允许重试，避免管理员在故障期间误判为“尚未配置”。

## 数据范围

菜单/接口权限只代表用户可以进入某类功能，不能代表用户可以访问该租户下所有资源。AgentHive 对需要业务隔离的资源继续叠加数据范围判断。

当前已落地的数据范围：

| 资源 | 可见性 | 规则 |
| --- | --- | --- |
| 知识库 | `tenant` | 租户内有 `knowledge:read` 的用户可读。 |
| 知识库 | `department` | 仅绑定部门成员或租户管理员可读；写入要求有交集部门范围。 |
| 知识库 | `private` | 仅 owner 或租户管理员可读写。 |
| Agent 实例 | `tenant` | 租户内有 `agents:read` 的用户可读；写入仍要求 owner/creator 或租户管理员。 |
| Agent 实例 | `department` | 仅实例绑定部门成员或租户管理员可读写。 |
| Agent 实例 | `private` | 仅 owner/creator 或租户管理员可读写。 |
| 媒体生成任务 | `owner/department` | 租户管理员可治理全部任务；普通用户只能查看、执行、轮询、取消、重试和下载自己创建的任务，或 `department_id` 属于自己部门成员关系的部门任务。 |

Agent 运行时如果通过 `context.agent_id` 引用 Agent 实例，也必须通过同一可见性策略；不可访问的 Agent 实例不得被用于加载默认模型、默认知识库或 system prompt。创建或更新 Agent 实例时，如果配置了 `knowledge_base_id` / `knowledge_base_ids`，后端必须立即校验这些知识库存在、属于当前租户，并且当前操作者具备读取数据范围，避免保存不可运行的 Agent 配置。Chat、Channel 和 Agent runtime 传入 LLM Gateway 前必须使用服务端 canonical context；客户端或 metadata 中伪造的 `department_id`、`agent_id`、`channel_id` 不得覆盖已校验的会话、Channel 或 Agent 实例绑定。

知识库删除、文档删除和文档重新入库属于写入治理操作，必须同时满足 `knowledge:write` 和对应知识库写入数据范围。删除采用软删除并保留审计日志，后端会尝试清理 MinIO 对象、RAGFlow 索引和 pgvector chunk，但不会删除历史审计、对话或费用账本。重新入库保留 MinIO 原文对象，只清理旧索引和 chunk 后再次触发 ingest，并记录 `knowledge.document.reingest` 审计事件。
知识库文档数量、容量检查、删除后的统计刷新和检索范围必须显式按 `tenant_id` 过滤，即使知识库 ID 理论上全局唯一，也不能依赖这一点作为多租户隔离边界。

## 后端判断顺序

```text
缺失/无效 Token → 401
tenant.admin → 允许
显式权限命中 → 允许
权限不满足 → 403
资源数据范围不满足 → 403
```

生产环境缺失 `Authorization` 必须返回 401。开发环境允许无 Token fallback，用于本地联调；该行为不得作为生产验收依据。

## 密码与 Token

- 用户密码必须通过 `bcrypt-sha256$` 格式保存：先对 UTF-8 密码做 SHA-256 预哈希，再使用 bcrypt 加盐哈希，避免 bcrypt 72 字节输入截断问题。
- 当前 bcrypt cost 为 12。后续提高 cost 时，登录成功后应通过 `password_hash_needs_rehash` 自动升级用户 hash，不要求客户集中重置密码。
- 未知格式、损坏 hash 或不受支持的历史 hash 必须安全失败，不得抛出原始异常或回退到明文比较。
- 成功登录必须记录 `auth.login` 审计事件；有效租户内的失败登录必须记录 `auth.login_failed`，状态为 `failure`。
- 登录失败响应必须保持统一文案，不得向调用方泄露租户、邮箱、用户状态或密码哪一项错误。具体原因只允许进入租户内审计日志。
- 登录失败会触发运行时节流：默认同一租户+邮箱或同一租户+IP 在 15 分钟内失败 5 次后返回 429。成功登录会清理对应失败计数。
- 登录失败节流是单体运行时保护，重启后会清空；审计日志仍是追溯撞库、停用账号尝试和异常来源的权威证据。
- JWT 由 AgentHive 签发，必须包含 `sub`、`tenant_id`、`permissions`、`iat`、`exp` 和 `iss=AgentHive`，受保护接口只接受 `Bearer` Token。
- `POST /api/v1/auth/refresh` 会基于当前 Bearer Token 重新加载用户状态和权限后签发新 access token；停用用户、删除用户或停用租户不得刷新。
- `POST /api/v1/auth/logout` 当前是审计型退出，会记录 `auth.logout` 并由前端清理本地 token；如果后续需要强制下线或多设备管理，应增加持久化 session/Token 黑名单表。
- 管理员可通过 `PATCH /api/v1/users/{user_id}/status` 启用或停用用户。停用用户会阻止新登录、refresh 和后续受保护业务接口访问，并记录 `org.user.status.update` 审计事件；管理员不能停用自己的账号。当前业务接口会在 RBAC 依赖层重新校验用户和租户活跃状态；如客户后续需要设备列表、单设备下线或 refresh token 轮换，应增加持久化 session/Token 黑名单能力。
- 管理员可通过 `PATCH /api/v1/users/{user_id}/password` 重置用户密码。新密码必须满足当前密码长度策略，后端只保存重新计算后的 `bcrypt-sha256$` hash，并记录 `org.user.password.reset` 审计事件；审计详情不得包含明文密码、密码 hash 或任何可还原凭据。
- 前端 API 客户端对受保护请求的 401 做统一处理：清理本地会话并回到登录页；登录、初始化等匿名接口的 401 不触发会话失效事件。
- 生产环境必须替换默认 `AGENTHIVE_SECRET_KEY`，并通过客户自己的密钥管理或配置管理系统保存。

## 前端展示规则

前端仅做体验层权限感知，不作为安全边界：

- `navItems.requiredAnyPermission` 声明页面入口所需权限。
- `lib/permissions.ts` 统一判断 `tenant.admin` 和普通权限。
- 如果当前页面因权限变化不可见，应用会回落到第一个可访问页面。
- License 页面允许 `license:read` 用户查看状态和导出 activation request；激活 signed license、注销当前 License 等写操作必须要求 `license:write`，前端应隐藏或禁用对应控件，后端仍以 `require_permission(Permission.LICENSE_WRITE)` 为准。
- License 激活成功、失败、替换和注销都必须进入审计日志。激活失败事件使用 `license.activate` + `status=failure`，只记录 HTTP 状态码、失败原因、输入格式和在线/离线激活模式，不得记录 License Key、signed license 原文或 activation code。
- 任何敏感操作仍必须以后端权限校验为准。

## 审计脱敏

- 审计日志可以记录业务上下文，但不得把 API Key、Authorization、Token、密码、License Key、激活码、私钥或加密 secret 原文暴露给管理后台。
- 审计写入服务和查询服务都会对 `details` 进行递归脱敏；包含 `secret`、`api_key`、`authorization`、`password`、`license_key`、`activation_code`，以及认证语义的 `token` 字段统一返回 `[REDACTED]`。
- `GET /api/v1/audit-logs/export` 使用独立的 `audit:export` 权限，导出的 CSV/JSON 必须复用同一脱敏路径，不得绕过管理后台展示层的脱敏规则。每次审计日志导出还必须写入 `audit.logs.export` 审计事件，只记录导出格式、行数、limit 和筛选条件，不得复制导出的日志行、details、用户代理原始敏感值或任何未脱敏内容。
- 管理后台审计列表应使用后端 `limit/offset` 分页浏览租户内事件；CSV/JSON 导出按当前筛选条件导出较大范围结果，仍必须保持租户隔离、独立权限和统一脱敏。
- `GET /api/v1/budgets/usage-ledger/export` 和 `GET /api/v1/budgets/budget-ledger/export` 使用独立的 `budgets:export` 权限。`budgets:read` 只允许查看预算和账本分页数据，不应默认允许批量导出部门、人员、成本中心或模型费用明细。
- `GET /api/v1/system/diagnostics` 使用独立的 `system:diagnostics` 权限。诊断包包含 health、readiness、system info 和交付摘要，只能导出已脱敏 JSON；每次导出必须写入 `system.diagnostics.export` 审计事件，审计详情只记录 schema、readiness 状态、delivery 状态、阻塞/警告数量和组件数量，不得复制诊断明细、环境变量、URL 凭据或任何密钥。
- 首次安装生成的租户管理员系统角色包含 `budgets:export`；普通角色必须在角色权限中显式配置该权限后才能导出费用账本。管理后台角色创建表单应展示权限目录，允许管理员点选 `budgets:export` 等细粒度权限。
- Analytics 看板使用独立的 `analytics:read` 权限，不应复用 `budgets:read`。预算管理员可以管理预算但不一定能查看全局经营分析；经营分析人员可以查看模型、部门、人员、Agent 维度用量趋势，但不应默认获得预算写入或批量导出权限。
- 审计查询和导出必须支持 `created_from` / `created_to` 时间范围筛选，用于按事故窗口、交付验收窗口或合规审查周期定位事件；时间范围筛选不得绕过租户隔离和权限校验。
- 管理后台审计详情面板只允许展示 API 返回的脱敏后事件对象；复制 JSON、表格展示和导出必须共享同一脱敏数据源，不能重新请求或拼接未脱敏原始字段。
- 模型用量字段如 `max_tokens`、`total_tokens`、`token_limit` 不是认证密钥，不应被脱敏，否则会影响成本治理审计。
- 新增审计事件时仍应优先记录业务标识、scope、状态和脱敏摘要，不应把敏感原文传给审计服务。
- Agent 模块安装、启用、停用的成功和失败都必须进入审计日志。成功事件应记录 `module_key`、`previous_state`、`next_state` 和操作结果消息；未授权、License 过期、缺少依赖或模块不存在等失败事件应记录为 `status=failure`，保留 `module_key`、HTTP 状态码和脱敏失败原因，便于私有化授权争议和现场交付排查。
- 官方 Agent 运行成功必须记录 `agent.run` 审计事件。该事件用于回答“谁在什么时候运行了哪个 Agent/实例、走了哪个模型路由、消耗了多少 Token/费用、使用了哪些知识库”，与 `llm_usage` 账本互补：`llm_usage` 是模型调用和成本事实来源，`agent.run` 是业务操作审计事实来源。
- `agent.instance.create` 和 `agent.instance.update` 在创建 active 实例或把实例激活为 active 时，审计详情必须包含 License 门禁证据：`license_gate`、`license_gate_reason`、`licensed`、`installed`、`enabled`。这样客户现场可以追溯某个 Agent 实例上线时是否满足当前 License、模块安装和启用状态。
- `agent.run` 审计详情必须包含 `agent_key`、`model_key`、`routing_key`、`max_tokens`、License 门禁结果、Agent 实例摘要、知识库检索摘要、来源数量和用量摘要；可以记录 `context_keys`、`department_id`、`channel_id`、`conversation_id` 等治理标识，但不得记录用户原始输入、完整 prompt、知识库片段正文或模型完整回答。
- Agent 绑定知识库运行时默认启用严格知识库守门。检索结果为空、缺少可评分来源或低于置信阈值时，运行时必须返回安全转人工/补充资料提示并跳过模型调用，避免官方 Agent 在无证据场景下编造答案。确需灰度验证时，可在服务端校验后的 `context.knowledge_guardrail_mode` 设置 `advisory` 仅记录诊断但继续调用模型，或设置 `off` 关闭守门；生产默认不得关闭。
- 知识库守门结果必须写入 `agent.run` 审计详情的知识库摘要和响应 metadata，包括 `mode`、`triggered`、`skipped_model_call`、`reason` 和置信诊断。守门跳过模型调用时，用量摘要应为 0 Token、0 成本，不得生成伪造的模型账单。
- Chat 会话和消息必须同时做租户隔离与会话访问控制。租户管理员可查看本租户全部会话；普通用户只能访问自己创建/归属的会话，或 `department_id` 属于自己部门成员关系的部门会话。消息列表和发送消息都必须先校验会话访问权，不能只按 `conversation_id + tenant_id` 查询。
- 媒体生成任务包含商品参考图、原始视频素材、生成产物和供应商任务状态，必须同时做租户隔离与任务访问控制。列表、详情、事件时间线、执行、入队、轮询、重试、取消和输出下载都必须复用同一访问规则；知道 `job_id` 或 MinIO object key 不等于拥有访问权。
- 媒体 Provider webhook 必须 fail closed：`job_id` 回调要校验 `provider_key` 和已有 `external_job_id` 是否匹配；仅凭 `external_job_id` 回调时，必须结合 `provider_key` 过滤并且只允许唯一匹配，重复匹配返回 409，不得更新任意第一条任务。已定位到具体任务后的无效状态迁移、终态冲突和输出归档失败必须写入 `media.generation.provider_callback_failed` 失败审计，但不得记录输出 URL、base64 内容或供应商密钥。
- 媒体输出归档下载 Provider URL 时必须防 SSRF。只允许 `http` / `https`，禁止 localhost、私网、回环、链路本地、保留、多播和未指定地址；域名解析后的每个地址都必须是公网地址。被阻断的 URL 不得写入 MinIO，也不得在审计详情中泄露原始 URL 或 base64 内容。
- 任何基于部门成员关系的访问判断都必须把 `user_departments` 与 `departments` 关联，并校验 `departments.tenant_id == principal.tenant_id`；不能只按 `user_id` 查询部门 ID。这样可以抵御历史导入、租户迁移或异常数据造成的跨租户部门授权污染。

## 验收检查

交付前至少确认：

1. 普通用户没有对应权限时，API 返回 403。
2. 生产环境无 Token 请求受保护 API 返回 401。
3. 租户管理员可以访问全部受控接口。
4. 前端登录普通用户后，不展示无权限模块入口。
5. 审计、预算、License、模型配置等高风险模块均有后端权限依赖。
6. 普通用户无法读取或运行其他用户的 private Agent 实例。
7. 普通用户无法创建或绑定到自己部门范围外的 department Agent 实例。
8. Agent 实例默认知识库绑定会在创建/更新时校验知识库访问范围，不能保存跨租户、已删除或无权读取的知识库 ID。
9. 直接运行官方 Agent、Chat 绑定 Agent、Channel 路由 Agent 后，都能在模型用量账本看到成本记录，并在审计日志看到 `agent.run` 或对应上层路由事件；审计详情只包含治理摘要，不包含用户原始输入和敏感凭据。
10. 知识库检索无匹配或低置信时，严格守门会跳过模型调用并返回安全提示；advisory 模式会继续调用模型但保留守门诊断。
11. 普通用户无法查看、调度或下载其他用户的私有媒体生成任务；部门成员可以访问本部门任务，租户管理员可以访问全部任务。
12. 媒体 Provider webhook 在 `provider_key` 不匹配、已有 `external_job_id` 不匹配或 `external_job_id` 匹配多条任务时返回 409，且不会结算预算或更新任务状态；已定位任务上的失败回调必须有 `media.generation.provider_callback_failed` 审计记录。
13. 媒体输出归档会拒绝内网 URL、localhost、私网 IP 和非 `http` / `https` scheme；拒绝后任务保持原状态，不产生对象存储写入。
