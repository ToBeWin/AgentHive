# AgentHive 私有化离线 License 交付指南

本文档面向 AgentHive 的销售、交付、实施、运维和客户管理员，说明私有化部署场景下的 License 交付边界、离线激活流程、模块授权、重复部署防护和故障处理规范。

AgentHive 商业交付优先采用私有化买断模式。客户购买的是指定授权版本、指定部署实例和已授权模块的使用权；后续大版本升级、新增 Agent 模块、高级部署形态、定制功能和长期运维支持，应按合同另行授权或续费。

## 1. 交付边界

### 1.1 授权对象

每份 License 必须绑定到一个明确的 AgentHive 私有化部署实例，建议至少包含以下字段：

| 字段 | 说明 |
| --- | --- |
| `product` | 固定为 `AgentHive`，防止授权文件被其他产品复用。 |
| `tenant_id` | 客户租户 ID，用于业务侧租户归属和审计。 |
| `deployment_id` | 商业授权部署 ID，由厂商在签发前确定。 |
| `install_id` | 客户环境首次安装生成的持久安装身份。 |
| `machine_fingerprint_hash` | 客户部署环境机器指纹 Hash，不保存原始硬件信息。 |
| `allowed_modules` | 已授权 Agent 模块，例如 `agent.customer_service`。 |
| `allowed_features` | 已授权平台能力，例如 Channel、预算治理、高可用部署等。 |
| `max_users` | 授权最大用户数。 |
| `max_agents` | 授权最大 Agent 数。 |
| `max_kb_size_gb` | 授权知识库对象与文档容量，按 GiB 口径执行运行时限制。 |
| `maintenance` | 可获得补丁、升级或维护支持的截止范围。 |
| `expires` | License 使用有效期；永久授权也应明确适用的大版本范围。 |

`max_users`、`max_agents` 和 `max_kb_size_gb` 不代表 AgentHive 必须按人数、实例数或容量逐项收费；它们是版本和部署规模边界。销售可以采用一次性买断报价，同时为不同公司规模、部署形态、模块包、知识库容量和后续扩容保留可执行的技术边界。

### 1.2 商业边界

- License 只授权合同约定的客户、租户、部署实例和模块，不自动包含未购买模块。
- 同一客户的测试、预生产、生产环境应分别签发 License，或在合同中明确环境数量和用途。
- 创建用户、创建 Agent 实例、上传知识库文档、安装/启用 Agent 模块、运行官方 Agent 时，后端必须执行 License 运行时校验；不得只依赖前端展示隐藏入口。
- 交付包可以包含产品运行所需的公钥、镜像、安装脚本、文档和默认配置模板。
- 交付包不得包含 License 签发私钥、厂商内部签发脚本的私有配置、客户无权使用的模块激活文件。
- 客户替换服务器、迁移机房、调整部署拓扑、恢复备份到新环境时，可能触发重新激活或人工复核。

### 1.2.1 模块选装约束

Agent 模块选装不是简单的前端开关，后端必须同时检查三类条件：

- `allowed_modules`：当前 License 是否包含该 Agent 模块。
- `allowed_features`：该模块声明的 `required_features` 是否全部授权，例如高级预算治理、离线激活、Channel 能力。
- `dependencies`：该模块依赖的其它 Agent 模块是否已安装；启用模块时依赖模块必须已启用。

模块目录 API 会返回 `missing_features` 和 `missing_dependencies`，管理后台应直接展示这些阻塞原因。销售可以据此设计基础包、行业包、高级包和加购模块；交付工程师也可以在客户现场快速判断是“License 未包含”、“功能未授权”，还是“依赖模块未安装/启用”。

### 1.3 技术边界

AgentHive 运行时只负责验证已签名 License，不负责生成生产 License。生产 License 必须由厂商在受控环境中使用私钥签发。

运行时约定：

| 环境变量 | 用途 |
| --- | --- |
| `AGENTHIVE_LICENSE_PUBLIC_KEY_PATH` | AgentHive 运行时验证 License 签名的 Ed25519 公钥文件路径。 |
| `AGENTHIVE_INSTALL_ID_PATH` | 每套部署持久安装身份文件路径。该文件必须随客户部署数据持久化。 |

签名算法采用 Ed25519。客户部署包只需要公钥；私钥只存在于厂商签发环境。

## 2. 离线激活流程

AgentHive 必须支持完全离线激活，适用于客户内网、专有云、无公网出口或合规隔离环境。

### 2.1 角色分工

| 角色 | 职责 |
| --- | --- |
| 客户管理员 | 部署 AgentHive、下载 activation request、上传或粘贴 signed license。 |
| 交付工程师 | 指导客户完成安装、收集授权请求、确认部署信息和合同范围。 |
| 厂商授权管理员 | 在受控环境中使用私钥签发 License，维护签发记录和密钥安全。 |
| 厂商运维/支持 | 处理迁移、扩容、过期、模块加购和故障排查。 |

### 2.2 标准流程

1. 客户完成 AgentHive 私有化部署。
2. AgentHive 首次启动时读取 `AGENTHIVE_INSTALL_ID_PATH`；如果文件不存在，则生成新的 `install_id` 并写入该路径。
3. 客户管理员进入后台 License 页面，下载 activation request。
4. activation request 应包含 `product=AgentHive`、`tenant_id`、`deployment_id`、`install_id`、`machine_fingerprint_hash`、版本信息和请求时间。
5. 交付工程师核对合同、客户名称、部署用途、授权模块、用户数、Agent 数、维护期和到期时间。
6. 厂商授权管理员在厂商受控环境使用 `license_issue.py` 和 Ed25519 私钥签发 signed license。
7. 客户管理员在后台粘贴或上传 signed license。
8. AgentHive 使用 `AGENTHIVE_LICENSE_PUBLIC_KEY_PATH` 指向的公钥验证签名、产品、部署身份、安装身份、机器指纹、有效期和授权范围。
9. 验证通过后，AgentHive 激活已授权功能和模块，并写入审计日志。

客户管理员导出 activation request 时，后端会写入
`license.activation_request.export` 审计事件。事件记录导出人、请求
ID、request hash、部署 ID、安装 ID、指纹算法和机器指纹 Hash 是否存在，
但不记录完整 `request_code`、signed license、激活码、私钥或原始硬件信息。
这条审计用于追踪“谁在什么时候为哪套部署发起过离线授权申请”。

如果激活新 License 时已有活跃 License，旧 License 会被置为 `inactive`，相关激活记录会被关闭，并额外写入 `license.supersede` 审计事件。该事件记录旧 License、新 License、状态变化和关闭的 activation 数量，用于续签、扩容、模块加购或交付争议排查。

客户管理员可以在后台执行 License 注销，用于迁移、重装、合同变更或交付排查前解除当前部署的授权状态。注销操作必须二次确认，并写入审计日志；即使当前没有活跃 License，也应记录一次 `license.deactivate` 审计事件，便于追踪现场操作。

### 2.3 签发命令示例

厂商首次建立签发环境时生成 Ed25519 密钥对：

```bash
cd backend
python scripts/license_issue.py generate-keypair \
  --private-key ./secure/agenthive_license_private.pem \
  --public-key ./secure/agenthive_license_public.pem
```

交付给客户部署包的只能是 `agenthive_license_public.pem`。客户生产环境应通过 `AGENTHIVE_LICENSE_PUBLIC_KEY_PATH` 指向该公钥，例如 Docker Compose 默认路径：

```text
/data/agenthive/license_public.pem
```

收到客户后台导出的 activation request 后，厂商在受控签发环境生成 signed license：

```bash
cd backend
python scripts/license_issue.py issue \
  --activation-request ./requests/customer-prod-activation-request.json \
  --private-key ./secure/agenthive_license_private.pem \
  --output ./issued/customer-prod-license.json \
  --customer-name "客户公司名称" \
  --license-type standard \
  --all-official-modules \
  --standard-features \
  --max-users 80 \
  --max-agents 12 \
  --max-kb-size-gb 20 \
  --maintenance-until 2027-06-30T23:59:59+08:00
```

签发前可列出当前版本内置的官方 Agent 模块，核对合同、报价单和 `--module` 参数：

```bash
python scripts/license_issue.py list-modules
python scripts/license_issue.py list-modules --format json
```

`license_issue.py issue` 会在生成 signed license 前校验所选模块的 `required_features` 是否全部包含在 `allowed_features` 中。例如 `agent.finance` 和 `agent.data_analyst` 需要 `feature.model_budget`；若缺失，签发会失败并提示补充 `--feature` 或使用 `--standard-features`，避免交付出“模块已买但无法启用”的授权文件。

如只授权部分模块，不使用 `--all-official-modules`，改为多次传入 `--module`：

```bash
python scripts/license_issue.py issue \
  --activation-request ./requests/customer-prod-activation-request.json \
  --private-key ./secure/agenthive_license_private.pem \
  --output ./issued/customer-prod-license.json \
  --customer-name "客户公司名称" \
  --module agent.customer_service \
  --module agent.copywriting \
  --feature feature.agent_catalog \
  --feature feature.license_offline_activation
```

该工具也支持 `--expires-at`、`--not-before`、`--metadata-json` 和 `--base64`，用于限时授权、延迟生效、写入订单号或生成适合粘贴的单行授权内容。

### 2.4 activation request 管理

activation request 不是 License，不代表授权已生效。它用于证明客户部署环境的身份，并向厂商发起离线签发请求。

交付时应注意：

- activation request 可以通过工单、加密邮件、客户交付群文件或合同约定介质传递。
- request 中不应包含明文硬件序列号、MAC 地址、磁盘序列号等原始敏感信息，只传递 Hash 或派生摘要。
- request 应包含生成时间，厂商可拒绝过旧请求，避免客户使用历史环境信息重复申请。
- 每次签发应保留 request 摘要、签发人、签发时间、合同或订单编号、License 摘要和客户确认记录。

### 2.5 signed license 管理

signed license 是客户激活 AgentHive 的正式授权文件。客户应将其作为重要交付资产保存，厂商也应保留签发记录。

建议 signed license 包含：

- 授权主体：客户名称、租户 ID、部署 ID。
- 部署绑定：install ID、机器指纹 Hash。
- 授权范围：用户数、Agent 数、知识库容量、模块、功能、Channel、维护期和到期时间。
- 签名信息：签名算法、key ID、签发时间、签发人或签发系统标识。
- 版本约束：适用的 AgentHive 大版本或授权版本范围。

## 3. 密钥保管规范

### 3.1 私钥

Ed25519 私钥是 AgentHive 商业授权体系的最高敏感资产。

必须遵守：

- 私钥只能存放在厂商受控签发环境，不得进入客户部署包。
- 私钥不得写入 Docker 镜像、Git 仓库、CI 日志、安装脚本、`.env.example`、客户文档样例或任何客户可见介质。
- 生产签发私钥应限制访问人员，启用最小权限、操作审计和备份加密。
- 生产签发应使用专用机器、专用账号或密钥管理系统，避免在个人开发机随意签发。
- 私钥泄露、疑似泄露或离职交接风险出现时，应立即轮换 key ID，停止旧私钥签发，并评估是否需要重新签发客户 License。

禁止事项：

- 禁止为了“方便客户本地自助激活”把私钥放进客户服务器。
- 禁止在客户现场使用未受控 U 盘、聊天工具明文文件或个人笔记保存私钥。
- 禁止让实施工程师持有生产私钥，除非其角色已被正式纳入授权管理员并接受同等审计。

### 3.2 公钥

公钥用于客户环境验证 signed license，可随部署包交付。

建议：

- 通过 `AGENTHIVE_LICENSE_PUBLIC_KEY_PATH` 指定公钥路径。
- 公钥文件应只读挂载或受配置管理系统管理。
- 公钥轮换时应保留兼容策略，例如允许一段时间内同时信任旧 key ID 和新 key ID。
- 客户不得自行替换公钥来绕过授权；运行时应记录公钥摘要和 License key ID，便于审计。

## 4. 重复部署防护

AgentHive License 应防止同一个部署包被复制到多套环境重复安装。

### 4.1 绑定策略

运行时验证应同时检查：

- `product` 必须为 `AgentHive`。
- `deployment_id` 必须与授权签发记录一致。
- `install_id` 必须与 `AGENTHIVE_INSTALL_ID_PATH` 中的持久身份一致。
- `machine_fingerprint_hash` 必须与当前环境计算结果匹配或落在允许的迁移策略内。
- License 签名必须由受信公钥验证通过。
- License 未过期、未被吊销，且维护期满足当前升级要求。

其中 `install_id` 是防止拷贝部署包重复激活的关键。每套部署首次启动生成唯一 `install_id`；如果客户复制容器镜像但未复制持久化安装身份，新的环境会生成不同 `install_id`，原 License 不应通过验证。

License 状态接口会同时返回 License 绑定身份和当前运行身份：

| 字段 | 说明 |
| --- | --- |
| `deployment_id` / `install_id` / `machine_fingerprint_hash` | License 记录绑定的部署身份。 |
| `runtime_deployment_id` / `runtime_install_id` / `runtime_machine_fingerprint_hash` | 当前运行环境实际安装身份。 |
| `verification_issues` | 运行时校验问题列表。 |

常见 `verification_issues`：

| Issue | 含义 |
| --- | --- |
| `deployment_id_mismatch` | License 绑定的部署 ID 与当前运行环境不一致。 |
| `install_id_mismatch` | License 绑定的安装 ID 与当前运行环境不一致，常见于复制部署包或丢失持久化安装身份。 |
| `machine_fingerprint_mismatch` | License 绑定的机器指纹与当前运行环境不一致。 |
| `license_expired` | License 已过期。 |
| `no_active_license` | 当前租户没有有效 License。 |

### 4.2 持久化要求

`AGENTHIVE_INSTALL_ID_PATH` 必须放在客户部署的持久化卷中，而不是容器临时文件系统。否则容器重建后会生成新的 `install_id`，导致 License 失效。

交付检查项：

- 确认 `AGENTHIVE_INSTALL_ID_PATH` 挂载到持久化目录。
- 确认备份策略包含安装身份文件。
- 确认灾备恢复时不会把同一个安装身份同时运行在两套生产环境。
- 确认迁移到新服务器前先走迁移授权流程，而不是直接复制生产数据和 License。

### 4.3 迁移与恢复

正常迁移流程：

1. 客户提交迁移申请，说明原部署、新部署、迁移原因和时间窗口。
2. 交付或支持团队确认合同允许迁移。
3. 客户在新环境生成 activation request。
4. 厂商签发新的 signed license。
5. 客户在新环境激活，并停用旧环境。
6. 厂商保留迁移记录，必要时将旧激活标记为 revoked。

灾难恢复场景下，如果恢复的是同一套持久化数据和同一安装身份，且机器指纹策略允许，License 可以继续使用；如果恢复到不同硬件或新集群，应重新申请激活。

## 5. 升级与模块授权

### 5.1 版本升级

License 中的 `maintenance` 字段用于控制客户是否有权获得补丁、升级包或维护支持。

建议规则：

- 补丁版本可在维护期内升级。
- 大版本升级需要检查合同和 License 版本范围。
- 维护期已过但 License 未过期时，客户可继续使用已授权版本，但不自动获得新版本升级权。
- 升级前应备份数据库、对象存储、安装身份文件和当前 signed license。
- 使用新 signed license 升级或续费后，应在审计日志中确认存在 `license.activate`；如果覆盖了旧授权，还应存在对应的 `license.supersede`。

生产升级脚本会在启动新版本和执行迁移前运行 License 升级预检：

```bash
docker compose --env-file .env -f docker-compose.yml run --rm --no-deps backend \
  python scripts/check_license_upgrade.py --target-version "${AGENTHIVE_VERSION:-0.3.0-alpha.1}"
```

预检要求当前活跃租户 License 为 `active`，部署 ID、安装 ID、机器指纹与运行环境一致，License 未过期，且 `maintenance_until` 晚于当前时间。未通过时，`scripts/upgrade.sh` 会以非 0 状态退出，交付或销售应先签发续费/升级 signed license，再继续升级。

### 5.2 Agent 模块授权

AgentHive 支持 Agent 模块选装和授权。模块是否可见、可安装、可启用，应由 License 中的 `allowed_modules` 控制。

后台 License 授权范围页必须同时展示授权状态和租户实际安装状态：已授权但尚未安装的模块显示为 `not_installed`，已启用模块显示为 `enabled`，License 过期时原授权模块显示为 `expired` 且不可继续启用。这样销售、交付和客户管理员可以清楚区分“合同已买”“平台已装”“当前可用”三件事。

Agent 实例状态也必须受到模块授权约束。创建或更新实例时，只要保存后的状态是 `active`，后端都必须重新验证当前 License 为 active、模块在 `allowed_modules` 中、租户已安装并启用该模块。未通过时应直接拒绝保存，而不是允许后台出现“已上线但运行时才失败”的假 active 状态。

Agent 运行时还必须重新校验实例绑定关系：会话或 Channel 指向的 `agent_id` 必须属于当前租户、当前用户可读、状态为 `active`，并且实例的 `agent_key` 与 `module_key` 必须分别匹配被调用的官方 Agent 和该 Agent 声明的 required module。任何错绑、旧数据迁移残留或手工修库造成的不一致都应返回 409/403，不能退化为只按前端选择或会话 metadata 信任。

禁用模块、License 注销、License 过期、License 身份不匹配，或新 License 移除了原模块授权后，系统必须立即执行 Agent 实例状态同步：所有不再满足“active License + 模块已授权 + 租户已启用模块”的 active 实例会被自动改为 `disabled`。历史实例、对话、审计和费用记录保留；系统不自动恢复这些实例为 `active`，即使后续重新授权或重新启用模块，也必须由管理员显式重新启用，避免越权恢复。

自动下线必须写入审计日志：

- `agent.instance.runtime_disable`：逐个记录被下线的 Agent 实例、模块、原状态、新状态和触发原因。
- `agent_module.disable`：记录 `disabled_agent_instance_count`，说明禁用模块影响了多少 active 实例。
- `license.activate` / `license.deactivate`：记录 `disabled_agent_instance_count`，说明 License 变更影响了多少 active 实例。

示例模块命名：

| 模块 | 建议标识 |
| --- | --- |
| 电商客服助手 | `agent.customer_service` |
| HR简历筛选助手 | `agent.hr_screening` |
| 文案创作助手 | `agent.copywriting` |
| 爆款内容拆解助手 | `agent.content_analysis` |
| 项目汇报助手 | `agent.report_writer` |
| 新品设计辅助 | `agent.product_design` |
| 财务效率助手 | `agent.finance` |
| 店铺运营助手 | `agent.store_operations` |
| 数据分析助手 | `agent.data_analyst` |

模块加购流程：

1. 客户确认新增模块、用户范围、部署实例和服务期限。
2. 商务或交付生成变更单。
3. 厂商基于原 deployment ID、install ID 和机器指纹重新签发 License。
4. 客户上传新 signed license。
5. AgentHive 刷新授权范围，新增模块进入可安装或可启用状态。

### 5.3 平台功能授权

`allowed_features` 用于授权非 Agent 模块的能力，例如：

- 企业微信、钉钉、飞书、网页 Widget 等 Channel。
- 模型预算、成本中心、审计增强、报表导出。
- 高可用部署、监控集成、备份恢复工具。
- 行业模板、MCP Server、私有模型接入能力。

功能授权应可审计。客户启用未授权功能时，前端应提示授权不足，后端应拒绝执行。

Channel 类型必须按功能键单独授权。管理后台创建 Channel 前会读取 License 授权范围，后端 `channel.create` 也会再次校验，不能只依赖前端隐藏入口。

| Channel 类型 | `allowed_features` 标识 | 说明 |
| --- | --- | --- |
| Web Widget | `channel.web_widget` | 可嵌入官网、内网门户或客户服务页面的网页聊天入口。 |
| REST API | `channel.rest_api` | 服务端到服务端的入站消息接入，适合自研系统和集成桥接。 |
| 企业微信 | `channel.wecom` | 企业微信内部助手、客服或应用回调接入。 |
| 钉钉 | `channel.dingtalk` | 钉钉机器人、工作台或事件回调接入。 |
| 飞书/Lark | `channel.feishu` | 飞书/Lark 企业应用回调接入。 |

签发 License 时如果客户只购买了 Web Widget 和 REST API，则 `allowed_features` 应只包含这两个 Channel 标识。客户后续加购企业微信、钉钉或飞书时，应重新签发 License，而不是直接修改数据库。

## 6. 故障排查

### 6.1 常见问题

| 现象 | 可能原因 | 处理建议 |
| --- | --- | --- |
| License 签名验证失败 | 公钥错误、License 文件损坏、使用了非生产签发私钥 | 核对 `AGENTHIVE_LICENSE_PUBLIC_KEY_PATH`、公钥 key ID、重新获取 signed license。 |
| 提示 product 不匹配 | License 不是为 AgentHive 签发 | 使用 `product=AgentHive` 的正式 License 重新激活。 |
| 提示 install ID 不匹配 | 客户更换了 `AGENTHIVE_INSTALL_ID_PATH`、容器重建丢失持久化文件、复制到新环境 | 恢复原安装身份文件；如确为迁移，重新提交 activation request。 |
| 提示机器指纹不匹配 | 服务器、虚拟机、磁盘、集群节点或部署拓扑变化 | 按迁移流程重新签发，或由支持团队按合同判断是否放行。 |
| License 过期 | `expires` 已到期 | 续费或签发新 License。 |
| 无法升级 | `maintenance` 已过期或版本范围不包含目标版本 | 续签维护或购买升级授权。 |
| 模块不可安装 | `allowed_modules` 未包含对应模块 | 核对合同和 License，走模块加购或重新签发。 |
| 用户数或 Agent 数达到上限 | `max_users` 或 `max_agents` 限制触发 | 清理停用对象或购买扩容授权。 |
| 激活后仍显示未授权 | 服务未刷新 License、缓存未更新、上传到了错误租户 | 刷新后台、重启应用服务，核对租户 ID 和审计日志。 |

### 6.2 排查顺序

建议按以下顺序排查：

1. 确认当前客户、租户、部署 ID 与合同一致。
2. 确认 `AGENTHIVE_LICENSE_PUBLIC_KEY_PATH` 指向正确公钥。
3. 确认 `AGENTHIVE_INSTALL_ID_PATH` 文件存在、可读、位于持久化卷。
4. 对比 activation request 中的 `install_id` 和当前运行时 `install_id`。
5. 对比 signed license 中的 `machine_fingerprint_hash` 和当前环境计算结果。
6. 检查 License 的 `expires`、`maintenance`、`allowed_modules`、`allowed_features`、`max_users`、`max_agents`。
7. 查看 AgentHive 审计日志和应用日志中的 License 验证失败原因。
8. 如涉及迁移、灾备、硬件变更或多环境复用，提交给厂商支持复核。

### 6.3 支持工单建议材料

客户提交 License 支持工单时，建议提供：

- 客户名称、租户 ID、部署 ID。
- AgentHive 版本号。
- activation request 文件或其摘要。
- signed license 文件或其摘要。
- 错误截图和审计日志中的失败原因。
- 是否近期发生迁移、恢复、扩容、容器重建、服务器更换或存储变更。

不要要求客户提供原始硬件序列号、生产数据库备份、模型 API Key 或其他与授权排查无关的敏感信息。

## 7. 交付检查清单

交付前：

- 合同已明确授权客户、部署数量、模块、功能、用户数、Agent 数、维护期和到期策略。
- 生产签发私钥未进入客户部署包、镜像、仓库、日志或文档样例。
- 客户部署包包含正确的 License 验证公钥。
- 安装文档说明了 `AGENTHIVE_LICENSE_PUBLIC_KEY_PATH` 和 `AGENTHIVE_INSTALL_ID_PATH`。
- `AGENTHIVE_INSTALL_ID_PATH` 已挂载到持久化卷。
- 生产环境已配置并持久化 MinIO；本地对象存储 fallback 仅用于开发调试，不作为客户生产交付方案。

激活时：

- activation request 来自客户实际部署环境。
- 签发前已核对合同和授权范围。
- signed license 使用 Ed25519 生产私钥签名。
- 激活成功后已检查模块、功能、用户数、Agent 数和有效期。
- 激活动作已写入审计日志。

交付后：

- 厂商保存签发记录、License 摘要、request 摘要和审批记录。
- 客户保存 signed license、安装身份文件和部署配置备份。
- 模块加购、迁移、扩容、续费和升级均通过重新签发或变更流程处理。

## 8. 安全红线

以下行为一律禁止：

- 将 Ed25519 私钥放入客户部署包。
- 将私钥写入 Docker 镜像、安装脚本、环境变量示例、README、客户文档或源码仓库。
- 让客户自行运行生产签发流程生成 License。
- 使用同一 signed license 激活多套未经授权的生产环境。
- 为绕过 License 验证而修改公钥、安装身份、机器指纹或授权字段。
- 在未审计的个人电脑、聊天工具或临时文件中保存生产私钥。

License 体系的目标不是影响客户正常私有化使用，而是保证商业授权、模块选装、升级维护和部署实例边界清晰可审计。交付团队应在安全、合规和客户体验之间保持一致标准：客户环境可离线运行，厂商私钥永不离开受控签发环境。
