# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个生产级的 AI 智能体（Agent）应用，使用 FastAPI + LangGraph + LangChain 构建。使用 PostgreSQL/pgvector 进行数据持久化，Langfuse 用于 LLM（大语言模型）可观测性，mem0ai 用于语义记忆，以及基于 JWT 的身份认证和会话管理。

## 常用命令

```bash
# 安装依赖（使用 uv 包管理器）
uv sync

# 开发服务器（热重载，端口 8000）
make dev

# 生产环境 / 预发布环境
make prod
make staging

# 代码检查与格式化
ruff check .
ruff format .

# LLM 评估
make eval          # 交互式
make eval-quick    # 非交互式
make eval-no-report

# Docker 相关
make docker-build-env ENV=development
make docker-run-env ENV=development
make docker-compose-up ENV=development  # 包含 Prometheus/Grafana 监控

# 测试（pytest 已配置，但尚未编写测试用例）
uv run pytest
uv run pytest tests/test_file.py::test_name  # 运行单个测试
```

## 架构

**请求流程：** FastAPI → LoggingContextMiddleware（日志上下文中间件） → MetricsMiddleware（指标中间件） → Route handler（路由处理器） → LangGraphAgent（LangGraph 智能体） → LLM（大语言模型，通过 Langfuse 追踪） → StreamingResponse（流式响应）

**核心模块：**
- `app/main.py` — 应用初始化、生命周期管理、中间件注册
- `app/api/v1/` — 路由：`auth.py`（JWT 认证、注册、会话管理），`chatbot.py`（同步 + 流式聊天）
- `app/agent/graph.py` — `LangGraphAgent`：编排 StateGraph（状态图），包含 "chat"（聊天）和 "tool_call"（工具调用）节点，使用 AsyncPostgresSaver 做检查点持久化，mem0ai 做长期记忆
- `app/agent/tools/` — 工具注册中心（目前包含 DuckDuckGo 搜索）
- `app/agent/prompts/` — 提示词加载
- `app/services/llm.py` — `LLMService`：LLM 注册中心，支持多个 ChatOpenAI 模型，自动重试/降级
- `app/services/database.py` — `DatabaseService`：基于 SQLModel/asyncpg 的异步数据库操作
- `app/core/config.py` — `Settings` 配置类，支持不同环境的配置文件（`.env.{development,staging,production}`）
- `app/schemas/` — Pydantic 数据模型，用于 API 请求/响应和图状态定义
- `evals/` — LLM 输出评估框架，评估指标定义在 `evals/metrics/prompts/` 中

## 关键规则（来自 AGENTS.md 的"十条戒律"）

1. **所有 import 必须放在文件顶部** — 不要在函数或类内部导入
2. **所有日志使用 structlog** — 事件名称必须是 `小写加下划线` 格式，事件中不要使用 f-string，变量通过 kwargs 传递
3. **使用 `logger.exception()` 而不是 `logger.error()`** — 以保留完整的错误堆栈信息
4. **所有重试逻辑使用 tenacity** — 指数退避策略：`@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))`
5. **所有路由必须添加限流装饰器** — 通过 slowapi 实现
6. **所有 LLM 操作必须启用 Langfuse 追踪**
7. **所有数据库操作必须是异步的**
8. **只缓存成功的响应** — 永远不要缓存错误
9. **使用 rich 库进行控制台输出** — 包括进度条、表格、面板等
10. **所有接口必须使用 Pydantic 模型** 和类型注解（遵循 RORO 模式，即"接收对象，返回对象"）

## 代码风格

- I/O 操作使用 `async def`，纯函数使用 `def`
- 采用函数式/声明式风格；除了 service（服务层）和 agent（智能体）外，尽量避免使用类
- 使用 guard clause（守卫语句）和 early return（提前返回）处理错误；正常逻辑放在最后
- 对预期内的错误使用 `HTTPException`
- 使用 FastAPI 的 `Depends()` 进行依赖注入（认证、数据库、服务等）
- 使用 lifespan 上下文管理器，不要用 `@app.on_event`

## 环境配置

1. 将 `.env.example` 复制为 `.env.development` 并填入 API 密钥
2. 必需的配置项：`OPENAI_API_KEY`、`JWT_SECRET_KEY`、PostgreSQL 数据库凭据、Langfuse 密钥
3. `APP_ENV` 控制运行环境（`development` 开发、`staging` 预发布、`production` 生产、`test` 测试）
4. 配置文件按以下优先级加载：`.env.{ENV}.local` → `.env.{ENV}` → `.env.local` → `.env`

## 参考资料：Claude Code 源码分析

`docs/claude-code-source-analysis/` 目录下包含对 Claude Code CLI 工具源码的架构分析，可作为本项目 Agent 系统设计的参考：

- `ref_claude_code_architecture.md` — 总体架构、目录结构、核心请求流程
- `ref_claude_code_tool_system.md` — 工具系统：接口设计、注册表模式、并发执行
- `ref_claude_code_permissions.md` — 五层权限与安全模型
- `ref_claude_code_agent_system.md` — Agent/子Agent 生命周期与上下文隔离
- `ref_claude_code_hooks_skills.md` — Hooks 事件机制、Skills 扩展、插件架构
- `ref_claude_code_design_patterns.md` — 10 个核心设计模式（类型驱动、DI、流式生成器等）
