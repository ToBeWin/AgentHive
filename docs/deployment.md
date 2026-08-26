# AgentHive 私有化部署说明

本文档补充 AgentHive 私有化交付中的存储和知识库上传验收要求。完整产品边界以项目根目录 `AGENTS.md` 为准。

如果采用“本地运行 backend/frontend，远程服务器只运行 PostgreSQL、Redis、MinIO”的开发或演示形态，请先阅读
[`docs/remote-infra-dev.md`](./remote-infra-dev.md)。该形态默认通过 SSH tunnel 连接远程基础设施，不直接向公网暴露数据库、Redis 或 MinIO。

## 环境变量

生产部署前必须准备根目录 `.env`。可以运行 `scripts/install.sh` 自动生成强随机密钥，也可以从 `.env.example` 复制后人工填写：

```bash
cp .env.example .env
```

`.env` 中的 `POSTGRES_PASSWORD`、`REDIS_PASSWORD`、`MINIO_ROOT_PASSWORD`、`LITELLM_MASTER_KEY`、`AGENTHIVE_MEDIA_WEBHOOK_SECRET`、`SECRET_KEY` 必须替换为客户部署唯一的强随机值。生产交付包不得复用开发环境默认密钥。`LITELLM_POSTGRES_DB` 默认为 `litellm`，必须保持为与 AgentHive 业务库 `agenthive` 不同的数据库名。

生产启动还必须显式配置客户实际使用的 HTTPS origin，例如 `AGENTHIVE_PUBLIC_BASE_URL=https://agenthive.acme.cn`。模板中的 `agenthive.example.com` 只用于说明，安装器和严格诊断会拒绝把模板域名作为生产交付地址。

从旧版升级时，应先把该变量和实际域名写入现有 `.env`，再运行 `scripts/backup.sh` 或 `scripts/upgrade.sh`；生产 Compose 会在变量缺失时直接拒绝渲染，以避免旧的明文入口被意外继续发布。

## 生产 TLS 边界

标准 Compose 采用“同宿主机 TLS 终止”模式：AgentHive 内置 Nginx 是 HTTP origin，但只绑定到 `127.0.0.1:${HTTP_PORT:-8080}`，不会直接暴露给局域网或公网。宿主机上的企业 Nginx、HAProxy、Caddy 或客户接入网关必须：

1. 在客户 HTTPS 域名上终止 TLS，使用企业 CA 或受信任证书；
2. 把请求代理到 `http://127.0.0.1:${HTTP_PORT:-8080}`；
3. 固定发送 `X-Forwarded-Proto: https`，并传递经过边界代理整理的 `Host` 和 `X-Forwarded-For`；
4. 对公网 HTTP 入口执行 HTTPS 跳转，不得把 AgentHive loopback origin 直接开放给客户端。

AgentHive 不会为生产环境关闭 `Secure` Cookie。除 `/api/v1/health` 和 `/api/v1/health/readiness` 外，loopback origin 收到未声明原始 HTTPS scheme 的请求会返回 `308` 到 HTTPS；两个健康端点继续允许本机安装器和 Docker 诊断通过 HTTP 探测。

宿主机外层 Nginx 的最小示例：

```nginx
server {
    listen 80;
    server_name agenthive.acme.cn;
    return 308 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name agenthive.acme.cn;
    ssl_certificate /etc/nginx/ssl/agenthive.crt;
    ssl_certificate_key /etc/nginx/ssl/agenthive.key;
    add_header Strict-Transport-Security "max-age=31536000" always;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

标准交付假定 TLS 终止器与 AgentHive 在同一宿主机。如果客户使用远程负载均衡器，应让远程负载均衡器连接同宿主机的受控边界代理或私有隧道；不要为了省事把 Compose origin 改为 `0.0.0.0`。完成后同时验证公网 HTTPS readiness 和浏览器登录，不能只验证 loopback health。

`AGENTHIVE_TRUSTED_PROXY_CIDRS` 用于应用层来源识别，`AGENTHIVE_FORWARDED_ALLOW_IPS` 用于 Uvicorn 接受内部 Nginx 整理后的 forwarded headers，从而让后端正确识别 HTTPS scheme 并发送 HSTS。两者默认只覆盖 loopback 和 Docker 默认私网。前者不要配置 `0.0.0.0/0` 或 `::/0`，后者不要配置 `*`；如客户自定义 Docker 网段，只增加该明确网段，并保持 origin 端口的 loopback 绑定不变。

首次生产启动前还必须把 AgentHive License 公钥写入 backend 数据卷。推荐使用安装脚本一次完成 `.env` 生成、公钥写入、容器启动、数据库迁移、官方 Agent 模块种子数据写入、数据库检查和 loopback origin readiness 等待：

```bash
scripts/install.sh --license-public-key ./agenthive_license_public.pem --start \
  --public-base-url https://agenthive.acme.cn
```

该命令会把公钥复制到 backend 容器内的 `/data/agenthive/license_public.pem`，然后按以下顺序执行：

1. 启动 PostgreSQL、Redis、MinIO、LiteLLM、backend 和 frontend。
2. 等待 backend 容器进入 running 状态。
3. 在 backend 容器内执行 `python scripts/init_db.py`，完成 Alembic 迁移和官方 Agent 模块 seed。
4. 执行 `python scripts/check_db.py`，验证迁移 head、官方模块 key 覆盖、pgvector 扩展和知识库向量 schema。
5. 等待 backend/frontend healthcheck 通过。
6. 启动内部 Nginx，并等待 loopback origin `http://127.0.0.1:${HTTP_PORT:-8080}/api/v1/health/readiness` 返回健康。该探测不替代公网 TLS 验收。

如果只生成 `.env` 或只预置公钥，也可以分别执行：

```bash
scripts/install.sh
scripts/install.sh --license-public-key ./agenthive_license_public.pem
```

`scripts/install.sh --start` 在没有检测到 License 公钥时会拒绝启动生产栈，避免 backend readiness 因 `license_identity` 阻塞而导致 nginx 无法等待到健康服务。只有本地评审或临时演示可以显式使用：

```bash
scripts/install.sh --allow-missing-license-public-key --start \
  --public-base-url https://agenthive.acme.cn
```

安装器默认等待 240 秒；客户服务器拉取镜像较慢或硬件较弱时可以延长：

```bash
scripts/install.sh --license-public-key ./agenthive_license_public.pem --start \
  --public-base-url https://agenthive.acme.cn --wait-timeout 600
```

`--skip-db-init` 只允许用于高级恢复或人工排障，不得作为标准交付路径。跳过后必须手工执行 `init_db.py` 和 `check_db.py`，并确认 readiness 通过后再交付。

## LiteLLM 数据库隔离

LiteLLM 使用 Prisma 管理自己的 schema 与迁移；它**不得**连接 AgentHive 业务数据库。标准 Compose 会让 PostgreSQL 在首次创建数据卷时通过 `infra/postgres/init/02_create_litellm_database.sh` 创建 `${LITELLM_POSTGRES_DB:-litellm}`，LiteLLM 的 `DATABASE_URL` 只指向该独立数据库。

从旧版 Compose 升级且 PostgreSQL 数据卷已存在时，Docker 不会再次自动执行 init 脚本。升级前先完成常规备份，然后执行以下幂等命令创建独立 LiteLLM 数据库并重建 LiteLLM：

```bash
docker compose --env-file .env -f docker-compose.yml exec -T postgres \
  sh /docker-entrypoint-initdb.d/02_create_litellm_database.sh
docker compose --env-file .env -f docker-compose.yml up -d --force-recreate litellm
```

随后运行 `scripts/upgrade.sh` 或标准的 `init_db.py` / `check_db.py` 验收流程。不要把 LiteLLM 的 Prisma 表复制或迁移到 `agenthive` 业务库。

如果历史部署已经让 LiteLLM 连接过 `agenthive` 并导致业务表被删除或重建，必须先按备份恢复 AgentHive 业务库，再执行上述隔离步骤；创建新 LiteLLM 数据库不会恢复已丢失的业务数据。

后端在 `AGENTHIVE_ENVIRONMENT=production` 时会执行生产配置门禁：`SECRET_KEY`、`LITELLM_MASTER_KEY`、`AGENTHIVE_MEDIA_WEBHOOK_SECRET`、`MINIO_ROOT_PASSWORD` 和 `REDIS_PASSWORD` 不得为空、不得使用模板占位值，也不得过短。未通过时后端会拒绝启动，readiness 的 `production_config` 组件也会报告 `unhealthy`。可用以下方式生成随机值：

```bash
openssl rand -hex 32
```

## API 安全基线

后端默认启用安全响应头和轻量级 API 限流，用于降低私有化部署中的误暴露、脚本滥用和异常流量风险。生产环境建议保留默认开启状态：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SECURITY_HEADERS_ENABLED` | `true` | 为 HTTP 响应添加 `X-Content-Type-Options`、`X-Frame-Options`、`Referrer-Policy`、`Permissions-Policy`，HTTPS 下补充 HSTS。 |
| `LOGIN_FAILURE_LIMIT` | `5` | 同一租户+邮箱或同一租户+IP 在登录失败窗口内允许的失败次数。 |
| `LOGIN_FAILURE_WINDOW_SECONDS` | `900` | 登录失败节流窗口秒数。 |
| `RATE_LIMIT_ENABLED` | `true` | 启用后端内置基础限流。 |
| `RATE_LIMIT_REQUESTS` | `120` | 同一来源、租户提示、接口路径在窗口期内允许的请求数。 |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | 限流窗口秒数。 |

健康检查、OpenAPI 文档和系统信息接口不参与限流，避免 Docker healthcheck 和部署诊断被误拦截。若客户已有外层 WAF/Nginx 限流，也建议保留后端限流作为最后一道保护，但可按客户实际并发量调高阈值。

## 数据库迁移与初始化

生产环境必须通过 Alembic 迁移到最新版本，不允许依赖 ORM `create_all` 隐式建表。标准首次部署使用 `scripts/install.sh --start` 时，安装器会自动执行迁移、seed 和数据库检查；升级使用 `scripts/upgrade.sh` 时也会自动执行同样检查。以下命令用于高级恢复、人工排障或显式复核：

```bash
docker compose --env-file .env -f docker-compose.yml exec backend python scripts/init_db.py
docker compose --env-file .env -f docker-compose.yml exec backend python scripts/check_db.py
```

本地评审、销售演示或前后端联调可以在 `init_db.py` 之后显式执行 demo seed：

```bash
docker compose --env-file .env -f docker-compose.dev.yml exec backend python scripts/seed_demo.py
```

`seed_demo.py` 会创建 `demo` 租户、默认管理员、部门、用户、角色、成本中心、示例 Agent、知识库、Channel、模型治理、预算和用量账本。该脚本是幂等的，可以重复运行补齐缺失演示数据；但它不是生产交付标准步骤，客户生产环境只有在明确要求预置演示数据时才允许执行。

`init_db.py` 会执行 `alembic upgrade head`，并幂等写入官方 Agent 模块目录。`check_db.py` 会验证：

- 数据库当前 Alembic revision 等于代码中的 head revision。
- 官方 Agent 模块种子数据 key 覆盖完整；缺失时会输出具体 `missing_modules`。
- PostgreSQL `vector` 扩展已安装。
- 媒体生成运行时索引完整；缺失时会输出具体 `missing_media_indexes`。

如果 `check_db.py` 失败，应先修复迁移或初始化问题；不要在未确认 schema 当前版本的情况下交付。

媒体生成模块依赖最新迁移中的运行时索引：任务列表按本人/部门数据范围分页、批量轮询 running 任务、Provider webhook 按 `provider_key + external_job_id` 定位任务都需要这些索引支撑。升级到包含图片/视频 Agent 的版本时，必须确认数据库 head 至少为 `0014_media_generation_job_runtime_indexes`，否则功能虽然可用，但多部门和高并发异步任务场景下会出现明显查询抖动。

管理后台 readiness / 诊断包的 database 组件也会返回 `media_runtime_indexes` 摘要；如果索引缺失，交付状态会降级并给出缺失索引名称，方便没有服务器 shell 权限的客户 IT 复核。

## 交付诊断包

私有化部署验收、实施支持和售后排障可以导出标准诊断包：

```text
GET /api/v1/system/diagnostics
```

该接口要求 `system:diagnostics` 权限，租户管理员默认具备全部权限；普通实施或运维角色需要显式授予该权限。管理后台“系统设置”页的诊断报告导出按钮会调用同一接口。

诊断包格式为 `deployment_diagnostics`，包含：

- `health`：轻量健康检查。
- `readiness`：深度就绪检查，包含 PostgreSQL、Redis、MinIO、LiteLLM、pgvector、生产配置、License 安装身份、可选 RAGFlow 和前端健康。
- `info`：产品名称、私有化部署版本信息。
- `delivery`：交付状态、阻塞项和警告项摘要。

诊断包会递归脱敏包含 `secret`、`password`、`token`、`api_key`、`master_key`、`authorization`、`credential`、`license_key` 等语义的字段，也会遮蔽 Bearer/sk key 和带用户名密码的 URL。诊断包仍可能包含服务地址、组件状态、部署 ID、安装 ID、机器指纹 hash 和交付摘要，导出文件应作为客户敏感运维材料保存。

每次导出都会写入 `system.diagnostics.export` 审计事件。审计详情只记录 schema、是否脱敏、readiness 状态、delivery 状态、阻塞/警告数量和组件数量，不复制诊断包正文。

`scripts/diagnose.sh` 支持把该受控诊断包写入 support bundle。先使用具备 `system:diagnostics` 权限的账号登录管理后台或调用登录 API 获取 Bearer Token，然后执行：

```bash
AGENTHIVE_DIAGNOSTICS_TOKEN="<access-token>" \
  scripts/diagnose.sh --strict --output-dir "diagnostics/$(date -u +%Y%m%dT%H%M%SZ)"
```

也可以使用参数传入：

```bash
scripts/diagnose.sh --output-dir diagnostics/current --diagnostics-token "<access-token>"
```

脚本不会打印或写入 Token。生成的 support bundle 会包含：

- `acceptance-checklist.md`：面向客户签收和交付归档的验收清单，包含结论、关键组件证据、部署身份、生产配置、待处理阻塞/警告和签字栏。
- `system-diagnostics.json`：后端标准诊断包。
- `system-diagnostics.meta`：请求 URL、HTTP 状态码、curl 状态和 `token_written=false` 标记。
- `summary.txt`：本次脚本检查失败数、警告数和 delivery 摘要。

未提供 Token 时，脚本仍会导出匿名 health/readiness、Compose 状态、数据库检查和前端构建状态，用于无法登录后台时的基础排障；但不会生成 `system-diagnostics.json` 或 `acceptance-checklist.md`。

管理后台导出的 `agenthive-support-bundle-*.zip` 也会包含 `acceptance-checklist.md`、`diagnostics.json`、`delivery-summary.md`、`manifest.json` 和 `README.md`，适合作为合同附件、实施验收记录和售后支持入口。该 zip 已经做语义脱敏，但仍应按客户敏感运维材料管理。

## 图片/视频生成 Agent 交付配置

商品图片生成助手和短视频生成助手是可选装官方 Agent。基础平台可以在未配置外部媒体模型时交付，但如果客户购买或启用媒体 Agent，交付前必须至少配置一条图片生成路由和一条视频生成路由，并确认 readiness 中 `media_generation` 组件为 `healthy`。

AgentHive 不会让图片/视频 Agent 直接调用供应商 SDK。所有请求都会先经过 Media Generation Gateway，完成 License、部门/人员模型策略、预算预占、异步任务、审计和 MinIO 输出规划，再路由到具体供应商。

官方 `image_generation` 和 `video_generation` Agent 运行时必须直接创建 `media_generation_jobs` 任务，而不是只调用 LLM 生成一段提示词计划。Agent 运行默认会把任务入队给媒体 Worker 执行；如需现场只创建任务不入队，可在运行上下文设置 `media_dispatch_mode=create_only`。Agent 运行响应会返回 `metadata.media_generation_job`，包含任务 ID、类型、状态、供应商、模型、路由、预计费用、输出存储规划和 dispatch 结果；管理后台 Agent 运行诊断应展示该任务，媒体任务页应能继续执行、轮询、查看产物和下载输出。

Chat 会话和 Channel webhook 触发媒体 Agent 时，也必须透传同一份 `metadata.media_generation_job` 摘要。Channel 的 `processing` 结果、`channel.webhook.processed`、`channel.message.routed` 和 `agent.run` 审计事件应能关联到同一个媒体任务 ID；摘要只允许包含任务 ID、类型、状态、供应商、模型、路由和 dispatch 结果，不得包含供应商密钥、完整提示词或私有素材 URL 凭据。

| 能力 | 变量 | 说明 |
| --- | --- | --- |
| ChatGPT Images 2.0 / OpenAI 图片 | `AGENTHIVE_OPENAI_IMAGES_BASE_URL`、`AGENTHIVE_OPENAI_IMAGES_API_KEY` | 默认 Base URL 可使用 `https://api.openai.com/v1`；国内客户也可以改为企业代理或兼容网关。 |
| Nano Banana 图片 | `AGENTHIVE_NANO_BANANA_BASE_URL`、`AGENTHIVE_NANO_BANANA_API_KEY` | 预留 Google/Nano Banana 或客户侧兼容服务入口。 |
| 火山 Seedance 2.0 视频 | `AGENTHIVE_VOLCENGINE_SEEDANCE_BASE_URL`、`AGENTHIVE_VOLCENGINE_SEEDANCE_API_KEY` | 用于短视频 Agent 的首选视频生成路由。 |
| 私有 OpenAI-compatible 媒体服务 | `AGENTHIVE_MEDIA_OPENAI_COMPATIBLE_BASE_URL`、`AGENTHIVE_MEDIA_OPENAI_COMPATIBLE_API_KEY` | 一套私有兼容端点可同时承载图片和视频模型。 |
| 私有图片/视频路径 | `AGENTHIVE_MEDIA_OPENAI_COMPATIBLE_IMAGE_PATH`、`AGENTHIVE_MEDIA_OPENAI_COMPATIBLE_VIDEO_PATH` | 默认分别为 `/images/generations` 和 `/videos/generations`。 |
| 私有媒体状态查询路径 | `AGENTHIVE_MEDIA_OPENAI_COMPATIBLE_STATUS_PATH` | webhook 丢失时的轮询兜底路径，支持 `{external_job_id}`、`{job_id}` 和 `{provider_key}` 占位。 |
| 平台公网地址 | `AGENTHIVE_PUBLIC_BASE_URL` | 外部供应商回调、客户访问和交付诊断使用的 AgentHive 公开地址，例如 `https://agenthive.customer.com`。 |
| 异步回调地址 | `AGENTHIVE_MEDIA_WEBHOOK_PUBLIC_URL` | 可选；不填时由 `AGENTHIVE_PUBLIC_BASE_URL` 自动拼接 `/api/v1/media/webhooks/provider`。 |
| 异步回调密钥 | `AGENTHIVE_MEDIA_WEBHOOK_SECRET` | 供应商异步任务回调必须使用该密钥验签；生产环境必须替换为强随机值，并会被生产配置门禁检查。 |
| 输出对象存储 | `AGENTHIVE_MEDIA_OUTPUT_BUCKET` | 生成结果、缩略图、参考输出和归档下载都写入 MinIO。 |
| 火山 Seedance 状态查询路径 | `AGENTHIVE_VOLCENGINE_SEEDANCE_STATUS_PATH` | Seedance 异步任务的轮询兜底路径，默认 `/jobs/{external_job_id}`，按客户侧网关实际协议调整。 |

`scripts/diagnose.sh --output-dir diagnostics/current` 会在 `summary.txt` 中写入：

- `media_generation_status`
- `media_generation_configured_models`
- `media_generation_image_models`
- `media_generation_video_models`
- `media_generation_configured_providers`
- `media_generation_missing_providers`
- `media_worker_status`
- `media_worker_ping_ok`
- `media_worker_count`

当 `media_generation` 为 `degraded` 时，它只作为交付 warning；这表示基础 AgentHive 平台仍可运行，但媒体 Agent 不应对客户宣称可用。交付图片/视频模块前，必须在管理后台“模型”页完成供应商凭据配置，或者在 `.env` 中配置对应变量并重启后端，再重新运行严格诊断。

媒体 Provider 配置完成后，必须执行一次真实网络探测，而不是只检查环境变量是否存在。管理后台“模型”页或 API `POST /api/v1/models/test-connection` 可传入 `provider_key`、`model_key`、`live_check=true` 和只读 `probe_path`（默认 `/models`）；验收结果应包含 `diagnostics.operation=media_provider_live_probe`、`diagnostics.live_network_call=true`、HTTP 状态码和耗时。探测请求会带 Provider Bearer Token，但响应、审计和支持包不得记录密钥、完整 Base URL、响应正文或供应商错误中的敏感信息。

当 `media_worker` 为 `degraded` 时，说明 Celery Worker 未响应 ping。基础平台仍可作为非媒体 Agent 平台交付，但图片/视频 Agent 只能创建任务，无法证明自动执行链路已就绪。交付媒体模块前，必须启动 Worker 并确认 readiness 中 `media_worker.details.worker_ping_ok=true`。

视频生成通常是异步任务。AgentHive 在提交视频任务时会把回调地址和 `X-AgentHive-Media-Webhook-Secret` 签名头一并交给 Provider；Provider 完成后应回调 `POST /api/v1/media/webhooks/provider`。如果 webhook 丢失，管理员可以在媒体任务页点击“轮询状态”，或点击“批量入队轮询”把当前 `running` 且已有外部任务 ID 的任务交给 Celery 兜底处理；运维也可以调用 `POST /api/v1/media/generations/poll/enqueue?limit=20`。轮询成功后同样会归档输出、结算预算并写入审计。生产环境必须保证回调地址能被 Provider 访问，且不要把内网地址直接配置为公开回调地址。

媒体 Agent 验收建议：

1. 安装并启用 `agent.image_generation` / `agent.video_generation`，确认 License 同时授权 `feature.media_generation` 和 `feature.model_budget`。
2. 对已配置的图片和视频 Provider 各执行一次 `live_check=true` 连接测试，确认不是仅通过配置存在性检查。
3. 使用官方 Agent 运行接口或管理后台 Agent 抽屉提交图片/视频自然语言需求，并带上参考图或参考视频。
4. 确认响应中 `usage.total_tokens=0`，说明媒体 Agent 没有绕到 LLM 文案链路；成本应由媒体预算账本预占和结算。
5. 确认响应 `metadata.media_generation_job.dispatch.queued=true` 且包含 Celery `task_id`；如果 Redis/Celery 不可用，应返回 `reason=queue_unavailable` 和重试动作，而不是宣称任务已执行。
6. 确认响应 `metadata.media_generation_job.id` 对应的任务出现在媒体任务列表，状态可继续从 `queued` 到 `running` / `succeeded` / `failed`。
7. 通过 Chat 会话和至少一个 Channel 测试入口触发同一个媒体 Agent，确认返回 metadata 或 processing 结果中包含媒体任务摘要。
8. 确认 `media.generation.create`、`media.generation.enqueue`、后续执行/轮询/下载事件、`agent.run` 和 Channel 路由审计事件均存在，且不包含供应商密钥、素材私有 URL 凭据或原始敏感上下文。
9. 使用另一名普通用户直接访问该任务详情、事件、运行/轮询/入队接口和输出下载接口，应返回 403；把任务绑定到该用户所在部门后，部门成员才可访问和下载。
10. 模拟 Provider webhook：正确 `job_id` / `external_job_id` 能更新任务；错误 `provider_key`、错误 `external_job_id` 或重复 `external_job_id` 必须返回 409，且不应写入成功状态或结算预算。输出归档失败时接口应返回 503、保留原任务状态、写入 `media.generation.provider_callback_failed` 审计，并且审计详情不得包含输出 URL 或 base64 内容。
11. 模拟 Provider 返回输出 URL：公网 `https` URL 可以归档到 MinIO；localhost、私网 IP、解析到私网的域名和 `file://` 等非 HTTP(S) scheme 必须被拒绝，且不得产生对象存储写入。

## 备份、恢复与升级

AgentHive 私有化交付必须把业务数据库、对象存储、安装身份和 License 验证材料作为一个整体备份。只备份 PostgreSQL 不足以恢复知识库文件、Channel 附件、安装身份和离线授权状态。

### 生产备份

执行：

```bash
scripts/backup.sh
```

备份目录默认写入 `backups/agenthive-<UTC时间>`，包含：

| 文件 | 内容 |
| --- | --- |
| `postgres.sql` | PostgreSQL 逻辑备份，包含业务表、审计、预算、License、知识库元数据。 |
| `minio_data.tgz` | MinIO 对象存储数据。 |
| `redis_data.tgz` | Redis 持久化数据。 |
| `agenthive_data.tgz` | AgentHive 数据卷，包含安装身份、License 公钥、本地 fallback 文件。 |
| `config/` | `.env`、Compose、Nginx、LiteLLM 配置快照。 |
| `manifest.json` | 备份格式、生成时间和文件清单。 |
| `checksums.sha256` | PostgreSQL、卷归档和关键配置的 SHA-256 清单；恢复会在清空任何数据前强制校验。 |

备份目录包含客户数据、模型密钥引用、License 材料和部署密钥，必须在外部使用客户认可的
加密介质、age/KMS 或备份平台加密保存并限制访问。内置恢复脚本会先验证
`checksums.sha256`，任一文件损坏或被修改都会在破坏性操作前停止。

### 生产恢复

恢复是破坏性操作，必须先停止外部流量并确认目标环境：

```bash
scripts/restore.sh --backup-dir backups/agenthive-YYYYMMDDTHHMMSSZ --yes
```

恢复流程会替换 AgentHive、MinIO、Redis 数据卷，并从 `postgres.sql` 重建 PostgreSQL `public` schema。恢复完成后必须执行：

```bash
scripts/diagnose.sh
docker compose --env-file .env -f docker-compose.yml exec backend python scripts/check_db.py
```

恢复验收至少确认：

1. readiness 返回 healthy。
2. License 页面没有出现 `install_id_mismatch` 或 `machine_fingerprint_mismatch`，除非这是一次迁移恢复。
3. 知识库文档元数据和 MinIO 对象均可访问。
4. 最近用量账本、预算策略、审计日志仍可查询。
5. Agent 模块授权状态与恢复前一致。

### 升级

升级前默认必须先备份：

```bash
scripts/upgrade.sh
```

该脚本会先执行 `scripts/backup.sh`，再构建 backend 镜像并运行 License 升级预检。预检会检查当前活跃租户的 License 是否为 active、部署身份是否匹配、License 是否过期，以及 `maintenance_until` 是否仍覆盖本次升级。预检通过后才会启动 Compose 栈、运行数据库初始化/迁移校验和诊断。只有在外部已经完成可靠备份时，才允许使用：

```bash
scripts/upgrade.sh --skip-backup
```

升级脚本默认会在最后运行严格诊断并生成脱敏支持包：

```bash
scripts/upgrade.sh --diagnostics-output-dir diagnostics/customer-prod-upgrade
```

如果 readiness、数据库、License 身份、生产配置或其它关键检查存在 failures，严格诊断会让升级脚本以非 0 状态退出，不应继续宣称升级完成。

如需单独检查当前部署是否有升级授权，可执行：

```bash
docker compose --env-file .env -f docker-compose.yml run --rm --no-deps backend \
  python scripts/check_license_upgrade.py --target-version "${AGENTHIVE_VERSION:-0.3.0-alpha.1}"
```

该命令不会输出 License Key 或 signed license 原文，只输出租户、客户名、License 类型、维护期、到期时间和阻塞原因。

## 对象存储

AgentHive 使用 MinIO 作为长期对象存储。生产环境必须配置 MinIO，并为 bucket 数据、配置和凭据挂载持久化存储；上传文件、知识库原文、解析产物、导出文件、头像和 Channel 附件都不应依赖应用容器本地磁盘长期保存。

开发环境可以启用本地文件 fallback，便于单机调试知识库上传流程。该 fallback 只允许用于 `AGENTHIVE_ENVIRONMENT=development` 和临时验证，不能作为生产交付方案。生产环境即使历史 metadata 中出现 `local_path`，后端也不会读取本地 fallback 文件，而是继续按 MinIO 读取并暴露错误。readiness 的 `minio.details.local_fallback_allowed` 应在生产环境为 `false`。使用 fallback 时，后端会在文档 `metadata` 中标注 `storage_backend=local-development-fallback`，交付验收应确认生产环境该值指向 MinIO。

生产环境准备知识库上传目标时必须具备完整 MinIO 配置和后端 MinIO SDK；缺失任一项时接口会直接失败，不会返回 placeholder 上传计划。placeholder 上传计划只允许出现在开发环境，用于本地 UI 联调或离线单机调试。

## 知识库持久化边界

生产交付中，知识库元数据必须由 PostgreSQL 持久化，文件原文和解析产物必须由 MinIO 持久化，向量存储和检索能力由 PostgreSQL + pgvector 或 RAGFlow 负责。开发模式可以在数据库不可用时短暂启用内存降级，便于本地调试启动链路；该降级不保留生产数据，不能作为生产交付或验收依据。

当前交付验收可验证文本类文件上传后的 chunk 检索闭环：后端会将文本内容切分并写入 PostgreSQL `knowledge_chunks` 表。数据库迁移已为 `knowledge_chunks` 建立 `embedding vector(1536)`、embedding 元数据列和 cosine ivfflat 索引；`check_db.py` 会验证这些结构存在。

默认 `RAG_EMBEDDING_MODE=deterministic_local` 使用 AgentHive 本地 hash embedding 写入 pgvector，用于离线部署、交付验收和向量链路冒烟测试。它不是最终语义 embedding 模型；生产语义检索应在后续接入 LLM Gateway embedding provider 后替换为真实 embedding。当前检索会优先尝试 pgvector 向量相似度，有向量结果时返回 `retrieval_mode=vector_similarity`，无结果或 schema 不可用时回退到文本 chunk 匹配。

如客户已有 RAGFlow 或希望将复杂解析交给外部 RAG 服务，可通过 RAGFlow-compatible HTTP Adapter 接入。AgentHive 默认发送稳定的私有桥接协议，具体路径可配置：

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `RAGFLOW_URL` | 空 | RAGFlow 或客户侧 RAG 桥接服务的 Base URL。为空时视为未配置。 |
| `RAGFLOW_API_KEY` | 空 | 可选 Bearer Token，不会写入日志或诊断输出。 |
| `RAGFLOW_HEALTH_PATH` | `/health` | 健康检查路径。 |
| `RAGFLOW_INGEST_PATH` | `/api/v1/agenthive/ingest` | 文档 ingest 提交路径。 |
| `RAGFLOW_RETRIEVE_PATH` | `/api/v1/agenthive/retrieve` | 检索路径。 |
| `RAGFLOW_DELETE_PATH` | `/api/v1/agenthive/documents/{knowledge_base_id}/{document_id}` | 删除路径，支持 `{knowledge_base_id}` 和 `{document_id}` 占位。 |

RAGFlow-compatible ingest payload 会包含 `tenant_id`、`knowledge_base_id`、`document_id`、`storage`、`parser_config` 和 `metadata`。retrieve payload 会包含 `query`、`top_k`、`filters` 和 `include_raw_chunks`。外部服务返回的 `chunks` / `results` 会被映射回 AgentHive 的统一 `RAGChunk`。

知识库删除采用治理型软删除：

- `DELETE /api/v1/knowledge/bases/{baseId}` 会归档知识库，软删除其文档元数据，并从 pgvector/RAGFlow/MinIO 尝试清理对应索引和对象。
- `DELETE /api/v1/knowledge/bases/{baseId}/documents/{documentId}` 会软删除单个文档，并重新计算知识库文档数量。
- `POST /api/v1/knowledge/bases/{baseId}/documents/{documentId}/reingest` 会保留 MinIO 原文对象，清理旧的 pgvector chunk 或 RAGFlow 文档索引，并基于原对象重新触发 ingest。该接口适用于解析失败后重试、切分策略调整后重建索引、或外部 RAG 引擎修复后的补偿入库。
- 删除操作要求 `knowledge:write` 和知识库写入数据范围；租户管理员仍可执行全部租户内知识库治理。
- 删除接口返回 `diagnostics`，用于说明对象、RAG 索引、pgvector chunk 的清理结果；清理异常也会写入审计日志，便于客户现场排查。
- 重新入库操作同样要求 `knowledge:write` 和知识库写入数据范围，并会写入 `knowledge.document.reingest` 审计事件。待上传、入库中和已删除文档不能重新入库。
- 被删除的知识库和文档不会再出现在默认列表、检索测试和 Agent RAG 上下文中；历史审计、对话引用和费用记录不应被物理删除。

## 知识库上传与 ingest 验收

知识库文档上传接口：

```text
POST /api/v1/knowledge/bases/{baseId}/documents/upload
```

multipart 字段：

| 字段 | 说明 |
| --- | --- |
| `file` | 待上传文档文件。 |
| `auto_ingest` | `true` 时上传后立即触发解析/入库；`false` 时仅保存文件和文档记录。 |
| `parser_config` | JSON object，传入解析参数。 |
| `metadata` | JSON object，传入业务元数据。 |

交付验收建议：

1. 在生产部署中确认 MinIO 服务健康、bucket 可访问、数据目录已持久化并纳入备份。
2. 上传一个测试文档，确认接口返回成功，知识库和文档元数据已写入 PostgreSQL，并在 MinIO 中能看到对应对象。
3. 使用 `auto_ingest=false` 上传，确认只生成文档记录，不立即进入解析流程。
4. 使用 `auto_ingest=true` 上传，确认文档进入 ingest 流程，状态最终变为可检索或明确失败原因，检索链路走 pgvector 或 RAGFlow。
5. 查询文档 metadata，确认生产环境 `storage_backend` 为 MinIO 相关标识，而不是本地 fallback；同时确认未启用内存知识库降级。
6. 对已上传、已索引或失败文档执行重新入库，确认接口基于 MinIO 原对象重新触发 ingest，并检查审计日志中的 `knowledge.document.reingest`。
7. 删除测试文档，确认文档列表、检索结果和 pgvector chunk 均不再包含该文档，并检查审计日志中的 `knowledge.document.delete`。
8. 删除测试知识库，确认知识库列表不再展示该知识库，相关文档不可见，并检查审计日志中的 `knowledge.base.delete`。

## Agent 知识库闭环验收

绑定知识库的官方 Agent 交付时必须验证完整运行闭环：

1. 创建或选择一个已授权、已启用的官方 Agent 实例，并绑定可读知识库。
2. 运行一个命中文档内容的问题，确认响应 metadata 中包含知识库来源、置信诊断和 `agent.run` 审计事件。
3. 运行一个明显超出知识库范围的问题，默认严格守门应返回安全提示并跳过模型调用；响应 metadata 中 `knowledge.guardrail.triggered=true`、`skipped_model_call=true`，用量为 0 Token。
4. 将服务端运行上下文切换为 `knowledge_guardrail_mode=advisory` 后重复低置信问题，确认模型调用继续执行，但 metadata 和审计中仍保留守门诊断。
5. 管理后台 Agent 运行结果应展示知识库置信度、是否需要人工复核和守门状态，便于现场人员判断是否需要补充知识文档。

## 健康检查与交付诊断

生产部署必须通过 AgentHive 的分层健康检查：

| 接口 | 用途 | 期望 |
| --- | --- | --- |
| `GET /api/v1/health` | 轻量活性检查，证明后端进程可响应。 | 返回 JSON，`service` 为 `agenthive-backend`。 |
| `GET /api/v1/health/readiness` | 生产就绪检查，验证 PostgreSQL 迁移、Redis、MinIO、LiteLLM、前端管理台、pgvector、License 安装身份，以及已配置的 RAGFlow 端点。 | 所有关键组件健康时返回 HTTP 200；否则返回 HTTP 503 并说明失败组件。响应体包含 `delivery` 交付验收摘要。 |
| `GET /api/v1/auth/setup-status` | 首次安装入口的初始化可用性检查。 | 即使 PostgreSQL 暂不可用，也应返回结构化 `setup_available=false`、`message` 和 `diagnostics`，方便安装页展示明确排障提示。 |

生产 `docker-compose.yml` 中后端容器使用 readiness 作为 Docker healthcheck。交付验收时应执行：

```bash
scripts/diagnose.sh
```

管理后台的 **Settings / 系统设置** 页面会并行读取 `health`、`readiness` 和 `system/info`，用于现场查看后端版本、部署环境、组件健康、License 安装身份和生产配置门禁。即使 readiness 返回 HTTP 503，前端也应展示响应体中的组件诊断，而不是只显示通用错误；这便于客户现场直接定位 PostgreSQL、Redis、MinIO、LiteLLM、前端管理台、pgvector 或 License 身份问题。

生产 Compose 会通过 `AGENTHIVE_FRONTEND_HEALTH_URL=http://frontend/` 让后端 readiness 探测前端容器。若客户采用自定义部署拓扑，必须把该变量指向管理台可访问的 HTTP 健康地址；单独运行后端的开发环境可以留空，此时后端只在发现本地 `frontend/dist/index.html` 时加入开发构建产物检查。

`readiness.delivery` 是交付验收摘要：

- `status=ready`：关键交付项均通过，可进入客户验收。
- `status=ready_with_warnings`：核心链路可用，但仍有非关键 warning，交付前应人工确认。
- `status=blocked`：存在阻塞项，不应交付或升级上线。
- `blockers` / `warnings`：包含组件、状态、说明和 remediation，便于直接分派给交付或运维。

首次安装页会读取 `auth/setup-status`。当数据库不可达时，后端不会只返回通用 503，而是返回 `setup_available=false` 和 `diagnostics.component=database`，前端会用当前语言显示“数据库不可用，请先检查 PostgreSQL”类提示。安装人员应优先修复数据库连接、迁移和凭据，而不是反复提交初始化表单。

管理后台 **Settings / 系统设置** 页的“交付支持包”区块会同时展示 UI 脱敏 JSON 导出状态、当前 `readiness.delivery` 快照、阻塞/警告/检查数量，以及严格验收和离线兜底命令。现场交付建议先在该页面确认交付状态，再用页面展示的 CLI 命令生成可归档的支持包；客户内网无法登录后台时，使用离线兜底命令先收集匿名 health/readiness 和本机环境证据。

诊断脚本默认是支持排障模式：即使 Docker daemon、数据库或 Redis 不可用，也会继续收集后端健康接口、迁移 head、`check_db.py`、pgvector schema、前端构建产物等证据，最后汇总 failures/warnings。交付验收或 CI 中应使用严格模式：

```bash
scripts/diagnose.sh --strict
```

需要发给交付或售后支持时，应生成脱敏支持包：

```bash
scripts/diagnose.sh --output-dir diagnostics/agenthive-$(date -u +%Y%m%dT%H%M%SZ)
```

支持包会包含 `diagnose.log`、`summary.txt`、`env-summary.tsv`、liveness/readiness 响应 JSON、HTTP meta、Docker Compose 服务状态、Alembic head 和 `check_db.py` 输出。readiness JSON 会保留组件级 `message`、`details` 和 `remediation`，用于直接定位 PostgreSQL、Redis、MinIO、LiteLLM、前端管理台、pgvector、生产配置或 License 身份问题。`summary.txt` 会提取 `delivery_status`、`delivery_blockers` 和 `delivery_warnings`，便于售后一眼判断是否能交付。支持包不会包含 `.env` 明文值，也不会导出完整渲染后的 Compose 配置；`env-summary.tsv` 只记录变量是否缺失/模板值和字符串长度。

诊断脚本会检查 Docker/Compose、必要配置文件、Compose 配置解析结果、服务状态，并实际访问 liveness/readiness 端点。若 readiness 不是 healthy，或 `check_db.py` 未通过，需要先修复对应组件，而不是跳过健康检查继续交付。支持人员不得把 `.env` 明文内容贴给客户或第三方；如需共享诊断材料，优先共享 `--output-dir` 生成的脱敏支持包。

在生产 Compose（`docker-compose.yml`）下，诊断脚本还会执行 `.env` 前置门禁：`POSTGRES_PASSWORD`、`REDIS_PASSWORD`、`MINIO_ROOT_USER`、`MINIO_ROOT_PASSWORD`、`LITELLM_MASTER_KEY`、`AGENTHIVE_MEDIA_WEBHOOK_SECRET`、`SECRET_KEY` 必须存在，不能仍是 `change-me`、`placeholder`、`example`、`agenthive_dev` 等模板值，并且密钥长度必须满足生产下限。该检查只输出变量名和失败原因，不输出变量值。

常见 readiness 失败项：

| 组件 | 常见原因 | 处理建议 |
| --- | --- | --- |
| `database` | PostgreSQL 未启动、密码错误、网络不可达。 | 检查 `.env` 中 `POSTGRES_PASSWORD` 和 postgres 容器日志。 |
| `redis` | Redis 密码错误或端口不可达。 | 检查 `.env` 中 `REDIS_PASSWORD` 和 redis 容器健康状态。 |
| `minio` | MinIO 凭据错误、bucket 服务未就绪、SDK 不可用。 | 检查 `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` 和 MinIO 容器日志。 |
| `litellm` | LiteLLM 未启动、配置文件错误、Master Key 错误。 | 检查 `LITELLM_CONFIG_FILE`、`LITELLM_MASTER_KEY` 和 litellm 容器日志。 |
| `frontend` | 前端容器未启动、构建产物缺失、nginx upstream 不通或 `AGENTHIVE_FRONTEND_HEALTH_URL` 未配置。 | 检查 frontend 容器健康状态、`npm --prefix frontend run build` 输出和 `AGENTHIVE_FRONTEND_HEALTH_URL`。 |
| `production_config` | 生产环境仍使用默认、占位或过短密钥。 | 重新生成 `.env` 中的 `SECRET_KEY`、`LITELLM_MASTER_KEY`、`AGENTHIVE_MEDIA_WEBHOOK_SECRET`、`MINIO_ROOT_PASSWORD` 和 `REDIS_PASSWORD`。 |
| `pgvector` | pgvector 扩展未启用、`knowledge_chunks` 向量列或索引缺失。 | 执行数据库迁移并运行 `backend/scripts/check_db.py`。 |
| `ragflow` | 配置了 `RAGFLOW_URL` 但健康检查失败。 | 检查 RAGFlow 或客户侧 RAG 桥接服务地址、路径和 API Key。 |
| `license_identity` | 安装身份文件损坏或生产环境缺少 License 公钥。 | 确认 `/data/agenthive/install-identity.json` 和 `/data/agenthive/license_public.pem`。 |
