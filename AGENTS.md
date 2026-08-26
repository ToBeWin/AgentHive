# AGENTS.md — AgentHive Enterprise AI Platform

> **面向 AI Coding Agent（Codex / Claude Code / Cursor）的完整项目指南**
> 本文件是项目的唯一权威规范，所有代码生成、架构决策、功能实现必须以此为准。
> 请在开始任何任务前完整阅读本文件。

---

## 目录

1. [产品概述](#1-产品概述)
2. [技术栈](#2-技术栈)
3. [架构设计](#3-架构设计)
4. [项目结构](#4-项目结构)
5. [数据库设计](#5-数据库设计)
6. [API规范](#6-api规范)
7. [Agent框架规范](#7-agent框架规范)
8. [RAG引擎规范](#8-rag引擎规范)
9. [Channel层规范](#9-channel层规范)
10. [权限与安全规范](#10-权限与安全规范)
11. [日志与审计规范](#11-日志与审计规范)
12. [企业级功能规范](#12-企业级功能规范)
13. [前端规范](#13-前端规范)
14. [部署规范](#14-部署规范)
15. [开发规范](#15-开发规范)
16. [测试规范](#16-测试规范)
17. [MVP范围与优先级](#17-mvp范围与优先级)

---

## 1. 产品概述

### 1.1 产品定位

**AgentHive** 是一个面向中小企业的私有化部署企业 AI 平台，帮助对 AI 零基础的中小企业完成 AI 智能化转型。

核心理念：**让企业每一个岗位都有一个专属 AI 同事**，而不是一堆割裂的 AI 工具。

### 1.2 目标用户

- **规模**：50–500人的中小企业
- **行业**：电商、制造、贸易、教育、法律、医疗
- **特征**：对 AI 无技术背景，有降本增效强烈需求，数据安全敏感，已使用企业微信/钉钉
- **典型客户**：电商公司（拼多多/淘宝/京东商家）

### 1.3 核心价值主张

```
私有化部署    数据永不离开客户服务器
可插拔Agent   按岗位按需开启，不捆绑销售
Agent选装      客户可按需求安装/启用官方Agent和行业Agent模块
低代码构建    非技术人员也能配置专属Agent
多渠道接入    企业微信/钉钉/飞书/网页Widget
引擎无关      底层RAG/LLM引擎可替换升级
模型治理      按租户/部门/人员/Agent精细控制模型、Token和费用
国际化        默认支持中文简体和英文，方便服务全球客户
```

### 1.4 产品形态

单体应用，私有化部署，Docker Compose 一键启动。平台自身不强依赖任何云服务，完全可在内网运行；云端LLM、云对象存储、云监控等只能作为客户主动配置的可选外部能力。

商业交付优先考虑私有化买断模式：客户购买当前授权版本和已授权模块，后续大版本升级、新增Agent模块、高级部署形态、定制功能、长期运维支持需另行付费。

### 1.4.1 统一Web端与角色化管理

AgentHive 必须是一个**成熟的企业级 AI 平台**，不是单一聊天工具，也不是只有技术人员可用的后台。默认交付形态为同一个 Web 端，根据登录用户的角色、权限、部门和资源授权动态呈现不同能力：

```text
同一Web端
├── 企业管理员视图：租户设置、License、组织部门、角色权限、模型供应商、预算、审计、交付诊断
├── 运维/实施视图：部署健康、组件状态、模型连通性、日志审计、支持包、升级与备份恢复
├── 模型管理员视图：供应商、Base URL、API Key、模型部署、路由、价格、策略、连接测试
├── Agent管理员视图：Agent模块选装、Agent实例、知识库绑定、渠道绑定、发布和运行诊断
├── 部门领导视图：本部门Agent使用情况、人员用量、预算消耗、知识库和效果报表
├── 普通员工视图：已授权Agent、对话、个人历史、可见知识库和个人用量
└── 审计/财务视图：费用账本、Token用量、审计日志、导出报表、成本中心
```

设计原则：

- 前端只有一个产品入口，不拆成多个割裂后台；导航、页面、按钮、表单字段、数据范围由权限系统控制。
- 后端权限永远是最终裁决；前端权限判断只用于体验优化和隐藏不可用入口。
- 所有管理能力都必须支持租户、部门、人员、角色和资源级范围，不允许只做全局开关。
- 模型接入必须有完整管理界面：选择供应商、填写 Base URL、API Key、模型 Key、部署名称、路由 Key、能力标签、价格、预算策略、连接测试和 live probe。
- API Key、License、Webhook Secret、LiteLLM Master Key 等敏感字段只允许写入和脱敏展示，禁止前端回显明文。
- 部门领导默认只能看本部门及下级部门数据；普通员工只能看自己有权使用的 Agent、知识库、渠道和用量。
- 管理员、运维、部门领导、员工等角色必须在项目初期作为产品骨架设计，不能后期临时补权限字段。

管理台必须覆盖以下一等模块，且每个模块都要有明确的读写权限、数据范围和审计事件：

| 模块 | 主要使用者 | 必须闭环的能力 |
|------|------------|----------------|
| 概览/运营看板 | 管理员、部门领导、财务 | 请求量、Token、费用、活跃模型、部门/人员/Agent用量、导出报表 |
| Agent 管理 | Agent管理员、部门领导 | 官方Agent选装、实例配置、模型选择、知识库绑定、渠道绑定、发布、试运行 |
| 模型管理 | 模型管理员、运维 | 供应商、Base URL、API Key、模型部署、价格、路由、fallback、连接测试、可用性探测 |
| 预算与费用 | 管理员、财务、部门领导 | 租户/部门/人员/Agent/Channel/模型级预算、限流、预警、费用账本和结算口径 |
| 部门与用户 | 管理员、部门管理员 | 组织树、用户、角色、部门归属、成本中心、批量导入、离职/停用 |
| 知识库 | 知识库管理员、Agent管理员 | 创建、上传、MinIO存储、RAG入库、检索测试、权限范围、Agent绑定 |
| 渠道 | 运维、Agent管理员 | 企业微信/钉钉/飞书/Web Widget/Webhook配置、Secret、回调测试、绑定Agent |
| 审计日志 | 管理员、审计/财务 | 登录、配置变更、模型调用、预算拦截、文件操作、导出和筛选 |
| License/交付诊断 | 运维、实施 | 授权激活、模块范围、部署指纹、组件健康、支持包、升级/备份提示 |

模型配置界面不得只是保存一个 API Key。至少要支持：

- 供应商类型：OpenAI、Anthropic、Gemini、Qwen、MiniMax、GLM、DeepSeek、Kimi、Doubao、OpenAI-compatible、LiteLLM、Ollama/vLLM 等。
- 连接信息：Base URL、API Key/Secret、组织ID、区域、代理、超时、重试、是否启用流式输出。
- 模型部署：模型 Key、展示名、上下文窗口、输入/输出/视觉/工具调用/图片/视频能力标签、默认参数、fallback 链。
- 治理信息：允许的租户/部门/人员/角色/Agent/Channel、预算策略、单次Token上限、日/月限额、境外模型限制。
- 成本信息：输入Token价格、输出Token价格、图片/视频单价、币种、计费单位、生效时间和历史价格。
- 验证动作：保存前格式校验、保存后连接测试、live probe、错误脱敏、审计记录和最后成功/失败时间。

### 1.5 命名规范

产品、文档、页面标题、安装脚本输出、Docker镜像标签、默认组织名称统一使用 **AgentHive**。

- ✅ 正确：AgentHive Enterprise AI Platform
- ✅ 正确：AgentHive 管理后台
- ❌ 错误：Hive Enterprise AI Platform
- ❌ 错误：AI Hive / Agent Hive（除非作为竞品或商标检索对象）

代码包、数据库名、Docker服务名可以使用小写 `agenthive`。历史路径 `hive/` 仅作为早期草案，不再用于新建代码。

### 1.6 内置官方Agent清单

| Agent名称 | 场景 | 优先级 |
|-----------|------|--------|
| 电商客服助手 | 客服辅助回答，知识库检索 | P0 |
| HR简历筛选助手 | 简历解析，岗位匹配评分 | P0 |
| 文案创作助手 | 小红书/抖音/朋友圈文案生成 | P0 |
| 商品图片生成助手 | 商品图、营销海报、参考图重绘和多图变体生成 | P0 |
| 短视频生成助手 | 商品短视频、参考视频续创、素材拆解和视频生成 | P0 |
| 爆款内容拆解助手 | 视频/文章爆款要素分析 | P1 |
| 项目汇报助手 | 工作汇报/周报/月报生成 | P1 |
| 新品设计辅助 | 产品创意、卖点提炼 | P1 |
| 财务效率助手 | 财务问答、报表解读 | P2 |
| 店铺运营助手 | 产品描述优化、运营建议 | P2 |
| 数据分析助手 | 经营数据问答、趋势分析 | P2 |

---

## 2. 技术栈

### 2.1 后端

```
语言框架      Python 3.12+  + FastAPI 0.115+
Agent框架     LangGraph 0.3+ / DeepAgents（复杂Agent）
LLM抽象       LiteLLM + LangChain 0.3+ + OpenAI-compatible Adapter
LLM网关       AgentHive LLM Gateway（策略/路由/预算/费用/审计）
可观测性      LangSmith（Agent链路追踪）
业务数据库    PostgreSQL 16+（唯一业务主库）
嵌入式数据库  SQLite 3（仅限本地缓存/边缘插件/单机工具状态，不存核心业务数据）
向量库        PostgreSQL + pgvector（默认向量存储）
缓存/队列     Redis 7+
异步任务      Celery 5+ + Redis Broker
文件存储      MinIO（S3兼容，私有化对象存储）
RAG引擎       RAGFlow（通过HTTP API调用，引擎无关设计）
数据迁移      Alembic
依赖管理      uv + pyproject.toml
类型检查      mypy（严格模式）
代码格式      ruff
```

### 2.2 前端

```
框架          React 19
语言          TypeScript 5.5+（严格模式）
样式          Tailwind CSS 4
基础UI        shadcn/ui
底层交互      Radix UI
图标          lucide-react
状态管理      Zustand 5
服务端状态    TanStack Query v5
路由          React Router v7
表单          React Hook Form + Zod
实时通信      SSE（流式输出）/ WebSocket（Channel消息）
构建工具      Vite 6
代码格式      Biome
```

### 2.3 基础设施

```
容器          Docker 27+ / Docker Compose v2
反向代理      Nginx 1.26+
进程管理      内置Docker健康检查 + 自动重启
监控          Prometheus + Grafana（可选，高级版）
日志          结构化JSON → 本地文件 → 可选ELK
```

### 2.4 版本约束

- Python 最低 3.12，禁止使用 3.11 及以下特性
- 所有依赖锁定到 minor 版本，patch 版本可浮动
- 禁止使用任何需要境外网络访问的服务（私有化部署原则）

### 2.5 存储边界

- 业务主库：必须使用 PostgreSQL，包含租户、用户、部门、权限、Agent、知识库元数据、对话、审计、模型用量、费用账本等核心数据。
- 嵌入式数据库：SQLite 只允许用于本地单机组件、临时缓存、插件私有状态、离线安装器状态，不得承载多租户核心业务表。
- 向量库：默认使用 PostgreSQL + pgvector；即使接入RAGFlow，也必须保留 pgvector 作为可替换/兜底向量存储方案。
- 对象存储：默认使用 MinIO，所有上传文件、解析原文、导出文件、头像、Channel附件都走 MinIO，不得落在应用容器本地磁盘作为长期存储。
- Redis：仅用于缓存、限流、队列、短期会话状态，不得作为权威业务数据源。

### 2.6 大模型供应商覆盖

AgentHive 必须支持全球主流大模型，并允许客户接入私有模型和任意 OpenAI-compatible Endpoint。

| 类型 | 必须支持 |
|------|----------|
| 国际主流 | OpenAI GPT、Anthropic Claude、Google Gemini、Azure OpenAI、AWS Bedrock、Google Vertex AI、Mistral、Cohere、xAI |
| 国内主流 | Qwen/通义千问、DeepSeek、Kimi/月之暗面、MiniMax、GLM/智谱、Doubao/火山、百度千帆/文心、腾讯混元、讯飞星火 |
| 聚合平台 | OpenRouter、Together AI、Fireworks、Groq、Novita、硅基流动、302.AI 等 |
| 本地/私有 | Ollama、vLLM、SGLang、LM Studio、Xinference、LocalAI、自建 OpenAI-compatible 服务 |

实现优先级：

1. LiteLLM Proxy / LiteLLM SDK：作为默认多模型协议适配层。
2. OpenAI-compatible Adapter：覆盖国产模型、聚合平台、自建网关。
3. Native Adapter：仅当供应商能力无法通过 LiteLLM 或 OpenAI-compatible 表达时实现。

---

## 3. 架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                     Channel 层                           │
│  企业微信  钉钉  飞书  淘宝旺旺  网页Widget  REST API     │
│  Telegram  小程序  MCP Server                            │
└──────────────────────┬──────────────────────────────────┘
                        │ 统一消息格式 UnifiedMessage
┌──────────────────────▼──────────────────────────────────┐
│               Channel Gateway                            │
│  消息标准化 / 会话路由 / 租户识别 / 限流                  │
└──────────────────────┬──────────────────────────────────┘
                        │
┌──────────────────────▼──────────────────────────────────┐
│             FastAPI 应用层（单体）                        │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Auth/RBAC   │  │  业务API     │  │  Admin API     │  │
│  │ 认证/权限   │  │  对话/知识库  │  │  用户/组织/审计│  │
│  └──────┬──────┘  └──────┬───────┘  └────────────────┘  │
│         └────────────────┼──────────────────────────────┘
│                           │
┌──────────────────────────▼──────────────────────────────┐
│              Agent 编排层                                 │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │            Agent Registry（注册中心）              │   │
│  │  发现/路由/健康检查/版本管理                       │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │
│  │ 官方Agent  │  │ 自建Agent  │  │  Agent Builder     │  │
│  │ 客服/HR/   │  │ 低代码     │  │  （低代码引擎）     │  │
│  │ 文案/...   │  │ 用户定制   │  │                    │  │
│  └──────┬─────┘  └─────┬──────┘  └────────────────────┘  │
│         └──────────────┘                                  │
│                  │                                        │
│  ┌───────────────▼──────────────────────────────────┐    │
│  │              Tool Registry（工具注册）             │    │
│  │  RAG Tools │ Skill Tools │ MCP Tools │ API Tools  │    │
│  └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│              Policy & Governance                         │
│  RBAC/ABAC │ 部门/人员策略 │ 模型预算 │ Token限流 │ 审计  │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                Platform Core（底层能力）                   │
│                                                          │
│  ┌───────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ RAG引擎   │  │ LLM网关  │  │ 文件存储  │  │ 向量库 │  │
│  │ Adapter   │  │ 多模型治理│  │ MinIO    │  │pgvector│  │
│  │（可替换） │  │ LiteLLM   │  │          │  │        │  │
│  └───────────┘  └──────────┘  └──────────┘  └────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 3.2 单体设计原则

本项目是**单体应用**，不是微服务。所有模块在同一个 Python 进程内运行，通过内部函数调用而非 HTTP 通信。

- 外部服务（RAGFlow、MinIO、Redis、PostgreSQL）通过网络调用
- Agent 是逻辑模块，不是独立进程
- Channel 接入通过 Webhook 回调，不需要独立进程
- 平台能力必须模块解耦，业务层只能依赖接口和服务契约，不能直接绑定具体LLM/RAG/Channel实现
- 新增模型供应商、Channel、RAG引擎、Skill、Agent类型时，优先新增 Adapter/Plugin/Registry 配置，不改核心业务流程

### 3.3 引擎无关设计

所有底层引擎通过 Adapter 接口隔离，上层业务永远只调用接口：

```python
# 所有RAG引擎必须实现此接口
class BaseRAGAdapter(ABC):
    @abstractmethod
    async def ingest(self, kb_id: str, file: UploadFile) -> IngestResult: ...
    
    @abstractmethod
    async def retrieve(self, kb_id: str, query: str, top_k: int = 5) -> list[Chunk]: ...
    
    @abstractmethod
    async def delete_document(self, kb_id: str, doc_id: str) -> bool: ...
    
    @abstractmethod
    async def health_check(self) -> HealthStatus: ...

# LLM引擎接口
class BaseLLMAdapter(ABC):
    @abstractmethod
    async def chat(self, messages: list[Message], **kwargs) -> LLMResponse: ...
    
    @abstractmethod
    async def stream_chat(self, messages: list[Message], **kwargs) -> AsyncIterator[str]: ...
```

### 3.4 LLM网关与模型治理

所有模型调用必须经过 AgentHive LLM Gateway，Agent、Channel、RAG、Skill 不得直接调用第三方模型SDK。

LLM Gateway职责：

```
模型目录       供应商、模型、上下文窗口、能力标签、价格、可用状态
凭据管理       租户/部门级API Key加密存储、脱敏展示、轮换和禁用
策略引擎       按租户/部门/人员/角色/Agent/Channel控制可用模型和参数
预算控制       调用前预估、调用中限流、调用后结算，支持日/月/自定义周期
路由与降级     按成本/质量/延迟/地区/合规要求选择模型，支持fallback
用量审计       每次请求记录模型、Token、费用、调用方、部门、来源、错误
```

图片/视频生成必须复用同一套治理理念，但通过 **AgentHive Media Generation Gateway** 承载异步任务、参考素材、输出资产和模型特有参数。图片/视频 Agent 不得直接调用 OpenAI、Google、火山引擎或其他供应商 SDK；必须先经过权限、License、预算、路由、审计和对象存储规划。

Media Generation Gateway 必须支持：

```text
模型目录       ChatGPT Images 2.0、Nano Banana、Seedance 2.0、私有/兼容媒体模型
输入资产       文本提示词、自然语言需求、参考图、参考视频、原始视频素材
参数控制       图片数量、比例、分辨率、视频时长、帧率、分辨率、种子、负向提示词
任务模式       同步图片生成、异步视频生成、素材拆解后生成
产物管理       输出图片/视频/中间帧/任务日志统一写入 MinIO
成本治理       按租户/部门/人员/Agent统计媒体生成次数、时长、资产数量和费用
```

调用链路：

```text
User/Channel → Auth/RBAC → Agent → Policy Engine
  → Budget Guard → Model Router → LiteLLM/OpenAI-compatible/Native Adapter
  → Usage Collector → Cost Ledger → Audit Log
```

策略优先级：

```text
显式Deny > 用户策略 > Agent策略 > Channel策略 > 部门策略 > 租户策略 > 系统默认策略
```

#### 3.4.1 LLM 网关熔断器（Provider 级限流与熔断）

LLM Gateway 内置进程级熔断器（`app/llm/circuit_breaker.py`），按 `deployment_id` 独立跟踪每个部署的调用健康度，避免单一故障 Provider/部署拖垮整网关。

状态机（每部署独立）：

```text
CLOSED     正常放行；连续失败累计达到 failure_threshold 后跳转 OPEN
OPEN       路由阶段直接跳过该部署；持续 cooldown_seconds 后跳转 HALF_OPEN
HALF_OPEN  放行探测请求；连续成功 success_threshold 次后回 CLOSED，
           任一失败立即回 OPEN 并重置冷却时钟
```

集成点：

- `ModelRouter.plan()` 过滤 OPEN 状态部署；当全部部署 OPEN 时保留原候选集合，作为最后兜底，避免完全阻断服务。
- `LLMGateway.chat()` / `LLMGateway.test_connection()` 在每次调用后调用 `record_success` / `record_failure`，驱动状态转换。
- 配置通过 `app/core/config.py` 的 settings 注入，应用启动时（`app/main.py`）调用 `circuit_breaker.configure(...)` 应用阈值与开关。

配置项（环境变量，支持 `LLM_CIRCUIT_BREAKER_*` 与 `AGENTHIVE_LLM_CIRCUIT_BREAKER_*` 前缀）：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_CIRCUIT_BREAKER_ENABLED` | `true` | 熔断器总开关；关闭后所有部署视为健康 |
| `LLM_CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | 连续失败多少次后打开熔断 |
| `LLM_CIRCUIT_BREAKER_COOLDOWN_SECONDS` | `30` | OPEN 状态持续时间，到期后进入 HALF_OPEN 探测 |
| `LLM_CIRCUIT_BREAKER_SUCCESS_THRESHOLD` | `2` | HALF_OPEN 阶段连续成功多少次后关闭熔断 |

运维端点（`app/api/v1/router.py`）：

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/llm/circuit-breaker` | `MODELS_READ` | 查看所有部署熔断状态快照（含连续失败数、`seconds_until_half_open` 等） |
| POST | `/api/v1/llm/circuit-breaker/{deployment_id}/reset` | `MODELS_WRITE` | 重置单部署熔断状态（运维逃生通道） |

熔断器为进程级单例（`circuit_breaker`），状态仅在进程内有效，重启后清空；多实例部署时各实例独立计数。

### 3.5 LiteLLM使用原则

LiteLLM 是推荐的模型协议适配层，但不是 AgentHive 的业务控制平面。

- AgentHive负责：租户、部门、人员、角色、Agent、知识库权限、License、业务预算、审计、成本中心。
- LiteLLM负责：多供应商协议转换、OpenAI兼容接口、虚拟Key、供应商fallback、基础限流、模型价格映射和底层调用日志。
- AgentHive数据库是费用和权限的最终事实来源；LiteLLM账单数据只能作为采集来源或校验来源。
- 私有化部署时，LiteLLM必须作为本地容器或本地Python依赖运行，不得依赖外部托管网关。

LiteLLM映射建议：

| AgentHive概念 | LiteLLM概念 |
|---------------|-------------|
| tenant | organization |
| department / cost_center | team |
| user | user / customer |
| agent / channel / conversation | metadata / tags |
| budget policy | key/team/user/org budget |

---

## 4. 项目结构

```
agenthive/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI 应用入口
│   │   │
│   │   ├── core/                      # 核心配置和基础设施
│   │   │   ├── config.py              # 环境变量 / Pydantic Settings
│   │   │   ├── database.py            # PostgreSQL 连接池（asyncpg）
│   │   │   ├── redis.py               # Redis 连接
│   │   │   ├── minio.py               # MinIO 客户端
│   │   │   ├── security.py            # JWT / 密码加密 / License验证
│   │   │   ├── exceptions.py          # 全局异常定义
│   │   │   └── constants.py           # 全局常量
│   │   │
│   │   ├── api/                       # HTTP路由层
│   │   │   ├── deps.py                # 公共依赖（get_current_user等）
│   │   │   └── v1/
│   │   │       ├── router.py          # 路由聚合
│   │   │       ├── auth.py            # 登录/注册/刷新Token/注销
│   │   │       ├── users.py           # 用户CRUD
│   │   │       ├── orgs.py            # 组织/部门管理
│   │   │       ├── roles.py           # 角色/权限管理
│   │   │       ├── agents.py          # Agent配置/发布/管理
│   │   │       ├── knowledge.py       # 知识库/文档管理
│   │   │       ├── chat.py            # 对话（SSE流式）
│   │   │       ├── channels.py        # Channel配置管理
│   │   │       ├── skills.py          # Skill管理
│   │   │       ├── analytics.py       # 数据统计看板
│   │   │       ├── audit.py           # 审计日志查询
│   │   │       └── admin.py           # 超级管理员接口
│   │   │
│   │   ├── agents/                    # Agent层
│   │   │   ├── registry.py            # Agent注册中心
│   │   │   ├── base.py                # Agent基类
│   │   │   ├── executor.py            # Agent执行引擎
│   │   │   ├── catalog.py             # Agent模块目录/选装/授权状态
│   │   │   ├── builder/               # 低代码Agent构建引擎
│   │   │   │   ├── engine.py          # Builder核心逻辑
│   │   │   │   ├── validator.py       # 配置验证
│   │   │   │   └── renderer.py        # 配置→LangGraph转换
│   │   │   │
│   │   │   └── official/              # 官方内置Agent
│   │   │       ├── customer_service/
│   │   │       │   ├── agent.py       # Agent主入口
│   │   │       │   ├── graph.py       # LangGraph图定义
│   │   │       │   ├── nodes.py       # 图节点函数
│   │   │       │   ├── state.py       # 状态Schema
│   │   │       │   └── tools.py       # 专属工具
│   │   │       ├── hr_screening/
│   │   │       ├── copywriting/
│   │   │       ├── content_analysis/
│   │   │       ├── report_writer/
│   │   │       └── data_analyst/
│   │   │
│   │   ├── channels/                  # Channel接入层
│   │   │   ├── gateway.py             # 消息标准化网关（核心）
│   │   │   ├── models.py              # UnifiedMessage定义
│   │   │   ├── router.py              # 消息→Agent路由
│   │   │   ├── wecom.py               # 企业微信
│   │   │   ├── dingtalk.py            # 钉钉
│   │   │   ├── feishu.py              # 飞书
│   │   │   ├── web_widget.py          # 网页Widget
│   │   │   └── webhook.py             # 通用Webhook
│   │   │
│   │   ├── rag/                       # RAG引擎适配层
│   │   │   ├── base.py                # BaseRAGAdapter接口
│   │   │   ├── ragflow.py             # RAGFlow实现
│   │   │   └── router.py             # 多引擎路由（按租户）
│   │   │
│   │   ├── llm/                       # LLM网关层（所有模型调用必须经过这里）
│   │   │   ├── base.py                # BaseLLMAdapter接口
│   │   │   ├── gateway.py             # LLM统一入口（策略/预算/审计）
│   │   │   ├── router.py              # 多模型路由/故障转移/降级
│   │   │   ├── policy.py              # 模型使用策略解析
│   │   │   ├── budget.py              # 调用前预算检查/预占/结算
│   │   │   ├── pricing.py             # 模型价格表和费用计算
│   │   │   ├── usage.py               # 用量采集和账本写入
│   │   │   ├── litellm_adapter.py     # LiteLLM Proxy/SDK适配
│   │   │   ├── openai_compatible.py   # 通用OpenAI兼容端点
│   │   │   ├── native/                # 必要时才写原生SDK适配
│   │   │   │   ├── openai.py
│   │   │   │   ├── anthropic.py
│   │   │   │   ├── gemini.py
│   │   │   │   ├── qwen.py
│   │   │   │   ├── minimax.py
│   │   │   │   ├── glm.py
│   │   │   │   ├── deepseek.py
│   │   │   │   ├── kimi.py
│   │   │   │   └── ollama.py
│   │   │   └── schemas.py             # LLM请求/响应/usage标准Schema
│   │   │
│   │   ├── skills/                    # Skill工具库
│   │   │   ├── registry.py            # Skill注册中心
│   │   │   ├── base.py                # BaseSkill接口
│   │   │   ├── mcp_client.py          # MCP协议客户端
│   │   │   └── builtin/               # 内置Skill
│   │   │       ├── search.py          # 网页搜索
│   │   │       ├── calculator.py      # 计算工具
│   │   │       ├── file_reader.py     # 文件读取
│   │   │       └── http_request.py    # HTTP请求
│   │   │
│   │   ├── models/                    # SQLModel数据模型
│   │   │   ├── base.py                # 基础Model（id, created_at等）
│   │   │   ├── tenant.py              # 租户/企业
│   │   │   ├── user.py                # 用户
│   │   │   ├── org.py                 # 组织/部门
│   │   │   ├── role.py                # 角色/权限
│   │   │   ├── agent.py               # Agent配置
│   │   │   ├── knowledge.py           # 知识库/文档
│   │   │   ├── conversation.py        # 对话/消息
│   │   │   ├── channel.py             # Channel配置
│   │   │   ├── llm.py                 # LLM供应商/模型/部署/策略/预算
│   │   │   ├── cost.py                # 成本中心/费用账本
│   │   │   └── audit_log.py           # 审计日志
│   │   │
│   │   ├── middleware/                # FastAPI中间件
│   │   │   ├── audit.py               # 审计日志记录
│   │   │   ├── rate_limit.py          # 请求限流
│   │   │   ├── tenant.py              # 租户识别
│   │   │   └── request_id.py          # 请求ID注入
│   │   │
│   │   └── services/                  # 业务服务层
│   │       ├── auth_service.py
│   │       ├── user_service.py
│   │       ├── org_service.py
│   │       ├── agent_service.py
│   │       ├── knowledge_service.py
│   │       ├── conversation_service.py
│   │       ├── channel_service.py
│   │       ├── llm_service.py
│   │       ├── budget_service.py
│   │       ├── cost_service.py
│   │       ├── analytics_service.py
│   │       └── license_service.py
│   │
│   ├── migrations/                    # Alembic数据库迁移
│   │   ├── env.py
│   │   └── versions/
│   │
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   │
│   ├── scripts/
│   │   ├── init_db.py                 # 数据库初始化
│   │   ├── create_admin.py            # 创建超级管理员
│   │   └── seed_data.py               # 初始数据
│   │
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── app/                       # 页面路由
│   │   │   ├── (auth)/
│   │   │   │   ├── login/
│   │   │   │   └── setup/             # 首次安装向导
│   │   │   └── (dashboard)/
│   │   │       ├── layout.tsx
│   │   │       ├── agents/            # Agent管理
│   │   │       ├── knowledge/         # 知识库管理
│   │   │       ├── channels/          # Channel配置
│   │   │       ├── users/             # 用户管理
│   │   │       ├── analytics/         # 数据看板
│   │   │       └── settings/          # 系统设置
│   │   │
│   │   ├── chat/                      # 独立对话页面
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                    # shadcn/ui组件
│   │   │   ├── agents/
│   │   │   ├── knowledge/
│   │   │   ├── chat/
│   │   │   │   ├── ChatWindow.tsx     # 对话主窗口（SSE流式）
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   └── SourceCard.tsx     # 知识来源展示
│   │   │   └── layout/
│   │   │
│   │   ├── lib/
│   │   │   ├── api/                   # API请求封装（TanStack Query）
│   │   │   ├── auth/                  # 认证逻辑
│   │   │   ├── i18n/                  # zh-CN / en-US 国际化资源
│   │   │   └── utils/
│   │   │
│   │   ├── hooks/
│   │   │   ├── useStreamChat.ts       # SSE流式对话
│   │   │   ├── usePermission.ts       # 权限判断
│   │   │   └── useAgentConfig.ts
│   │   │
│   │   └── stores/
│   │       ├── auth.ts                # 认证状态
│   │       └── ui.ts                  # UI状态
│   │
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── docker-compose.yml                 # 生产部署
├── docker-compose.dev.yml             # 开发环境
├── nginx/
│   └── nginx.conf
├── scripts/
│   ├── install.sh                     # 一键安装脚本
│   ├── upgrade.sh                     # 升级脚本
│   └── diagnose.sh                    # 诊断脚本
└── docs/
    ├── deployment.md
    └── api.md
```

---

## 5. 数据库设计

### 5.1 设计原则

- 所有表必须有 `id`（UUID）、`created_at`、`updated_at`
- 多租户隔离：所有业务表必须有 `tenant_id` 字段
- 软删除：重要数据用 `deleted_at` 而非物理删除
- 审计日志表只允许 INSERT，禁止 UPDATE/DELETE
- 使用 SQLModel（Pydantic + SQLAlchemy 合体）定义模型

### 5.2 核心表结构

```sql
-- ============================================================
-- 租户与授权
-- ============================================================

CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    slug            VARCHAR(50) UNIQUE NOT NULL,       -- 租户标识符
    license_key     TEXT,                               -- License密钥
    license_type    VARCHAR(20) DEFAULT 'basic',        -- basic/standard/pro
    license_expires_at TIMESTAMPTZ,
    max_users       INTEGER DEFAULT 50,
    max_agents      INTEGER DEFAULT 5,
    max_kb_size_gb  DECIMAL(10,2) DEFAULT 5.0,
    config          JSONB DEFAULT '{}',                -- 租户级配置
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE licenses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id),
    license_key_hash TEXT NOT NULL UNIQUE,           -- 不保存明文License
    license_type    VARCHAR(30) NOT NULL,            -- standard/pro/enterprise/custom
    customer_name   VARCHAR(150) NOT NULL,
    deployment_id   UUID NOT NULL,                   -- 授权部署ID
    install_id      UUID,                            -- 首次安装时生成
    machine_fingerprint_hash TEXT,                   -- 机器指纹Hash，不保存原始硬件信息
    allowed_modules JSONB NOT NULL DEFAULT '[]',     -- 授权模块，如 agent.customer_service
    allowed_features JSONB NOT NULL DEFAULT '[]',    -- 授权功能，如 wecom/budget/ha
    max_activations INTEGER DEFAULT 1,
    maintenance_until TIMESTAMPTZ,                   -- 可免费升级/获取补丁的截止时间
    expires_at      TIMESTAMPTZ,                     -- NULL表示永久授权当前大版本
    issued_at       TIMESTAMPTZ NOT NULL,
    activated_at    TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'inactive',  -- inactive/active/expired/revoked/mismatch
    signature_alg   VARCHAR(30) DEFAULT 'RSA-SHA256',
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE license_activations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID REFERENCES tenants(id),
    license_id      UUID NOT NULL REFERENCES licenses(id),
    deployment_id   UUID NOT NULL,
    install_id      UUID NOT NULL,
    machine_fingerprint_hash TEXT NOT NULL,
    activation_mode VARCHAR(20) DEFAULT 'offline',   -- offline/online/manual
    activation_code_hash TEXT,                       -- 离线激活请求码Hash
    status          VARCHAR(20) DEFAULT 'active',    -- active/revoked/mismatch
    first_seen_at   TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at    TIMESTAMPTZ DEFAULT NOW(),
    metadata        JSONB NOT NULL DEFAULT '{}'
);

-- ============================================================
-- 用户与认证
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    email           VARCHAR(255) NOT NULL,
    username        VARCHAR(50),
    hashed_password TEXT NOT NULL,
    full_name       VARCHAR(100),
    avatar_url      TEXT,
    phone           VARCHAR(20),
    is_super_admin  BOOLEAN DEFAULT false,             -- 平台超管
    is_tenant_admin BOOLEAN DEFAULT false,             -- 企业管理员
    is_active       BOOLEAN DEFAULT true,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE(tenant_id, email)
);

-- ============================================================
-- 组织架构
-- ============================================================

CREATE TABLE departments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    parent_id       UUID REFERENCES departments(id),   -- 支持多级部门
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    sort_order      INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE cost_centers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    department_id   UUID REFERENCES departments(id),
    code            VARCHAR(50) NOT NULL,
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    monthly_budget_usd DECIMAL(12,4),
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, code)
);

CREATE TABLE user_departments (
    user_id         UUID REFERENCES users(id),
    department_id   UUID REFERENCES departments(id),
    is_leader       BOOLEAN DEFAULT false,
    is_primary      BOOLEAN DEFAULT false,            -- 成本归属/默认部门
    position_title  VARCHAR(100),
    cost_center_id  UUID REFERENCES cost_centers(id),
    PRIMARY KEY (user_id, department_id)
);

-- ============================================================
-- 权限（RBAC）
-- ============================================================

CREATE TABLE roles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            VARCHAR(50) NOT NULL,
    description     TEXT,
    permissions     JSONB DEFAULT '[]',               -- 权限列表
    is_system       BOOLEAN DEFAULT false,            -- 系统内置角色不可删
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_roles (
    user_id         UUID REFERENCES users(id),
    role_id         UUID REFERENCES roles(id),
    granted_by      UUID REFERENCES users(id),
    granted_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);

-- ============================================================
-- 知识库
-- ============================================================

CREATE TABLE knowledge_bases (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    department_id   UUID REFERENCES departments(id),  -- 部门归属（可选）
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    engine_type     VARCHAR(20) DEFAULT 'ragflow',    -- ragflow / custom
    engine_kb_id    TEXT,                             -- 底层引擎的KB ID
    chunk_method    VARCHAR(20) DEFAULT 'naive',      -- 分块策略
    embedding_model VARCHAR(100),
    is_public       BOOLEAN DEFAULT false,            -- 企业内公开
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id           UUID NOT NULL REFERENCES knowledge_bases(id),
    tenant_id       UUID NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    file_size       BIGINT,
    file_type       VARCHAR(50),
    storage_path    TEXT NOT NULL,                   -- MinIO路径
    engine_doc_id   TEXT,                            -- 底层引擎的文档ID
    status          VARCHAR(20) DEFAULT 'pending',   -- pending/processing/ready/failed
    chunk_count     INTEGER DEFAULT 0,
    error_message   TEXT,
    uploaded_by     UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Agent
-- ============================================================

CREATE TABLE agents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    avatar_url      TEXT,
    agent_type      VARCHAR(50) NOT NULL,            -- customer_service/hr/copywriting/custom
    status          VARCHAR(20) DEFAULT 'draft',     -- draft/published/disabled
    config          JSONB NOT NULL DEFAULT '{}',     -- Agent完整配置
    -- config包含：system_prompt, llm_model, temperature,
    --             knowledge_base_ids[], skill_ids[], mcp_servers[]
    --             escalation_rules, response_style, language
    version         INTEGER DEFAULT 1,
    is_official     BOOLEAN DEFAULT false,           -- 官方内置Agent
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE agent_modules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_key      VARCHAR(100) NOT NULL UNIQUE,    -- customer_service/hr_screening/copywriting
    name            VARCHAR(100) NOT NULL,
    display_name_i18n JSONB NOT NULL DEFAULT '{}',
    description_i18n JSONB NOT NULL DEFAULT '{}',
    category        VARCHAR(50) NOT NULL,            -- official/industry/custom/marketplace
    module_type     VARCHAR(50) NOT NULL,            -- official_agent/template_pack/plugin
    version         VARCHAR(30) NOT NULL,
    min_platform_version VARCHAR(30),
    license_feature_key VARCHAR(100),                -- License中对应的授权功能
    default_config  JSONB NOT NULL DEFAULT '{}',
    required_capabilities JSONB NOT NULL DEFAULT '[]', -- rag/tools/vision/long_context等
    supported_locales JSONB NOT NULL DEFAULT '["zh-CN", "en-US"]',
    is_builtin      BOOLEAN DEFAULT false,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE tenant_agent_modules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    module_id       UUID NOT NULL REFERENCES agent_modules(id),
    install_status  VARCHAR(20) DEFAULT 'not_installed', -- not_installed/installed/enabled/disabled/expired
    installed_by    UUID REFERENCES users(id),
    installed_at    TIMESTAMPTZ,
    enabled_at      TIMESTAMPTZ,
    config          JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, module_id)
);

CREATE TABLE agent_departments (
    agent_id        UUID REFERENCES agents(id),
    department_id   UUID REFERENCES departments(id),
    PRIMARY KEY (agent_id, department_id)
);

-- 允许哪些用户/角色使用此Agent
CREATE TABLE agent_permissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        UUID NOT NULL REFERENCES agents(id),
    target_type     VARCHAR(10) NOT NULL,            -- user/role/department
    target_id       UUID NOT NULL,
    can_use         BOOLEAN DEFAULT true,
    can_configure   BOOLEAN DEFAULT false
);

-- 通用资源权限（用于知识库/模型/Skill/Channel等资源级ACL）
CREATE TABLE resource_permissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    resource_type   VARCHAR(50) NOT NULL,            -- agent/knowledge_base/model/channel/skill
    resource_id     UUID NOT NULL,
    target_type     VARCHAR(20) NOT NULL,            -- user/role/department/tenant
    target_id       UUID NOT NULL,
    actions         JSONB NOT NULL DEFAULT '[]',     -- read/use/update/delete/configure
    effect          VARCHAR(10) DEFAULT 'allow',     -- allow/deny
    conditions      JSONB NOT NULL DEFAULT '{}',     -- ABAC条件，如仅本部门/下级部门
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Channel（消息渠道）
-- ============================================================

CREATE TABLE channels (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    agent_id        UUID NOT NULL REFERENCES agents(id),
    name            VARCHAR(100) NOT NULL,
    channel_type    VARCHAR(30) NOT NULL,           -- wecom/dingtalk/feishu/web_widget/webhook
    config          JSONB NOT NULL DEFAULT '{}',   -- 各渠道的具体配置（加密存储）
    webhook_url     TEXT,                           -- 系统生成的Webhook接收地址
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 对话与消息
-- ============================================================

CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    agent_id        UUID NOT NULL REFERENCES agents(id),
    channel_id      UUID REFERENCES channels(id),
    user_id         UUID REFERENCES users(id),      -- 内部用户（可为空，外部用户无账号）
    external_user_id TEXT,                           -- 外部渠道用户ID
    external_user_name TEXT,
    channel_type    VARCHAR(30),
    title           VARCHAR(255),                   -- 对话标题（首条消息截取）
    message_count   INTEGER DEFAULT 0,
    total_tokens    INTEGER DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'active',   -- active/closed/escalated
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    tenant_id       UUID NOT NULL,
    role            VARCHAR(10) NOT NULL,            -- user/assistant/system
    content         TEXT NOT NULL,
    content_type    VARCHAR(20) DEFAULT 'text',      -- text/image/file
    -- Agent元数据
    agent_id        UUID REFERENCES agents(id),
    model_name      VARCHAR(100),
    prompt_tokens   INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    latency_ms      INTEGER,
    -- RAG检索来源
    sources         JSONB DEFAULT '[]',             -- [{doc_id, chunk, score, filename}]
    -- 质量反馈
    feedback        VARCHAR(10),                    -- good/bad/null
    feedback_note   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Skill
-- ============================================================

CREATE TABLE skills (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID,                           -- NULL=全平台内置
    name            VARCHAR(100) NOT NULL,
    slug            VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    skill_type      VARCHAR(20) NOT NULL,           -- builtin/mcp/api/custom
    impl_config     JSONB NOT NULL DEFAULT '{}',   -- 实现配置（端点/协议/参数）
    input_schema    JSONB,                          -- JSON Schema
    output_schema   JSONB,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 审计日志（不可篡改）
-- ============================================================

CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID,
    user_id         UUID,
    user_email      VARCHAR(255),
    user_ip         INET,
    user_agent      TEXT,
    request_id      UUID,
    action          VARCHAR(100) NOT NULL,          -- CREATE_KB / DELETE_USER / LOGIN 等
    resource_type   VARCHAR(50),                    -- knowledge_base / user / agent 等
    resource_id     UUID,
    resource_name   VARCHAR(255),
    old_value       JSONB,                          -- 变更前（可选）
    new_value       JSONB,                          -- 变更后（可选）
    status          VARCHAR(10) DEFAULT 'success',  -- success / failed
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
    -- 注意：此表无 updated_at，禁止更新
);

-- 分区索引（按月）
CREATE INDEX idx_audit_logs_tenant_created ON audit_logs(tenant_id, created_at DESC);
CREATE INDEX idx_audit_logs_user_created ON audit_logs(user_id, created_at DESC);

-- ============================================================
-- LLM模型治理、预算与使用量追踪
-- ============================================================

CREATE TABLE llm_providers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID,                           -- NULL=平台内置供应商模板
    name            VARCHAR(100) NOT NULL,          -- OpenAI/Anthropic/Gemini/Qwen/DeepSeek/Kimi等
    provider_type   VARCHAR(50) NOT NULL,           -- openai/anthropic/gemini/litellm/openai_compatible/ollama
    base_url        TEXT,
    region          VARCHAR(50),                    -- cn/us/eu/apac/local
    is_builtin      BOOLEAN DEFAULT false,
    is_active       BOOLEAN DEFAULT true,
    config          JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE llm_credentials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    provider_id     UUID NOT NULL REFERENCES llm_providers(id),
    department_id   UUID REFERENCES departments(id),
    name            VARCHAR(100) NOT NULL,
    encrypted_secret TEXT NOT NULL,                 -- AES-256加密后的API Key/凭据
    secret_preview  VARCHAR(20),                    -- sk-***abcd
    scope_type      VARCHAR(20) DEFAULT 'tenant',   -- tenant/department/system
    is_active       BOOLEAN DEFAULT true,
    expires_at      TIMESTAMPTZ,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE llm_models (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id     UUID REFERENCES llm_providers(id),
    model_key       VARCHAR(150) NOT NULL,          -- 平台内部唯一标识，如 openai/gpt-4o-mini
    display_name    VARCHAR(150) NOT NULL,
    model_family    VARCHAR(80),                    -- gpt/claude/gemini/qwen/deepseek/kimi/glm/minimax
    model_type      VARCHAR(30) DEFAULT 'chat',     -- chat/embedding/rerank/image/video/audio
    context_window  INTEGER,
    max_output_tokens INTEGER,
    supports_streaming BOOLEAN DEFAULT true,
    supports_tools BOOLEAN DEFAULT false,
    supports_json_mode BOOLEAN DEFAULT false,
    supports_vision BOOLEAN DEFAULT false,
    supports_reasoning BOOLEAN DEFAULT false,
    supports_embedding BOOLEAN DEFAULT false,
    supports_image_generation BOOLEAN DEFAULT false,
    supports_video_generation BOOLEAN DEFAULT false,
    is_active       BOOLEAN DEFAULT true,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(model_key)
);

CREATE TABLE llm_deployments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    provider_id     UUID NOT NULL REFERENCES llm_providers(id),
    credential_id   UUID REFERENCES llm_credentials(id),
    model_id        UUID NOT NULL REFERENCES llm_models(id),
    name            VARCHAR(100) NOT NULL,
    routing_key     VARCHAR(150) NOT NULL,          -- Agent配置中选择的逻辑模型名
    adapter_type    VARCHAR(50) NOT NULL,           -- litellm/openai_compatible/native/ollama
    litellm_model   VARCHAR(200),                   -- LiteLLM模型名，如 anthropic/claude-3-5-sonnet
    api_base        TEXT,
    priority        INTEGER DEFAULT 100,
    weight          INTEGER DEFAULT 1,
    timeout_seconds INTEGER DEFAULT 60,
    rpm_limit       INTEGER,
    tpm_limit       INTEGER,
    is_active       BOOLEAN DEFAULT true,
    config          JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE llm_model_prices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        UUID NOT NULL REFERENCES llm_models(id),
    currency        VARCHAR(10) DEFAULT 'USD',
    input_cost_per_1k_tokens DECIMAL(12,8) DEFAULT 0,
    output_cost_per_1k_tokens DECIMAL(12,8) DEFAULT 0,
    cached_input_cost_per_1k_tokens DECIMAL(12,8) DEFAULT 0,
    cache_write_cost_per_1k_tokens DECIMAL(12,8) DEFAULT 0,
    reasoning_cost_per_1k_tokens DECIMAL(12,8) DEFAULT 0,
    image_input_cost_per_1k DECIMAL(12,8) DEFAULT 0,
    image_output_cost_per_unit DECIMAL(12,8) DEFAULT 0,
    video_output_cost_per_second DECIMAL(12,8) DEFAULT 0,
    audio_input_cost_per_minute DECIMAL(12,8) DEFAULT 0,
    effective_from  TIMESTAMPTZ DEFAULT NOW(),
    effective_to    TIMESTAMPTZ,
    source          VARCHAR(50) DEFAULT 'manual',   -- manual/litellm/provider
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE llm_policies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            VARCHAR(100) NOT NULL,
    target_type     VARCHAR(20) NOT NULL,           -- tenant/department/user/role/agent/channel
    target_id       UUID,
    effect          VARCHAR(10) DEFAULT 'allow',    -- allow/deny
    allowed_model_ids JSONB DEFAULT '[]',
    denied_model_ids  JSONB DEFAULT '[]',
    max_prompt_tokens INTEGER,
    max_completion_tokens INTEGER,
    max_context_tokens INTEGER,
    max_cost_per_request_usd DECIMAL(10,4),
    rpm_limit       INTEGER,
    tpm_limit       INTEGER,
    allow_external_models BOOLEAN DEFAULT true,
    allow_reasoning_models BOOLEAN DEFAULT true,
    allow_vision_models BOOLEAN DEFAULT true,
    conditions      JSONB NOT NULL DEFAULT '{}',
    priority        INTEGER DEFAULT 100,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE llm_budgets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            VARCHAR(100) NOT NULL,
    scope_type      VARCHAR(20) NOT NULL,           -- tenant/department/user/agent/channel/cost_center
    scope_id        UUID,
    period          VARCHAR(20) NOT NULL,           -- daily/weekly/monthly/quarterly/yearly/custom
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    currency        VARCHAR(10) DEFAULT 'USD',
    max_cost        DECIMAL(12,4),
    max_tokens      BIGINT,
    alert_thresholds JSONB DEFAULT '[0.8, 0.9, 1.0]',
    action_on_exceed VARCHAR(20) DEFAULT 'block',   -- block/downgrade/alert_only
    fallback_model_id UUID REFERENCES llm_models(id),
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE llm_budget_ledger (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    budget_id       UUID NOT NULL REFERENCES llm_budgets(id),
    usage_id        UUID,
    entry_type      VARCHAR(20) NOT NULL,           -- reserve/settle/release/adjust
    tokens_delta    BIGINT DEFAULT 0,
    cost_delta      DECIMAL(12,6) DEFAULT 0,
    currency        VARCHAR(10) DEFAULT 'USD',
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE llm_usage (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    department_id   UUID REFERENCES departments(id),
    cost_center_id  UUID REFERENCES cost_centers(id),
    user_id         UUID,
    agent_id        UUID,
    channel_id      UUID,
    conversation_id UUID,
    message_id      UUID,
    provider_id     UUID REFERENCES llm_providers(id),
    model_id        UUID REFERENCES llm_models(id),
    deployment_id   UUID REFERENCES llm_deployments(id),
    model_name      VARCHAR(150) NOT NULL,
    request_type    VARCHAR(30) DEFAULT 'chat',     -- chat/embedding/rerank/image/video/audio
    prompt_tokens   INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    cached_input_tokens INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,
    reasoning_tokens INTEGER DEFAULT 0,
    total_tokens    INTEGER DEFAULT 0,
    image_count     INTEGER DEFAULT 0,
    video_seconds   INTEGER DEFAULT 0,
    audio_seconds   INTEGER DEFAULT 0,
    estimated_cost_usd DECIMAL(12,6) DEFAULT 0,
    final_cost_usd  DECIMAL(12,6) DEFAULT 0,
    latency_ms      INTEGER,
    status          VARCHAR(20) DEFAULT 'success',  -- success/failed/blocked/cancelled
    blocked_reason  TEXT,
    policy_id       UUID REFERENCES llm_policies(id),
    request_id      UUID,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_llm_usage_tenant_created ON llm_usage(tenant_id, created_at DESC);
CREATE INDEX idx_llm_usage_department_created ON llm_usage(department_id, created_at DESC);
CREATE INDEX idx_llm_usage_user_created ON llm_usage(user_id, created_at DESC);
CREATE INDEX idx_llm_usage_agent_created ON llm_usage(agent_id, created_at DESC);

-- ============================================================
-- 向量存储（pgvector，RAGFlow不用时的备选）
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id           UUID NOT NULL REFERENCES knowledge_bases(id),
    doc_id          UUID NOT NULL REFERENCES documents(id),
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(1536),                   -- OpenAI text-embedding-3-small
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_embeddings_kb_id ON embeddings(kb_id);
CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

---

## 6. API规范

### 6.1 基础约定

```
Base URL:     /api/v1
认证方式:     Bearer JWT Token（Header: Authorization: Bearer <token>）
内容类型:     application/json
字符编码:     UTF-8
时间格式:     ISO 8601（2026-01-01T00:00:00Z）
分页参数:     ?page=1&page_size=20
排序参数:     ?sort_by=created_at&sort_order=desc
```

### 6.2 响应格式

所有接口返回统一格式：

```typescript
// 成功
{
  "success": true,
  "data": <any>,
  "message": "操作成功"
}

// 分页
{
  "success": true,
  "data": {
    "items": [...],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "pages": 5
  }
}

// 错误
{
  "success": false,
  "error": {
    "code": "RESOURCE_NOT_FOUND",   // 业务错误码
    "message": "知识库不存在",
    "detail": {}                     // 可选，调试信息
  }
}
```

### 6.3 错误码定义

```
AUTH_FAILED           401  认证失败/Token过期
PERMISSION_DENIED     403  无权限
RESOURCE_NOT_FOUND    404  资源不存在
VALIDATION_ERROR      422  请求参数错误
RATE_LIMIT_EXCEEDED   429  请求频率超限
LICENSE_EXPIRED       402  License过期
LICENSE_LIMIT_REACHED 402  超出License限制
INTERNAL_ERROR        500  服务内部错误
RAG_ENGINE_ERROR      502  RAG引擎异常
LLM_ERROR             502  LLM调用异常
```

### 6.4 核心接口清单

```
认证
POST   /api/v1/auth/login              # 登录
POST   /api/v1/auth/logout             # 注销
POST   /api/v1/auth/refresh            # 刷新Token
GET    /api/v1/auth/me                 # 当前用户信息

用户管理
GET    /api/v1/users                   # 用户列表
POST   /api/v1/users                   # 创建用户（管理员）
GET    /api/v1/users/{id}              # 用户详情
PUT    /api/v1/users/{id}              # 更新用户
DELETE /api/v1/users/{id}              # 删除用户（软删除）
POST   /api/v1/users/{id}/reset-password # 重置密码

组织架构
GET    /api/v1/departments             # 部门树形列表
POST   /api/v1/departments             # 创建部门
PUT    /api/v1/departments/{id}        # 更新部门
DELETE /api/v1/departments/{id}        # 删除部门

知识库
GET    /api/v1/knowledge-bases         # 知识库列表
POST   /api/v1/knowledge-bases         # 创建知识库
GET    /api/v1/knowledge-bases/{id}    # 知识库详情
PUT    /api/v1/knowledge-bases/{id}    # 更新知识库
DELETE /api/v1/knowledge-bases/{id}    # 删除知识库
POST   /api/v1/knowledge-bases/{id}/documents     # 上传文档
GET    /api/v1/knowledge-bases/{id}/documents     # 文档列表
DELETE /api/v1/knowledge-bases/{id}/documents/{doc_id} # 删除文档
POST   /api/v1/knowledge-bases/{id}/test          # 检索测试

Agent
GET    /api/v1/agent-modules           # Agent模块目录（含可安装/已安装/未授权状态）
GET    /api/v1/agent-modules/{id}      # Agent模块详情
POST   /api/v1/agent-modules/{id}/install # 安装Agent模块
POST   /api/v1/agent-modules/{id}/enable  # 启用Agent模块
POST   /api/v1/agent-modules/{id}/disable # 禁用Agent模块
GET    /api/v1/agents                  # Agent列表
POST   /api/v1/agents                  # 创建Agent
GET    /api/v1/agents/{id}             # Agent详情
PUT    /api/v1/agents/{id}             # 更新Agent配置
DELETE /api/v1/agents/{id}             # 删除Agent
POST   /api/v1/agents/{id}/publish     # 发布Agent
POST   /api/v1/agents/{id}/disable     # 下线Agent
GET    /api/v1/agents/official         # 官方Agent模板列表

对话（SSE流式）
POST   /api/v1/chat/{agent_id}         # 发起对话（返回SSE流）
GET    /api/v1/conversations           # 对话历史列表
GET    /api/v1/conversations/{id}      # 对话详情+消息
DELETE /api/v1/conversations/{id}      # 删除对话
POST   /api/v1/messages/{id}/feedback  # 消息反馈（好/差评）

Channel
GET    /api/v1/channels                # Channel列表
POST   /api/v1/channels                # 创建Channel
PUT    /api/v1/channels/{id}           # 更新Channel
DELETE /api/v1/channels/{id}           # 删除Channel
POST   /api/v1/channels/{id}/test      # 测试Channel连通性

# Webhook接收（不需要认证，用签名验证）
POST   /api/v1/webhook/wecom/{channel_id}     # 企业微信消息接收
POST   /api/v1/webhook/dingtalk/{channel_id}  # 钉钉消息接收
POST   /api/v1/webhook/feishu/{channel_id}    # 飞书消息接收
POST   /api/v1/webhook/generic/{channel_id}   # 通用Webhook

LLM模型治理
GET    /api/v1/llm/providers           # 模型供应商列表
POST   /api/v1/llm/providers           # 新增供应商（管理员）
PUT    /api/v1/llm/providers/{id}      # 更新供应商
POST   /api/v1/llm/credentials         # 新增/轮换供应商凭据（加密存储）
GET    /api/v1/llm/models              # 模型目录
POST   /api/v1/llm/models/sync         # 从LiteLLM/供应商同步模型目录
GET    /api/v1/llm/deployments         # 可用模型部署列表
POST   /api/v1/llm/deployments         # 创建模型部署
POST   /api/v1/llm/deployments/{id}/test # 测试模型连通性
GET    /api/v1/llm/policies            # 模型使用策略
POST   /api/v1/llm/policies            # 创建策略
PUT    /api/v1/llm/policies/{id}       # 更新策略
GET    /api/v1/llm/prices              # 模型价格表
POST   /api/v1/llm/prices              # 新增/覆盖价格

预算与费用
GET    /api/v1/budgets                 # 预算列表（租户/部门/人员/Agent）
POST   /api/v1/budgets                 # 创建预算
PUT    /api/v1/budgets/{id}            # 更新预算
GET    /api/v1/budgets/{id}/usage      # 预算使用情况
GET    /api/v1/cost-centers            # 成本中心列表
POST   /api/v1/cost-centers            # 创建成本中心
GET    /api/v1/costs/ledger            # 费用流水

数据统计
GET    /api/v1/analytics/overview      # 总览数据
GET    /api/v1/analytics/conversations # 对话趋势
GET    /api/v1/analytics/agents        # Agent使用统计
GET    /api/v1/analytics/users         # 用户活跃度
GET    /api/v1/analytics/tokens        # Token消耗统计
GET    /api/v1/analytics/costs         # 费用统计（租户/部门/人员/Agent/模型）
GET    /api/v1/analytics/models        # 模型调用质量/延迟/错误率/成本
GET    /api/v1/analytics/departments   # 部门级用量和费用

审计日志
GET    /api/v1/audit-logs              # 审计日志列表（管理员）
GET    /api/v1/audit-logs/export       # 导出审计日志（CSV）

系统管理
GET    /api/v1/admin/system/health     # 系统健康状态
GET    /api/v1/admin/system/info       # 系统信息/版本
GET    /api/v1/admin/license/fingerprint # 获取本机部署指纹/离线激活请求码
POST   /api/v1/admin/license/activate  # 激活License
GET    /api/v1/admin/license/status    # License状态
GET    /api/v1/admin/license/modules   # 当前License授权模块和功能
POST   /api/v1/admin/license/deactivate # 注销当前部署激活（在线/人工场景）
```

### 6.5 SSE流式对话协议

```
POST /api/v1/chat/{agent_id}
Content-Type: application/json
Authorization: Bearer <token>

Request Body:
{
  "message": "用户输入的问题",
  "session_id": "uuid",          // 会话ID，新对话不传
  "stream": true
}

SSE Response（text/event-stream）:

data: {"type": "start", "conversation_id": "uuid", "session_id": "uuid"}

data: {"type": "chunk", "content": "根据"}

data: {"type": "chunk", "content": "您的产品手册"}

data: {"type": "sources", "sources": [
  {"doc_id": "uuid", "filename": "产品手册.pdf", "chunk": "...", "score": 0.92}
]}

data: {"type": "end", "usage": {"prompt_tokens": 150, "completion_tokens": 80}}

data: [DONE]
```

---

## 7. Agent框架规范

### 7.1 Agent基类与编排运行时

所有Agent必须继承 `BaseAgent`，并显式声明编排运行时。AgentHive 的默认技术栈是 **LangChain + LangGraph**：

- 复杂、多步骤、有状态、需要工具路由/人工介入/长链路审计的 Agent，默认使用 LangGraph。
- 简单的岗位助手、文案、报告、结构化生成类 Agent，可使用 LangChain Runnable / Chain。
- 图片/视频生成类 Agent 使用 Media Generation Gateway 承担模型适配、参考素材、异步任务和 MinIO 产物管理，必要时叠加 LangGraph 做素材拆解与多步骤编排。
- DeepAgents、CrewAI、AutoGen、LlamaIndex Workflow、Haystack、DSPy、Semantic Kernel 等先进技术栈可以按 Agent 业务特点选用，但必须封装在 Agent Adapter 内，不能绕过 AgentHive 的权限、模型网关、预算、审计和 License。

```python
class BaseAgent(ABC):
    definition: AgentDefinition
    
    async def invoke(self, message: str, session_id: str) -> AgentResponse:
        """同步调用"""
        ...
    
    async def stream(self, message: str, session_id: str) -> AsyncIterator[AgentChunk]:
        """流式调用，必须实现"""
        ...
```

`AgentDefinition` 必须包含：

```python
class AgentDefinition(BaseModel):
    agent_key: str
    required_module: str
    capabilities: list[str]
    orchestration_runtime: Literal[
        "langgraph",
        "langchain",
        "deepagents",
        "media_gateway",
        "native",
    ]
    orchestration_features: list[str]
```

编排运行时选择建议：

| 场景 | 推荐运行时 |
|------|------------|
| 客服、店铺运营、数据分析、多步骤RAG、需人工升级 | LangGraph |
| 文案、报告、HR摘要、财务解释、单轮结构化生成 | LangChain |
| 图片/视频生成、参考素材处理、异步媒体任务 | Media Gateway + LangGraph |
| 多Agent协作、复杂项目型任务、长期规划 | DeepAgents / LangGraph |
| 特定算法型工具、无需LLM编排的小工具 | Native Adapter |

### 7.2 LangGraph使用规范

```python
# ✅ 正确：显式定义状态Schema
class CustomerServiceState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    query: str
    retrieved_chunks: list[dict]
    final_answer: str
    sources: list[dict]
    requires_human: bool
    session_id: str
    tenant_id: str

# ✅ 正确：生产环境使用PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

checkpointer = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)

# ✅ 正确：thread_id包含租户隔离
config = {
    "configurable": {
        "thread_id": f"{tenant_id}:{agent_id}:{session_id}"
    }
}

# ❌ 错误：生产环境不得使用MemorySaver
# checkpointer = MemorySaver()  # 仅开发使用
```

### 7.3 官方Agent规范——客服助手

```python
# 客服Agent工作流
def build_customer_service_graph():
    workflow = StateGraph(CustomerServiceState)
    
    # 节点
    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("retrieve_knowledge", retrieve_knowledge_node)
    workflow.add_node("generate_answer", generate_answer_node)
    workflow.add_node("check_confidence", check_confidence_node)
    workflow.add_node("escalate_to_human", escalate_node)
    
    # 边
    workflow.set_entry_point("classify_intent")
    workflow.add_edge("classify_intent", "retrieve_knowledge")
    workflow.add_edge("retrieve_knowledge", "generate_answer")
    workflow.add_edge("generate_answer", "check_confidence")
    workflow.add_conditional_edges(
        "check_confidence",
        lambda state: "escalate" if state["requires_human"] else "end",
        {"escalate": "escalate_to_human", "end": END}
    )
    
    return workflow.compile(checkpointer=checkpointer)
```

### 7.4 DeepAgents使用场景

仅在以下场景使用DeepAgents，其他场景用LangGraph：
- 爆款内容拆解（需要规划+多步分析）
- 数据分析助手（需要长时间执行+代码执行）
- HR简历批量处理（需要子任务分解）

### 7.5 Agent选装与模块化

官方Agent、行业Agent包、第三方Agent模板必须通过 `agent_modules` 注册，租户通过 `tenant_agent_modules` 安装和启用。

Agent模块状态：

```text
not_installed  未安装，不可创建实例
installed      已安装但未启用，管理员可配置
enabled        已启用，可创建Agent实例并授权给用户/部门
disabled       已禁用，已有实例不可继续使用，但历史数据保留
expired        License过期或模块未授权，不可使用
```

选装规则：

- License中的 `allowed_modules` / `allowed_features` 决定租户可安装哪些Agent模块。
- 未授权模块可以在模块目录中展示为“未授权”，但不能安装和启用。
- Agent实例必须来自已启用模块，`custom` 类型除外；创建或更新实例时，只要保存后的状态是 `active`，后端必须重新校验当前 License、模块授权和租户模块启用状态，不能只依赖运行时拦截。
- 禁用模块后，不删除历史Agent、对话、审计和费用记录，只阻止新调用。
- 模块升级必须校验 `min_platform_version`，不允许安装不兼容版本。
- 官方模块必须提供 `display_name_i18n`、`description_i18n`、默认配置、所需能力和推荐模型能力，不得硬编码具体供应商。

### 7.6 低代码Agent Builder规范

用户通过JSON配置定义Agent，Builder引擎将配置转换为LangGraph：

```typescript
// Agent配置Schema（前端提交，后端验证）
interface AgentBuilderConfig {
  name: string
  description: string
  avatar_url?: string
  llm: {
    deployment_id: string  // 从平台已配置且当前用户/部门有权限的模型部署中选择
    model: string          // 逻辑模型名，仅用于展示和兼容旧配置
    temperature: number    // 0.0 - 1.0
    max_tokens: number
    max_cost_per_request?: number
    fallback_deployment_ids?: string[]
  }
  system_prompt: string    // 角色设定和规则
  knowledge_bases: string[]  // 知识库ID列表
  skills: string[]           // Skill ID列表
  response_style: 'formal' | 'friendly' | 'concise'
  language: 'zh' | 'en' | 'auto'
  escalation: {
    enabled: boolean
    confidence_threshold: number  // 低于此值转人工，0.0-1.0
    escalation_message: string
  }
  greeting_message: string   // 欢迎语
  fallback_message: string   // 无法回答时的默认回复
}
```

Agent配置校验要求：

- `deployment_id` 必须存在、启用，并通过当前租户/部门/用户/角色的 `llm_policies` 检查。
- `max_tokens`、`temperature`、`max_cost_per_request` 不能超过策略上限。
- 如果配置了 fallback 模型，fallback 也必须经过同样权限和预算检查。
- 官方Agent模板只能声明推荐模型能力（如需要长上下文/工具调用/视觉），不能硬编码特定供应商。

### 7.7 图片/视频生成Agent规范

图片生成 Agent 和视频生成 Agent 是电商客户的核心成交模块，必须作为官方可选装模块交付：

| Agent | 模块ID | 默认能力 | 推荐模型路由 |
|-------|--------|----------|--------------|
| 商品图片生成助手 | `agent.image_generation` | 文生图、参考图、批量变体、商品主图、品牌风格控制 | `image-generation` |
| 短视频生成助手 | `agent.video_generation` | 文生视频、图生视频、参考视频、素材拆解、时长/帧率/分辨率控制 | `video-generation` |

产品要求：

- 用户既可以手动编写提示词，也可以用自然语言下发目标，Agent 负责转译为可执行生成任务。
- 图片 Agent 必须支持参考图、比例、分辨率、生成张数、风格约束、负向提示词和品牌规范。
- 视频 Agent 必须支持参考图、参考视频、原始视频素材上传、素材拆解、目标时长、帧率、分辨率、镜头脚本和异步任务状态。
- 生成结果、参考素材、中间产物和导出文件必须统一进入 MinIO，不得长期保存在应用容器本地磁盘。
- 生成任务必须记录租户、部门、人员、Agent、模型、输入资产数量、输出资产数量、视频秒数、费用、状态和错误原因。
- License 必须能单独授权 `agent.image_generation`、`agent.video_generation` 和 `feature.media_generation`，方便单独售卖或作为高级包交付。

模型接入要求：

- 图片模型首批预留：`openai/gpt-image-2`（ChatGPT Images 2.0）、`google/nano-banana`、`openai-compatible-image`。
- 视频模型首批预留：`volcengine/seedance-2.0`（火山引擎 Seedance 2.0）、`openai-compatible-video`。
- 所有供应商参数必须通过模型部署配置表达，不得硬编码到 Agent 业务逻辑。
- 供应商 SDK、HTTP API、回调验签、异步任务轮询都必须封装在 Media Generation Gateway Adapter 内。
- Agent 只提交标准化 `MediaGenerationRequest`，由 Gateway 负责模型选择、参数映射、预算预占、调用执行、结果入库和审计。

---

## 8. RAG引擎规范

### 8.1 RAGFlow对接

RAGFlow通过HTTP API调用，不直接导入其Python模块：

```python
class RAGFlowAdapter(BaseRAGAdapter):
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0
        )
    
    async def retrieve(self, kb_id: str, query: str, top_k: int = 5) -> list[Chunk]:
        resp = await self.client.post("/api/v1/retrieval", json={
            "kb_id": kb_id,
            "question": query,
            "top_k": top_k,
            "similarity_threshold": 0.2,
            "vector_similarity_weight": 0.3,
        })
        resp.raise_for_status()
        return [Chunk(**chunk) for chunk in resp.json()["data"]["chunks"]]
```

### 8.2 多引擎路由

```python
# 按租户配置不同引擎（扩展点，MVP阶段只用RAGFlow）
class RAGRouter:
    async def get_adapter(self, tenant_id: str) -> BaseRAGAdapter:
        config = await self.get_tenant_rag_config(tenant_id)
        engine = config.get("engine", "ragflow")
        return self.adapters[engine]
```

### 8.3 知识库操作规范

- 文档上传：先存MinIO，再提交RAGFlow解析，异步处理
- 文档状态轮询：Celery任务定期查询RAGFlow处理状态
- 文档删除：先删RAGFlow，再删MinIO，最后更新数据库
- 知识库权限：在AgentHive层做权限控制，不依赖RAGFlow的权限

### 8.4 语义嵌入服务

通过 `EmbeddingService` Protocol 抽象，支持双适配器：

| 适配器 | 配置 | 适用场景 |
|---|---|---|
| `LocalHashEmbeddingService` | `RAG_EMBEDDING_PROVIDER=local_hash`（默认） | 开发/气隙环境兜底，确定性 hash 向量 |
| `LLMGatewayEmbeddingAdapter` | `RAG_EMBEDDING_PROVIDER=llm_gateway` + `RAG_EMBEDDING_API_BASE_URL`/`API_KEY` | 生产语义嵌入，OpenAI-compatible `/embeddings` |

**LLMGatewayEmbeddingAdapter 韧性策略**：

| 机制 | 配置 | 行为 |
|---|---|---|
| 超时 | `RAG_EMBEDDING_REQUEST_TIMEOUT_SECONDS=30` | 单次请求超时 |
| 重试 | `RAG_EMBEDDING_MAX_RETRIES=2` + `RETRY_BACKOFF_SECONDS=0.5` | 仅对 5xx/网络错误重试，指数退避；4xx 不重试（永久错误） |
| 熔断 | `CIRCUIT_BREAKER_FAILURE_THRESHOLD=5` + `RESET_TIMEOUT_SECONDS=60` | 连续失败 N 次后打开熔断；冷却窗口内短路返回 `CircuitBreakerOpenError` |
| 熔断降级 | — | development 环境熔断打开时回退到 LocalHash；production 抛错（fail-closed） |
| 半开探测 | — | 冷却窗口结束后放行一次探测请求；成功则关闭熔断，失败则重新打开 |

**关键设计**：嵌入服务无状态切换成本——所有适配器实现同一 Protocol，pgvector/RAGFlow 通过依赖注入接收 `EmbeddingService`，配置变更无需改 retrieval 代码。

---

## 9. Channel层规范

### 9.1 统一消息格式

```python
@dataclass
class UnifiedMessage:
    # 来源
    channel_id: str
    channel_type: ChannelType           # wecom/dingtalk/feishu/web_widget/webhook
    original_msg_id: str               # 原始消息ID（用于回复）
    
    # 租户/Agent路由
    tenant_id: str
    agent_id: str
    
    # 发送者
    external_user_id: str              # 渠道用户ID
    external_user_name: str
    internal_user_id: Optional[str]    # 关联的内部用户（如果有）
    
    # 内容
    content: str
    content_type: ContentType          # text/image/file/voice
    attachments: list[Attachment] = field(default_factory=list)
    
    # 会话
    session_id: str                    # 跨消息的会话连续性
    
    # 时间
    received_at: datetime
```

### 9.2 企业微信接入规范

```python
class WeCom Channel:
    # 消息接收：验证签名 → 解密 → 转UnifiedMessage → 路由Agent
    # 消息回复：Agent结果 → 调用企业微信发消息API
    # 支持：文本/图片/文件/语音
    # 不支持：直接回复（必须主动推送）
    
    async def verify_signature(self, msg_signature, timestamp, nonce, echostr): ...
    async def decrypt_message(self, xml_content: str) -> dict: ...
    async def send_text(self, to_user: str, content: str): ...
```

### 9.3 Channel安全规范

- 所有Channel的密钥/Token必须加密存储（AES-256）
- Webhook接收端点必须验证来源签名
- Channel配置在前端不返回完整密钥，只返回脱敏后的值
- 企业微信/钉钉的EncodingAESKey必须安全存储

### 9.4 Channel主动推送API

除被动 webhook 入站外，业务系统可主动向指定渠道用户推送消息，无需先收到入站消息。

**端点**：`POST /api/v1/channels/{channel_id}/push`
**权限**：`channels:write`
**Channel 状态**：必须为 `ACTIVE`

#### 9.4.1 两种推送模式

| 模式 | 字段值 | 行为 | 适用场景 |
|---|---|---|---|
| DIRECT（默认） | `mode: "direct"` | 直接把 `text` 原文交付给 vendor_api（或 outbound_webhook），不调用 Agent 运行时 | 系统通知、营销群发、预警广播等预渲染内容 |
| AGENT | `mode: "agent"` | 调用 Channel 配置的 Agent（或 `agent_key` 覆盖），以 `text` 作为输入，再把 Agent 的回答交付 | 需 LLM 推理的主动外呼，如"主动询问今日工单状态" |

#### 9.4.2 请求示例

```json
POST /api/v1/channels/{channel_id}/push
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "external_user_id": "user001",
  "text": "您的预约已确认，时间为明天 14:00。",
  "mode": "direct",
  "conversation_key": "appointment:flow:abc",
  "metadata": {"campaign_id": "summer-2026", "source_system": "crm"}
}
```

AGENT 模式示例：

```json
{
  "external_user_id": "staff001",
  "text": "总结今日订单",
  "mode": "agent",
  "agent_key": "ops_alert_agent",
  "model_key": "qwen-plus"
}
```

#### 9.4.3 响应结构

```json
{
  "channel_id": "...",
  "channel_type": "wecom",
  "channel_key": "wecom-corp-1",
  "mode": "direct",
  "delivered": true,
  "agent_invoked": false,
  "agent_key": null,
  "response_text": null,
  "conversation_key": "wecom:wecom-corp-1:user001",
  "outbound_delivery": {
    "attempted": true,
    "delivered": true,
    "mode": "vendor_api_wecom",
    "status_code": 200,
    "details": {"wecom_errcode": 0}
  },
  "request_id": "req-push-1",
  "error": null,
  "message": "Message delivered."
}
```

#### 9.4.4 关键设计

- **DIRECT 不调用 Agent**：`agent_invoked=false`，`response_text=null`，直接走 outbound 链路
- **AGENT 失败隔离**：Agent 运行时抛异常时记录 `error="processing_exception"`，**不**调用 vendor，避免脏数据触达用户；异常字符串经 `_safe_processing_error` 过滤后再进 audit，避免 `api_key` 等敏感字段泄漏
- **conversation_key 默认值**：`{channel_type}:{channel_key}:{external_user_id}`；调用方可通过 `conversation_key` 覆盖（例如绑定到既有会话）
- **vendor 未配置**：返回 `delivered=false`、`outbound_delivery.attempted=false`、`mode="vendor_api_not_configured"`；AGENT 模式下 Agent 仍可成功运行并返回 `response_text`，调用方可据此回退到其他渠道
- **Channel 禁用**：直接返回 `error="channel_disabled"`，不调用 Agent 也不调用 vendor
- **审计**：所有推送（无论成功失败）都记录 `action="channel.push"`，包含 `push_mode`、`agent_invoked`、`delivered`、`outbound_delivery` 全量诊断；调用方 `metadata` 的 key 列表（仅 key，不含 value）记录在 `caller_metadata_keys` 字段，便于追踪
- **凭证透传**：access_token / agent_id 等通过 Channel 配置注入，调用方无感知；WeCom `touser` 取 `wecom_to_user` 或回退到 `external_user_id`
- **跨渠道一致**：WeCom（`/cgi-bin/message/send`）、DingTalk（`robot_webhook` 或 `work_notice`）、Feishu（`/im/v1/messages`）三种 vendor_api 均支持主动推送

#### 9.4.5 与被动 webhook 的差异

| 维度 | webhook 入站 | 主动 push |
|---|---|---|
| 触发方 | 渠道用户发消息 | 业务系统主动调用 API |
| 签名校验 | 必须验证来源签名 | 不需要（用 JWT 鉴权） |
| 重放保护 | timestamp + nonce 时间窗口 | 不需要 |
| Agent 调用 | 默认调用（除非 `agent_id` 为空） | 仅 AGENT 模式调用 |
| DIRECT 文本 | 不支持 | 支持（绕过 Agent） |
| Audit action | `channel.webhook.received` / `processed` / `message.routed` | `channel.push` |

---

### 9.5 Channel Secret 轮换 API

支持双 secret 平滑过渡的 Webhook 签名密钥轮换机制，避免轮换期间丢失在途请求。

#### 9.5.1 端点

| 端点 | 方法 | 权限 | 说明 |
|---|---|---|---|
| `/api/v1/channels/{channel_id}/secret/rotate` | POST | `channels:write` | 把当前 secret 暂存为 `previous_secret`，新 secret 设为主 secret |
| `/api/v1/channels/{channel_id}/secret/promote` | POST | `channels:write` | 删除暂存的 `previous_secret`，完成轮换 |

#### 9.5.2 轮换流程（推荐 24 小时过渡窗口）

1. 调用 `POST /secret/rotate`，提交 `new_secret`
2. 平台主 secret 立即生效；旧 secret 仍接受 24h（过渡窗口）
3. 观察日志中 `rotation_previous_secret_used` 标志衰减到 0
4. 调用 `POST /secret/promote` 删除旧 secret，完成轮换

#### 9.5.3 请求/响应

**Rotate 请求**：
```json
{
  "new_secret": "新密钥字符串"
}
```

**Rotate 响应**：
```json
{
  "channel_id": "uuid",
  "rotated": true,
  "previous_secret_staged": true,
  "message": "Secret rotated. The previous secret remains valid during the transition window; call /secret/promote to finalize."
}
```

**Promote 响应**：
```json
{
  "channel_id": "uuid",
  "promoted": true,
  "message": "Previous secret dropped. Only the current secret is now accepted."
}
```

#### 9.5.4 关键设计

- **过渡窗口兜底**：webhook 验签时，若主 secret 失败且存在 `previous_secret`，自动回退校验。回退成功会在 `runtime_evidence` 中标记 `rotation_previous_secret_used: true`
- **审计**：`channel.secret.rotate` 和 `channel.secret.promote` 两个 audit action 记录 actor、时间、是否暂存/丢弃旧 secret
- **缓存一致性**：轮换立即更新内存缓存，无需重启服务
- **幂等**：`promote` 在无暂存 secret 时返回 noop 消息，不报错

### 9.6 Channel 消息轮询 API（Web Widget / REST API）

面向 **没有 vendor_api / outbound webhook** 的渠道（Web Widget、REST API），客户端通过轮询拉取 Agent 出站消息。

#### 9.6.1 端点

```
GET /api/v1/channels/poll/{channel_type}/{channel_key}
    ?external_user_id=<必填>
    &conversation_key=<可选>
    &after=<可选，上一页返回的 next_cursor>
    &limit=<可选，默认 50，上限 200>
```

#### 9.6.2 鉴权

使用 Channel 的 webhook secret 做 HMAC-SHA256 签名（与入站 webhook 同一 secret），通过请求头传递：

| Header | 说明 |
|---|---|
| `X-AgentHive-Signature` | `sha256=<hex>` 或 `<hex>` |
| `X-AgentHive-Timestamp` | 客户端时间戳（防重放） |
| `X-AgentHive-Nonce` | 一次性随机串（防重放） |

签名 base = `{timestamp}.{nonce}.{METHOD}.{path}?{sorted_query}`，其中 `sorted_query` 为查询参数按 key 排序后 `&` 连接。**轮换过渡窗口**内同时接受 `previous_secret`。Channel 未配置 secret 时允许匿名轮询（生产环境务必配置 secret）。

#### 9.6.3 响应

```json
{
  "channel_id": "uuid",
  "channel_type": "web_widget",
  "external_user_id": "visitor-1",
  "conversation_key": "web_widget:web_widget-corp-1:visitor-1",
  "messages": [
    {
      "message_id": "uuid",
      "conversation_id": "uuid",
      "conversation_key": "web_widget:web_widget-corp-1:visitor-1",
      "role": "assistant",
      "content": "您好，有什么可以帮您？",
      "created_at": "2026-06-25T10:00:00Z",
      "request_id": "req-xxx",
      "model_key": "qwen-plus"
    }
  ],
  "next_cursor": "uuid-or-null",
  "has_more": false
}
```

#### 9.6.4 关键设计

- **仅返回 assistant/agent 角色**：过滤掉用户自己的消息，避免回环
- **游标分页**：`after` 是上一页最后一条消息的 `message_id`（UUID 字典序）；`has_more=true` 时用 `next_cursor` 继续拉取
- **会话隔离**：按 `external_user_id`（+ 可选 `conversation_key`）匹配 `ConversationSession.metadata_json`，绝不跨用户泄露
- **DB + Python 双层过滤**：tenant / role / 排序在 DB；会话匹配 / 游标 / 分页在纯 Python helper（`_select_matching_sessions` / `_paginate_messages`），便于单元测试
- **无状态**：轮询端点无服务端游标存储，客户端自管理 `after` 游标，便于水平扩展

### 9.7 Web Widget 嵌入 SDK

面向 **Web Widget / REST API 渠道**，提供一份可嵌入任意客户网站的轻量 JS SDK，自动完成「发送消息 → 轮询 Agent 回复」闭环。

#### 9.7.1 接入方式

```html
<script>
  window.AgentHiveWidget = {
    baseUrl: "https://api.your-domain.com",
    channelKey: "your-web-widget-channel-key",
    channelSecret: "your-channel-secret",       // 可选，启用 HMAC 签名
    externalUserId: "visitor-123",               // 可选，缺省自动生成并 localStorage 持久化
    conversationKey: "session-abc",              // 可选
    primaryColor: "#2563eb",
    title: "Customer Support",
    pollIntervalMs: 3000,                        // 可选，最小 1500ms
    pollLimit: 50,                               // 可选，1-200
  };
</script>
<script src="https://api.your-domain.com/widget/agenthive-widget.js" async></script>
```

#### 9.7.2 端点

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/v1/channels/webhook/web_widget/{channel_key}` | POST | 发送用户消息（inbound） |
| `/api/v1/channels/poll/web_widget/{channel_key}` | GET | 轮询 Agent 回复（outbound） |
| `/widget/agenthive-widget.js` | GET | 静态 SDK 脚本（无需鉴权） |

#### 9.7.3 关键设计

- **零依赖**：纯 vanilla JS，无 React/Vue/jQuery，内嵌 SHA-256 + HMAC-SHA256 实现，gzip 后约 6KB
- **签名鉴权**：当 `channelSecret` 提供时，轮询请求自动附加 `X-AgentHive-Signature: sha256=<hmac>` / `X-AgentHive-Timestamp` / `X-AgentHive-Nonce`，与后端 `_verify_poll_signature` 一致
- **会话持久化**：`externalUserId` 缺省时自动生成并通过 `localStorage` 持久化，跨刷新保持会话
- **轮询节流**：打开面板后按 `pollIntervalMs`（默认 3s，最小 1.5s）轮询，关闭面板停止轮询；发送消息后 500ms 立即触发一次轮询
- **游标分页**：使用后端返回的 `next_cursor` 作为 `after` 参数，仅拉取新消息
- **CORS 隔离**：专用的 `widget_cors_middleware` 仅对 `/api/v1/channels/{poll,webhook}/web_widget/` 路径注入 `Access-Control-Allow-Origin`，其余 API 保持严格 CORS 策略
- **生产安全建议**：对于公开网站，推荐部署一个轻量签名代理（BFF）持有 `channelSecret`，避免在客户端暴露 secret；SDK 在无 secret 时降级为不签名（依赖后端 channel 未配置 secret 时的放行策略）

#### 9.7.4 配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `WIDGET_CORS_ENABLED` | `true` | 启用 Widget 专用 CORS 中间件 |
| `WIDGET_CORS_ORIGINS` | `["*"]` | Widget CORS 允许的 origin 列表，`*` 表示任意 |

---


## 10. 权限与安全规范

### 10.1 RBAC权限体系

```
权限层级
├── SuperAdmin（平台超级管理员）
│   └── 管理所有租户，不属于任何租户
│
└── 租户内权限
    ├── TenantAdmin（企业管理员）
    │   └── 管理本企业所有资源
    ├── OrgAdmin（部门管理员）
    │   └── 管理本部门资源
    ├── AgentManager（Agent管理员）
    │   └── 创建/编辑/发布Agent，管理知识库
    ├── KBManager（知识库管理员）
    │   └── 上传/管理知识库文档
    ├── ModelAdmin（模型管理员）
    │   └── 管理模型供应商、凭据、模型部署、价格表和策略
    ├── OpsEngineer（运维/实施人员）
    │   └── 查看组件健康、连接诊断、日志、支持包、升级/备份恢复提示
    ├── DepartmentLead（部门领导）
    │   └── 查看本部门及下级部门Agent使用、人员用量、预算消耗和效果报表
    ├── FinanceViewer（费用查看员）
    │   └── 查看部门/人员/Agent级Token和费用报表
    ├── User（普通用户）
    │   └── 使用已开放的Agent，查看自己的对话
    └── ReadOnly（只读用户）
        └── 查看，不能操作
```

### 10.2 权限码定义

```python
class Permission(str, Enum):
    # 用户管理
    USER_CREATE = "user:create"
    USER_READ   = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    
    # 知识库
    KB_CREATE   = "kb:create"
    KB_READ     = "kb:read"
    KB_UPDATE   = "kb:update"
    KB_DELETE   = "kb:delete"
    DOC_UPLOAD  = "doc:upload"
    DOC_DELETE  = "doc:delete"
    
    # Agent
    AGENT_CREATE  = "agent:create"
    AGENT_READ    = "agent:read"
    AGENT_UPDATE  = "agent:update"
    AGENT_DELETE  = "agent:delete"
    AGENT_PUBLISH = "agent:publish"
    AGENT_USE     = "agent:use"
    
    # Channel
    CHANNEL_CREATE = "channel:create"
    CHANNEL_MANAGE = "channel:manage"

    # LLM模型治理
    LLM_PROVIDER_MANAGE = "llm_provider:manage"
    LLM_CREDENTIAL_MANAGE = "llm_credential:manage"
    LLM_MODEL_READ = "llm_model:read"
    LLM_DEPLOYMENT_MANAGE = "llm_deployment:manage"
    LLM_POLICY_MANAGE = "llm_policy:manage"
    LLM_PRICE_MANAGE = "llm_price:manage"
    LLM_USE = "llm:use"

    # 预算与费用
    BUDGET_CREATE = "budget:create"
    BUDGET_READ   = "budget:read"
    BUDGET_UPDATE = "budget:update"
    BUDGET_DELETE = "budget:delete"
    COST_READ     = "cost:read"
    COST_EXPORT   = "cost:export"
    
    # 统计与审计
    ANALYTICS_READ = "analytics:read"
    AUDIT_READ     = "audit:read"
    AUDIT_EXPORT   = "audit:export"
    
    # 系统
    SYSTEM_CONFIG  = "system:config"
    LICENSE_MANAGE = "license:manage"
```

### 10.3 权限检查实现

```python
# 依赖注入式权限检查
def require_permission(*permissions: Permission):
    async def checker(user = Depends(get_current_user)):
        for perm in permissions:
            if not await check_user_permission(user, perm):
                raise HTTPException(403, f"缺少权限: {perm}")
        return user
    return checker

# 使用方式
@router.delete("/knowledge-bases/{kb_id}")
async def delete_kb(
    kb_id: str,
    user = Depends(require_permission(Permission.KB_DELETE))
):
    ...
```

### 10.4 RBAC + ABAC + 资源ACL

权限系统必须同时支持三层控制：

```text
RBAC        判断用户是否具备某类操作权限，如 agent:create、budget:update
ABAC        根据用户属性和上下文判断范围，如本部门/下级部门/本人/成本中心
ResourceACL 判断具体资源是否开放，如某个知识库、Agent、模型部署、Skill
```

典型规则：

- 普通用户只能使用授权给自己、所在角色或所在部门的Agent。
- 部门管理员只能管理本部门及下级部门用户、知识库、Agent、预算和报表。
- 部门领导默认只有部门级只读分析权限，除非额外授权，不得修改模型、License、全局预算和跨部门知识库。
- 运维/实施人员可以查看健康检查、连接测试和脱敏日志，但默认不能读取业务对话明文、API Key明文和知识库文件内容。
- 模型管理员可以配置供应商和部署，但不能默认查看所有对话内容。
- 模型管理员新增或修改模型部署时，必须同时配置数据范围、费用口径、预算策略和连接测试结果。
- 财务查看员可以看费用和Token报表，但不能读取对话明文和知识库文件。
- 财务、法务、HR等敏感知识库必须使用 `resource_permissions` 显式授权。
- 境外模型、联网搜索、文件上传、视觉模型、推理模型都必须可被策略禁止。

### 10.5 JWT规范

```python
# Access Token: 8小时过期
# Refresh Token: 7天过期，单次使用
# Token Payload:
{
    "sub": "user_id",
    "tenant_id": "tenant_id",
    "email": "user@example.com",
    "is_super_admin": false,
    "permissions": ["kb:read", "agent:use"],  # 缓存权限，减少DB查询
    "iat": 1234567890,
    "exp": 1234567890,
    "jti": "unique_token_id"                  # 用于吊销
}
```

### 10.6 安全要求

- 密码：bcrypt加密，cost factor 12
- API Key：加密存储，前端显示时脱敏
- SQL注入：全部使用参数化查询（SQLAlchemy ORM），禁止拼接SQL
- XSS：前端所有用户输入的内容渲染时转义
- CSRF：API使用Bearer Token，天然防CSRF
- 请求限流：登录接口 5次/分钟，普通接口 100次/分钟
- Prompt注入：用户输入注入LLM前进行过滤和沙箱隔离

---

## 11. 日志与审计规范

### 11.1 日志分类

```
应用日志      app.log        结构化JSON，INFO级别以上
错误日志      error.log      ERROR级别，包含完整堆栈
访问日志      access.log     所有HTTP请求
Agent日志     agent.log      Agent执行链路（LangSmith同步）
LLM日志       llm.log        模型路由、延迟、Token、费用、错误
审计日志      → 数据库        重要操作，不可篡改
```

### 11.2 结构化日志格式

```json
{
  "timestamp": "2026-01-01T00:00:00.000Z",
  "level": "INFO",
  "request_id": "uuid",
  "tenant_id": "uuid",
  "user_id": "uuid",
  "service": "agenthive-backend",
  "module": "agents.customer_service",
  "message": "Agent执行完成",
  "data": {
    "agent_id": "uuid",
    "session_id": "uuid",
    "latency_ms": 1250,
    "tokens": 230,
    "sources_count": 3
  }
}
```

### 11.3 必须记录审计的操作

```
用户类      LOGIN / LOGOUT / CREATE_USER / DELETE_USER / RESET_PASSWORD
权限类      GRANT_ROLE / REVOKE_ROLE / UPDATE_PERMISSIONS
知识库类    CREATE_KB / DELETE_KB / UPLOAD_DOC / DELETE_DOC
Agent类     CREATE_AGENT / PUBLISH_AGENT / DELETE_AGENT / UPDATE_AGENT
模块类      INSTALL_AGENT_MODULE / ENABLE_AGENT_MODULE / DISABLE_AGENT_MODULE / UPGRADE_AGENT_MODULE
模型类      CREATE_LLM_PROVIDER / UPDATE_LLM_CREDENTIAL / DELETE_LLM_CREDENTIAL / UPDATE_LLM_POLICY
预算类      CREATE_BUDGET / UPDATE_BUDGET / DELETE_BUDGET / EXPORT_COST_REPORT
系统类      UPDATE_SYSTEM_CONFIG / ACTIVATE_LICENSE / DEACTIVATE_LICENSE / LICENSE_MISMATCH / EXPORT_DATA
```

### 11.4 审计日志写入规范

```python
# 中间件自动记录，业务代码无需手动调用
# 但重要操作可以主动补充上下文
async def audit_log(
    action: str,
    resource_type: str,
    resource_id: str,
    old_value: dict = None,
    new_value: dict = None,
):
    # 从请求上下文获取user_id, tenant_id, ip等
    # 异步写入数据库，不阻塞业务流程
    await audit_queue.put(AuditEntry(...))
```

---

## 12. 企业级功能规范

### 12.1 多租户隔离

- 数据库层：所有查询必须带 `WHERE tenant_id = :tenant_id`
- 文件存储：MinIO按租户分桶 `bucket: tenant-{tenant_id}`
- RAGFlow：每个租户有独立的知识库命名空间
- Redis：所有Key加租户前缀 `{tenant_id}:{key}`
- LangGraph：thread_id包含tenant_id

**禁止跨租户数据访问**，违反此规则是严重安全漏洞。

### 12.2 模型费用与预算治理

AgentHive 必须将模型费用治理作为企业级核心能力，而不是事后统计报表。

预算范围：

```text
租户预算      控制整个企业总费用
部门预算      控制部门或下级部门费用
人员预算      控制个人使用费用和Token
Agent预算     控制单个Agent的费用上限
Channel预算   控制企业微信/网页Widget等渠道费用
成本中心预算  适配企业财务核算
```

预算周期：

- daily / weekly / monthly / quarterly / yearly
- 自定义 `period_start` / `period_end`
- 同一对象允许同时存在多个预算窗口，例如每日100元 + 每月3000元

控制动作：

```text
block       超预算后拒绝调用
downgrade   自动切换到更低成本fallback模型
alert_only  只告警不中断，用于试运行期
```

调用控制要求：

- 调用前：按输入Token估算 + `max_tokens` 预估最大费用，预算不足时拒绝或降级。
- 调用中：限制 `max_tokens`、RPM、TPM、并发、Agent最大迭代次数、单次最大费用。
- 调用后：用供应商返回 usage 或本地 tokenizer 计算实际费用，写入 `llm_usage` 和 `llm_budget_ledger`。
- 流式输出：必须在结束事件或异常事件里结算费用；用户中断时要记录已消耗Token。
- 价格变化：价格表必须带生效时间，历史费用不可因新价格而改变。
- 多币种：数据库以USD为统一核算币种，可在前端按汇率展示人民币等本地币种。

### 12.3 License机制

License 目标：

```text
防重复安装      同一License默认只能绑定一个deployment/install/machine fingerprint
防越权使用      未授权Agent模块、Channel、高级功能不可启用
防版本滥用      买断当前大版本，超过maintenance_until后升级需新授权
可离线激活      私有化客户不要求访问AgentHive云服务
可审计追踪      每个部署包带deployment_id/install_id水印
```

现实边界：

- 私有化交付无法绝对防止代码泄漏或镜像被复制，只能通过签名验证、环境绑定、镜像水印、License校验、合同约束和交付流程降低风险。
- 离线License无法实时发现所有重复安装；如需严格控制重复安装，必须启用在线激活或人工激活台账。
- 应用中只能内置License公钥，私钥绝不能进入代码仓库、Docker镜像、客户环境或CI日志。

授权内容：

```text
license_type         standard/pro/enterprise/custom
deployment_id        授权部署ID
install_id           首次安装生成并写入本地安全存储
machine_fingerprint  机器指纹Hash，绑定服务器/虚拟机环境
allowed_modules      可安装Agent模块
allowed_features     可启用功能，如 wecom/budget/ha/offline_model
maintenance_until    可免费升级/获取补丁截止时间
expires_at           授权过期时间，NULL代表永久使用当前大版本
max_activations      默认1，企业版可购买更多
```

```python
class LicenseValidator:
    """离线License验证，不需要联网"""
    
    # License内容（RSA签名，私钥由AgentHive持有）
    # {
    #   "tenant_name": "XX公司",
    #   "deployment_id": "uuid",
    #   "license_type": "standard",
    #   "allowed_modules": ["agent.customer_service", "agent.hr_screening"],
    #   "allowed_features": ["wecom", "web_widget", "budget", "analytics"],
    #   "machine_fingerprint_hash": "sha256:...",
    #   "max_activations": 1,
    #   "maintenance_until": "2027-01-01",
    #   "expires_at": null,
    #   "issued_at": "2026-01-01",
    #   "signature": "..."
    # }
    
    def validate(self, license_key: str) -> LicenseInfo:
        # 用内置公钥验证签名
        # 检查过期时间
        # 返回License信息
        ...
    
    def check_limit(self, resource: str, current: int, license: LicenseInfo):
        # 检查模块、功能、激活次数、维护期、过期时间、机器指纹
        ...
```

激活流程：

```text
1. install.sh 首次启动生成 install_id。
2. backend 读取机器环境生成 machine_fingerprint_hash。
3. 管理员在 /admin/license/fingerprint 页面导出离线激活请求码。
4. AgentHive销售/交付侧使用私钥签发License。
5. 客户导入License，系统验证签名、deployment_id、install_id、fingerprint、模块授权。
6. 激活成功后写入 licenses 与 license_activations。
7. 每次启动、每天定时、启用模块、调用高级功能时重新校验License。
```

机器指纹建议采集：

- CPU架构、主板/机器ID、系统UUID、Docker宿主机ID、网卡MAC Hash、磁盘卷ID Hash。
- 指纹必须容忍少量硬件变化，采用加权匹配，不得因网卡变化立刻导致系统不可用。
- 不保存原始硬件信息，只保存Hash和匹配结果。

防重复安装策略：

```text
离线标准版：License绑定 deployment_id + install_id + machine_fingerprint_hash，默认1次激活
离线企业版：允许多个fingerprint，但必须写入License授权数量
在线增强版：启动或定期向授权服务器上报 deployment_id/install_id/fingerprint，发现重复后吊销
人工管控版：交付侧维护license_activations台账，升级和支持前强制核验
```

部署包保护：

- 商业闭源版以Docker镜像/加密wheel交付，不交付完整源码。
- 镜像必须带版本号、build_id、deployment_watermark。
- 关键企业功能放在 enterprise 模块中，社区版/试用版镜像不包含完整实现。
- 安装脚本输出、系统信息页、审计日志必须显示 `deployment_id` 和脱敏License状态。
- 禁止在前端或日志中输出完整License、完整机器指纹、完整API Key。

### 12.4 数据备份规范

```bash
# 自动备份脚本（每日凌晨2点）
pg_dump agenthive > backup_$(date +%Y%m%d).sql
# MinIO数据镜像
# 保留最近30天
# 备份文件加密存储
```

### 12.5 健康检查接口

```python
GET /api/v1/admin/system/health

Response:
{
  "status": "healthy",              # healthy/degraded/unhealthy
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "components": {
    "database": {"status": "healthy", "latency_ms": 2},
    "redis": {"status": "healthy", "latency_ms": 1},
    "minio": {"status": "healthy"},
    "ragflow": {"status": "healthy", "latency_ms": 45},
    "llm": {"status": "healthy", "model": "gpt-4o-mini"}
  },
  "disk_usage_gb": 12.5,
  "memory_usage_mb": 1024
}
```

---

## 13. 前端规范

### 13.0 设计输入与审美规范

AgentHive 的前端不是普通后台模板，必须体现“可销售的企业级 AI 平台”质感。所有新增页面、复杂组件、交互流程和视觉重构必须同时参考两类设计输入：

1. **Google Stitch 设计稿**：项目根目录 `stitch_agenthive_enterprise_ui_design/` 是当前产品 UI 的基础方向，包含页面结构、信息密度、组件组合和视觉风格参考。实现页面时必须先查看对应 Stitch 设计稿或相近页面，不得脱离设计稿凭空搭建。
2. **Huashu Design（花叔 Design）**：在 Stitch 基础上进行产品级优化，用于提升视觉层级、信息架构、企业软件质感、交互反馈和细节完成度。若 Codex 本地已安装 `huashu-design` skill，涉及 UI 设计、页面重构、视觉评审、交互原型、高保真实现时必须先阅读并遵守该 skill 的相关原则。

执行要求：

- Stitch 是“基础参照”，Huashu Design 是“质量校准器”；不得只照搬 Stitch，也不得完全抛开 Stitch 另起炉灶。
- 优先做真实可用的产品界面，不做营销页式 Dashboard，不堆装饰性大卡片、渐变背景、空洞标语和无业务含义的图形。
- 企业管理台应强调清晰、克制、可扫描、可配置、可审计；按钮、表格、表单、筛选、状态、权限提示、空状态都要服务真实工作流。
- 每个页面至少明确一个主任务和一个次任务，避免“所有信息平铺但没有操作焦点”。
- 视觉层级必须靠信息结构、间距、字号、对齐、状态色和组件一致性建立，不靠花哨装饰。
- 所有关键状态必须设计完整：loading、empty、error、disabled、permission denied、license gated、saving、success。
- 页面文案必须符合 AgentHive 企业私有化产品定位，避免消费级、玩具化、过度营销化语气。
- 当 Stitch 与现有代码冲突时，优先保留既有组件体系和工程可维护性，再以最小必要样式/组件调整靠近设计稿。
- 当 Huashu Design 评审发现界面过于通用、AI slop、信息密度失衡、视觉焦点错误时，必须优先修复这些体验问题。
- 前端实现完成后，重要页面应通过浏览器或截图检查确认无明显文字溢出、重叠、错位、不可点击区域和移动端布局坍塌。

### 13.1 组件规范

- 所有页面组件放在 `src/app/` 下对应路由目录
- 可复用组件放在 `src/components/` 下按功能分类
- shadcn/ui 组件通过 CLI 生成到 `src/components/ui/`
- 禁止直接引入 Radix UI，统一通过 shadcn 封装
- 前端必须保持组件化和模块解耦，禁止把完整业务页面、复杂表单、数据请求、状态管理、展示组件长期堆在同一个文件中
- `App.tsx` 只负责应用启动、全局状态、Shell组合和路由分发，不得继续新增完整业务页面实现
- 业务页面应拆分到 `src/app/`、`src/pages/` 或 `src/features/<domain>/`，复杂页面继续拆成 `components/`、`hooks/`、`utils/`、`types/` 等小模块
- 单个页面/容器文件建议不超过 350 行，通用组件建议不超过 200 行，hooks/utils 建议不超过 180 行；任何文件达到 500 行前必须优先拆分
- 新增功能不得继续扩大已有超大文件；如果必须修改超大文件，应在同一任务中顺手抽离相关模块
- 所有组件必须有清晰职责边界：展示组件不直接调用API，数据请求统一通过 hooks/API 层，业务规则不得散落在 JSX 中

### 13.2 API请求规范

```typescript
// 统一使用TanStack Query
// 所有API请求封装在 src/lib/api/ 下

// 示例
export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: () => apiClient.get<Agent[]>('/agents'),
  })
}

export function useCreateAgent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateAgentInput) => 
      apiClient.post<Agent>('/agents', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
    }
  })
}
```

### 13.3 流式输出实现

```typescript
// SSE客户端（对话流式输出）
async function* streamChat(agentId: string, message: string, sessionId?: string) {
  const response = await fetch(`/api/v1/chat/${agentId}`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getToken()}`
    },
    body: JSON.stringify({ message, session_id: sessionId, stream: true })
  })
  
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    
    const chunk = decoder.decode(value)
    for (const line of chunk.split('\n')) {
      if (line.startsWith('data: ') && line !== 'data: [DONE]') {
        yield JSON.parse(line.slice(6)) as ChatChunk
      }
    }
  }
}
```

### 13.4 权限控制

统一 Web 端必须以权限和角色驱动信息架构：

- 菜单项、页面入口、操作按钮、表单字段、列表筛选、导出按钮都必须声明所需权限。
- 页面组件必须支持不同角色的降级视图，例如员工只能使用 Agent，部门领导可看部门报表，运维可看诊断，模型管理员可管理模型但不默认读取业务对话内容。
- 管理端页面必须优先复用同一套布局、导航、权限判断和 API 封装，不得为不同角色复制多套几乎相同的页面。
- 模型管理、部门用户、预算费用、审计日志、交付诊断、Agent模块市场、知识库和渠道配置都属于企业管理台核心模块，不能藏在临时设置页或不可发现入口中。
- 权限不足时必须提供清晰的禁用状态、空状态或申请联系管理员提示，而不是静默隐藏所有上下文。

```typescript
// 前端权限判断（配合后端权限，不替代后端）
function usePermission(permission: string): boolean {
  const { user } = useAuthStore()
  return user?.permissions?.includes(permission) ?? false
}

// 使用
const canDeleteKB = usePermission('kb:delete')
{canDeleteKB && <Button onClick={handleDelete}>删除</Button>}
```

### 13.5 国际化

- MVP阶段必须至少支持中文简体（zh-CN）和英文（en-US）。
- 默认语言：中文简体；用户可在个人设置中切换语言。
- 所有界面文案、菜单、按钮、表单校验、错误提示、空状态、通知、权限说明、报表字段名必须进入 i18n 资源文件，不得硬编码在组件内。
- i18n资源目录：
  - `src/lib/i18n/zh-CN.ts`
  - `src/lib/i18n/en-US.ts`
  - `src/lib/i18n/index.ts`
- API错误码保持英文常量，前端根据错误码映射本地化文案。
- 后端返回的系统内置角色名、权限说明、官方Agent模板名必须提供 `display_name_i18n` / `description_i18n` 字段。
- 日期、时间、数字、货币必须使用 locale-aware formatter。
- zh-CN 日期格式：`YYYY年MM月DD日`；en-US 日期格式：`MMM D, YYYY`。
- zh-CN 货币默认展示人民币符号和本地化格式；系统底层费用统一按USD核算，可按汇率展示本地币种。

---

## 14. 部署规范

### 14.1 Docker Compose配置

```yaml
# docker-compose.yml（生产）
version: '3.9'

services:
  nginx:
    image: nginx:1.26-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on: [frontend, backend]
    restart: always

  frontend:
    image: agenthive-frontend:${VERSION}
    restart: always

  backend:
    image: agenthive-backend:${VERSION}
    environment: &backend-env
      - DATABASE_URL=postgresql+asyncpg://agenthive:${DB_PASSWORD}@postgres:5432/agenthive
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - MINIO_ENDPOINT=minio:9000
      - RAGFLOW_URL=http://ragflow:9380
      - LITELLM_BASE_URL=http://litellm:4000
      - LITELLM_MASTER_KEY=${LITELLM_MASTER_KEY}
      - SECRET_KEY=${SECRET_KEY}
      - LANGSMITH_API_KEY=${LANGSMITH_API_KEY}
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_healthy}
      minio: {condition: service_healthy}
    restart: always

  celery_worker:
    image: agenthive-backend:${VERSION}
    command: celery -A app.core.celery worker -l info -c 4
    environment: *backend-env
    restart: always

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: agenthive
      POSTGRES_USER: agenthive
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "agenthive"]
      interval: 10s
      retries: 5
    restart: always

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
    restart: always

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_PASSWORD}
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
    restart: always

  ragflow:
    image: infiniflow/ragflow:latest
    environment:
      - MYSQL_PASSWORD=${RAGFLOW_DB_PASSWORD}
    volumes:
      - ragflow_data:/ragflow
    restart: always

  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    command: ["--config", "/app/config.yaml", "--port", "4000"]
    environment:
      - LITELLM_MASTER_KEY=${LITELLM_MASTER_KEY}
      - DATABASE_URL=postgresql://agenthive:${DB_PASSWORD}@postgres:5432/agenthive
    volumes:
      - ./litellm/config.yaml:/app/config.yaml:ro
    depends_on:
      postgres: {condition: service_healthy}
    restart: always

volumes:
  postgres_data:
  redis_data:
  minio_data:
  ragflow_data:
```

### 14.2 最低硬件要求

```
联网版（调用云端LLM）
  CPU:    8核
  内存:   16GB
  磁盘:   200GB SSD
  网络:   能访问LLM API即可

完全离网版（本地模型）
  CPU:    16核
  内存:   64GB
  GPU:    RTX 4090 / A100（运行Ollama）
  磁盘:   1TB SSD
```

### 14.3 一键安装脚本约定

```bash
# install.sh 必须完成：
# 1. 检查Docker和Docker Compose版本
# 2. 生成随机SECRET_KEY、数据库密码等
# 3. 创建 .env 文件
# 4. 拉取镜像
# 5. 启动服务
# 6. 等待健康检查通过
# 7. 执行数据库迁移
# 8. 创建默认超级管理员
# 9. 输出访问地址和初始密码
```

---

## 15. 开发规范

### 15.1 代码规范

```
Python:
  - 所有函数必须有类型注解
  - 异步函数使用 async/await
  - 禁止使用 * import
  - 复杂函数必须有文档字符串
  - 使用 ruff 格式化，mypy 严格类型检查

TypeScript:
  - 禁止使用 any 类型
  - 组件Props必须定义接口
  - 使用 Biome 格式化
```

### 15.2 命名规范

```
数据库表名:       snake_case 复数（users, knowledge_bases）
Python类名:       PascalCase
Python函数/变量:  snake_case
API路由:          kebab-case（/knowledge-bases）
React组件:        PascalCase
TypeScript接口:   PascalCase（前缀 I 可选）
环境变量:         UPPER_SNAKE_CASE
```

### 15.3 Git规范

```
分支策略:
  main          生产分支，只接受PR合并
  develop       开发分支
  feature/*     功能分支
  fix/*         修复分支

Commit格式（Conventional Commits）:
  feat: 新功能
  fix: Bug修复
  docs: 文档更新
  refactor: 重构
  test: 测试
  chore: 构建/工具
```

### 15.4 禁止事项

```
❌ 禁止在代码中硬编码任何密钥/密码/API Key
❌ 禁止跨租户数据访问
❌ 禁止在生产环境使用MemorySaver（LangGraph）
❌ 禁止直接拼接SQL字符串
❌ 禁止在前端存储敏感信息（LocalStorage）
❌ 禁止使用同步阻塞调用（FastAPI全程async）
❌ 禁止删除或修改审计日志表数据
❌ 禁止在日志中记录用户密码、完整API Key
```

---

## 16. 测试规范

### 16.1 测试分层

```
单元测试    测试单个函数/类，Mock所有外部依赖
集成测试    测试API端点，使用测试数据库
E2E测试     关键用户流程（可选，MVP后）
```

### 16.2 必须测试的关键路径

```
① 用户登录/Token验证
② 知识库文档上传→解析→检索完整流程
③ 对话流式输出（SSE）
④ RBAC权限控制（有权限/无权限两种case）
⑤ 多租户数据隔离（A租户不能访问B租户数据）
⑥ Channel消息接收→Agent路由→回复
⑦ License验证（有效/过期/超限）
⑧ 审计日志记录
⑨ LLM策略控制（用户/部门有权限与无权限两种case）
⑩ 预算控制（调用前拦截、调用后结算、超额降级/阻断）
⑪ Agent模块选装（未授权/已安装/启用/禁用/过期）
⑫ License验证（签名错误/机器不匹配/重复安装/模块未授权）
```

---

## 17. MVP范围与优先级

### 17.1 P0（第一版发布必须有）

```
功能
├── 用户管理（创建/禁用/重置密码）
├── 组织/部门管理
├── RBAC权限控制（5个内置角色）
├── 中英文国际化（zh-CN / en-US）
├── LLM模型管理（供应商/凭据/模型部署/连通性测试）
├── LiteLLM或OpenAI-compatible模型接入
├── 基础模型策略（按租户/部门/人员/Agent允许或禁止模型）
├── 基础预算控制（租户/部门/人员月度费用和Token上限）
├── Agent模块选装（官方Agent按License授权安装/启用）
├── 知识库管理（上传/解析/检索测试）
├── 电商客服Agent（官方内置，可配置）
├── HR简历筛选Agent（官方内置，可配置）
├── 文案创作Agent（官方内置，可配置）
├── 对话界面（SSE流式，来源展示）
├── 企业微信Channel接入
├── 网页Widget（可嵌入客户官网）
├── 数据看板（基础统计）
├── 模型费用看板（按部门/人员/Agent/模型）
├── 审计日志（操作记录）
├── License验证机制（离线激活/机器指纹/模块授权/重复安装防护）
└── Docker Compose一键部署
```

### 17.2 P1（发布后1-2个月）

```
├── 钉钉/飞书Channel接入
├── 低代码Agent Builder
├── 爆款内容拆解Agent
├── 项目汇报Agent
├── MCP工具接入
├── 对话历史管理和导出
├── Ollama离网模型支持
├── 多模型Fallback和成本优先路由
└── 多预算窗口（日/月/季度组合）
```

### 17.3 P2（3-6个月）

```
├── 财务效率Agent
├── 数据分析Agent
├── Agent Marketplace（第三方Agent接入）
├── Skill市场（ClawHub技能迁移）
├── 高级数据看板
├── 模型质量评测与自动路由优化
├── 成本异常检测和预算预测
└── 批量导入/导出
```

### 17.4 开发时序

```
Week 1-2    数据库Schema + 基础CRUD API + JWT认证 + i18n骨架
Week 3-4    组织/部门/RBAC/资源ACL + 审计日志
Week 5-6    LLM Gateway + LiteLLM/OpenAI-compatible接入 + 模型部署测试
Week 7-8    预算/费用账本 + 部门/人员模型策略 + 成本看板
Week 9-10   知识库管理 + RAGFlow对接 + 文件上传
Week 11-12  LangGraph客服Agent + SSE流式对话
Week 13-14  企业微信Channel + 网页Widget + 前端管理控制台
Week 15-16  HR Agent + 文案Agent + Docker打包 + 安装脚本 + 内测
```

---

## 附录：关键设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 产品命名 | AgentHive | 更明确表达企业Agent平台，所有对外命名统一 |
| 部署模式 | 单体 | 私有化中小企业，降低运维复杂度 |
| 业务数据库 | PostgreSQL | 多租户核心业务、审计、费用账本必须可靠一致 |
| 嵌入式数据库 | SQLite仅用于本地/边缘/插件状态 | 避免把核心业务数据分散到不可治理的本地文件 |
| 向量库 | PostgreSQL + pgvector | 统一关系型和向量存储，减少组件 |
| RAG引擎 | RAGFlow via API | 文档解析质量最优，协议隔离便于替换 |
| LLM网关 | AgentHive Gateway + LiteLLM | AgentHive负责业务治理，LiteLLM负责多模型协议适配 |
| 模型接入 | LiteLLM + OpenAI-compatible + Native Adapter | 覆盖全球主流模型、国产模型和私有本地模型 |
| 费用治理 | 租户/部门/人员/Agent/Channel/成本中心预算 | 企业采购最关心可控成本和责任归属 |
| Agent交付 | 模块化选装 | 客户按需求购买/启用Agent，便于买断交付和后续增购 |
| Agent框架 | LangGraph为主 | 生产级持久化，行为可预期，可审计 |
| 认证方式 | JWT | 无状态，适合私有化部署 |
| 文件存储 | MinIO | 私有化S3兼容，不依赖云服务 |
| 国际化 | zh-CN + en-US 起步 | 满足中文客户和国际化扩展 |
| 注册方式 | 关闭公开注册，管理员创建 | 企业内部系统安全要求 |
| License | 离线RSA验证 + deployment/install/fingerprint绑定 | 客户可断网部署，同时降低重复安装和越权使用风险 |

---

> **最后更新**: 2026-06-08
> **版本**: v1.0.0
> **维护者**: MetaPure Lab / yjing
> **项目**: AgentHive Enterprise AI Platform
