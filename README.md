# FastAPI LangGraph Agent 模板

一个生产级的 FastAPI 模板，用于构建集成了 LangGraph 的 AI 智能体（Agent）应用。该模板为构建可扩展、安全且易于维护的 AI 智能体服务提供了坚实的基础。

## 🌟 功能特性

- **生产级架构**

  - 基于 FastAPI 的高性能异步 API 接口，搭配 uvloop 优化
  - 集成 LangGraph，支持 AI 智能体工作流和状态持久化
  - 集成 Langfuse，用于 LLM（大语言模型）的可观测性和监控
  - 结构化日志，支持按环境切换格式，并附带请求上下文
  - 速率限制（Rate Limiting），可为每个接口配置不同规则
  - PostgreSQL + pgvector，用于数据持久化和向量存储
  - 支持 Docker 和 Docker Compose 部署
  - Prometheus 指标采集和 Grafana 仪表盘监控

- **AI 与 LLM 功能**

  - 基于 mem0ai 和 pgvector 的长期记忆功能，支持语义化记忆存储
  - LLM 服务内置自动重试逻辑，使用 tenacity 库实现
  - 支持多种 LLM 模型（GPT-4o、GPT-4o-mini、GPT-5、GPT-5-mini、GPT-5-nano）
  - 流式响应（Streaming），支持实时聊天交互
  - 工具调用（Tool Calling）和函数执行能力

- **安全性**

  - 基于 JWT 的身份认证
  - 会话管理（Session Management）
  - 输入内容清洗（Input Sanitization）
  - CORS 跨域配置
  - 速率限制保护

- **开发体验**

  - 按环境自动加载配置，支持 .env 文件
  - 完善的日志系统，支持上下文绑定
  - 清晰的项目结构，遵循最佳实践
  - 全面的类型注解（Type Hints），提升 IDE 支持
  - 通过 Makefile 命令轻松搭建本地开发环境
  - 自动重试逻辑，采用指数退避（Exponential Backoff）策略，增强容错性

- **模型评估框架**
  - 基于指标的模型输出自动化评估
  - 与 Langfuse 集成，进行追踪分析
  - 详细的 JSON 报告，包含成功/失败指标
  - 交互式命令行界面
  - 可自定义评估指标

## 🚀 快速开始

### 前置要求

- Python 3.13+
- PostgreSQL（[参见数据库设置](#数据库设置)）
- Docker 和 Docker Compose（可选）

### 环境配置

1. 克隆仓库：

```bash
git clone <repository-url>
cd <project-directory>
```

2. 创建并激活虚拟环境：

```bash
uv sync
```

3. 复制示例环境配置文件：

```bash
cp .env.example .env.[development|staging|production] # 例如 .env.development
```

4. 根据你的实际配置修改 `.env` 文件（可参考 `.env.example`）

### 数据库设置

1. 创建一个 PostgreSQL 数据库（例如使用 Supabase 或本地 PostgreSQL）
2. 在 `.env` 文件中更新数据库连接配置：

```bash
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=cool_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

- 你不需要手动创建数据表，ORM 会自动处理。但如果遇到问题，可以手动执行 `schemas.sql` 文件来创建数据表。

### 运行应用

#### 本地开发

1. 安装依赖：

```bash
uv sync
```

2. 运行应用：

```bash
make [dev|staging|prod] # 例如 make dev
```

1. 打开 Swagger UI：

```bash
http://localhost:8000/docs
```

#### 使用 Docker

1. 通过 Docker Compose 构建并运行：

```bash
make docker-build-env ENV=[development|staging|production] # 例如 make docker-build-env ENV=development
make docker-run-env ENV=[development|staging|production] # 例如 make docker-run-env ENV=development
```

2. 访问监控工具：

```bash
# Prometheus 指标
http://localhost:9090

# Grafana 仪表盘
http://localhost:3000
默认登录凭据：
- 用户名: admin
- 密码: admin
```

Docker 部署包含以下组件：

- FastAPI 应用
- PostgreSQL 数据库
- Prometheus 指标采集
- Grafana 指标可视化
- 预配置的仪表盘，包括：
  - API 性能指标
  - 速率限制统计
  - 数据库性能
  - 系统资源使用情况

## 📊 模型评估

项目内置了一个强大的评估框架，用于衡量和追踪模型性能的变化趋势。评估器会自动从 Langfuse 获取追踪数据，应用评估指标，并生成详细的报告。

### 运行评估

你可以使用 Makefile 提供的命令，以不同方式运行评估：

```bash
# 交互模式，逐步引导你完成设置
make eval [ENV=development|staging|production]

# 快速模式，使用默认设置（无交互提示）
make eval-quick [ENV=development|staging|production]

# 仅评估，不生成报告
make eval-no-report [ENV=development|staging|production]
```

### 评估功能

- **交互式命令行**：用户友好的界面，带有彩色输出和进度条
- **灵活配置**：可设置默认值，也可在运行时自定义
- **详细报告**：JSON 格式的报告，包含全面的指标信息：
  - 整体成功率
  - 各指标的表现情况
  - 耗时和时间信息
  - 追踪级别的成功/失败详情

### 自定义指标

评估指标以 Markdown 文件的形式定义在 `evals/metrics/prompts/` 目录中：

1. 在该目录下创建一个新的 Markdown 文件（例如 `my_metric.md`）
2. 定义评估标准和评分逻辑
3. 评估器会自动发现并应用你的新指标

### 查看报告

报告会自动生成在 `evals/reports/` 目录下，文件名中包含时间戳：

```
evals/reports/evaluation_report_YYYYMMDD_HHMMSS.json
```

每份报告包含：

- 高层统计信息（追踪总数、成功率等）
- 各指标的性能数据
- 追踪级别的详细信息，方便调试

## 🔧 配置说明

应用使用灵活的配置系统，支持按环境区分设置：

- `.env.development` - 本地开发环境设置
- `.env.staging` - 预发布环境设置
- `.env.production` - 生产环境设置

### 环境变量

主要的配置变量包括：

```bash
# 应用配置
APP_ENV=development
PROJECT_NAME="FastAPI LangGraph Agent"
DEBUG=true

# 数据库配置
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=mydb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# LLM 配置
OPENAI_API_KEY=your_openai_api_key
DEFAULT_LLM_MODEL=gpt-4o
DEFAULT_LLM_TEMPERATURE=0.7
MAX_TOKENS=4096

# 长期记忆配置
LONG_TERM_MEMORY_COLLECTION_NAME=agent_memories
LONG_TERM_MEMORY_MODEL=gpt-4o-mini
LONG_TERM_MEMORY_EMBEDDER_MODEL=text-embedding-3-small

# 可观测性配置
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com

# 安全配置
SECRET_KEY=your_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 速率限制配置
RATE_LIMIT_ENABLED=true
```

## 🧠 长期记忆

应用内置了基于 mem0ai 和 pgvector 的智能长期记忆系统：

### 功能特性

- **语义化记忆存储**：基于语义相似度来存储和检索记忆
- **用户隔离的记忆空间**：每个用户拥有独立的记忆空间
- **自动记忆管理**：自动提取、存储和检索记忆
- **向量搜索**：使用 pgvector 进行高效的相似度搜索
- **可配置模型**：记忆处理和向量嵌入（Embedding）使用不同的模型

### 工作原理

1. **记忆写入**：对话过程中，重要信息会被自动提取并存储
2. **记忆检索**：根据对话上下文，自动检索相关的记忆
3. **记忆搜索**：语义搜索可以跨对话查找相关记忆
4. **记忆更新**：当获取到新信息时，已有记忆会被自动更新

## 🤖 LLM 服务

LLM 服务提供了稳健的、生产级的大语言模型交互能力，内置自动重试逻辑，支持多种模型。

### 功能特性

- **多模型支持**：预配置支持 GPT-4o、GPT-4o-mini、GPT-5 及其变体
- **自动重试**：使用 tenacity 实现指数退避重试逻辑
- **推理配置**：GPT-5 系列模型支持可配置的推理能力等级
- **按环境调优**：开发环境和生产环境使用不同的参数
- **降级机制**：主模型失败时可优雅降级

### 支持的模型

| 模型        | 适用场景         | 推理能力等级 |
| ----------- | ---------------- | ------------ |
| gpt-5       | 复杂推理任务     | 中等         |
| gpt-5-mini  | 性能与成本均衡   | 低           |
| gpt-5-nano  | 快速响应         | 最低         |
| gpt-4o      | 生产环境负载     | 不适用       |
| gpt-4o-mini | 低成本任务       | 不适用       |

### 重试配置

- 遇到 API 超时、速率限制和临时错误时自动重试
- **最大重试次数**：3 次
- **等待策略**：指数退避（1秒、2秒、4秒）
- **日志记录**：所有重试操作都会附带上下文写入日志

## 📝 高级日志

应用使用 structlog 进行结构化、上下文化的日志记录，并自动追踪请求。

### 功能特性

- **结构化日志**：所有日志都具有统一的字段结构
- **请求上下文**：自动绑定 request_id、session_id 和 user_id
- **按环境切换格式**：生产环境使用 JSON 格式，开发环境使用彩色控制台输出
- **性能追踪**：自动记录请求耗时和状态
- **异常追踪**：完整的堆栈追踪，并保留上下文信息

### 日志上下文中间件

每个请求会自动附带以下信息：
- 唯一的请求 ID（Request ID）
- 会话 ID（Session ID，已认证时）
- 用户 ID（User ID，已认证时）
- 请求路径和方法
- 响应状态码和耗时

### 日志格式规范

- **事件名称**：使用小写加下划线（lowercase_with_underscores）
- **禁止使用 f-string**：将变量作为 kwargs 传入，以便正确过滤
- **上下文绑定**：始终包含相关的 ID 和上下文
- **合理的日志级别**：debug、info、warning、error、exception

## ⚡ 性能优化

### uvloop 集成

应用使用 uvloop 增强异步性能（通过 Makefile 自动启用）：

**性能提升效果**：
- 异步操作速度提升 2-4 倍
- I/O 密集型任务延迟更低
- 连接池管理更高效
- 并发请求的 CPU 使用率更低

### 连接池

- **数据库**：异步连接池，池大小可配置
- **LangGraph 检查点（Checkpointing）**：使用共享连接池进行状态持久化
- **Redis**（可选）：用于缓存的连接池

### 缓存策略

- 仅缓存成功的响应
- 可根据数据变化频率配置 TTL（过期时间）
- 数据更新时自动失效缓存
- 支持 Redis 或内存缓存

## 🔌 API 接口参考

### 认证接口

- `POST /api/v1/auth/register` - 注册新用户
- `POST /api/v1/auth/login` - 登录认证，获取 JWT 令牌
- `POST /api/v1/auth/logout` - 登出并使会话失效

### 聊天接口

- `POST /api/v1/chatbot/chat` - 发送消息并获取回复
- `POST /api/v1/chatbot/chat/stream` - 发送消息，以流式方式获取回复
- `GET /api/v1/chatbot/history` - 获取对话历史
- `DELETE /api/v1/chatbot/history` - 清除聊天历史

### 健康检查与监控

- `GET /health` - 健康检查（包含数据库状态）
- `GET /metrics` - Prometheus 指标接口

如需查看详细的 API 文档，请在应用运行后访问 `/docs`（Swagger UI）或 `/redoc`（ReDoc）。

## 📚 项目结构

```
whatsapp-food-order/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py              # 认证接口
│   │       ├── chatbot.py           # 聊天接口
│   │       └── api.py               # API 路由聚合
│   ├── core/                        # 核心业务逻辑
│   │   ├── graph.py                 # LangGraph 智能体
│   │   ├── tools/                   # 智能体工具
│   │   └── prompts/
│   │       ├── __init__.py          # 提示词加载器
│   │       └── system.md            # 系统提示词
│   ├── infrastructure/              # 基础设施
│   │   ├── config.py                # 配置管理
│   │   ├── logging.py               # 日志配置
│   │   ├── metrics.py               # Prometheus 指标
│   │   ├── middleware.py            # 自定义中间件
│   │   └── limiter.py               # 速率限制
│   ├── models/
│   │   ├── user.py                  # 用户模型
│   │   └── session.py               # 会话模型
│   ├── schemas/
│   │   ├── auth.py                  # 认证数据模式
│   │   ├── chat.py                  # 聊天数据模式
│   │   └── graph.py                 # 图状态数据模式
│   ├── services/
│   │   ├── database.py              # 数据库服务
│   │   └── llm.py                   # LLM 服务（含重试逻辑）
│   ├── utils/
│   │   ├── __init__.py
│   │   └── graph.py                 # 图相关工具函数
│   └── main.py                      # 应用入口
├── evals/
│   ├── evaluator.py                 # 评估逻辑
│   ├── main.py                      # 评估命令行入口
│   ├── metrics/
│   │   └── prompts/                 # 评估指标定义
│   └── reports/                     # 生成的评估报告
├── grafana/                         # Grafana 仪表盘配置
├── prometheus/                      # Prometheus 配置
├── scripts/                         # 工具脚本
├── docker-compose.yml               # Docker Compose 配置
├── Dockerfile                       # 应用 Docker 镜像
├── Makefile                         # 开发命令
├── pyproject.toml                   # Python 依赖配置
├── schema.sql                       # 数据库表结构
├── SECURITY.md                      # 安全策略
└── README.md                        # 本文件
```

## 🛡️ 安全说明

如有安全方面的问题，请查阅我们的[安全策略](SECURITY.md)。

## 📄 许可证

本项目基于 [LICENSE](LICENSE) 文件中指定的条款进行许可。

## 🤝 参与贡献

欢迎贡献代码！请确保：

1. 代码遵循项目的编码规范
2. 所有测试通过
3. 新功能包含相应的测试
4. 文档已同步更新
5. 提交信息遵循 Conventional Commits（约定式提交）规范

## 📞 支持与帮助

如有问题、疑问或想参与贡献，请在项目仓库中提交 Issue。
