# AI Agent（智能代理）开发指南

本文档为参与本 LangGraph FastAPI Agent 项目的 AI 代理提供核心开发规范。

## 项目概述

这是一个生产级别的 AI 代理应用，基于以下技术栈构建：
- **LangGraph** — 用于构建有状态的、多步骤 AI 代理工作流
- **FastAPI** — 高性能异步 REST API 框架
- **Langfuse** — LLM（大语言模型）的可观测性与链路追踪
- **PostgreSQL + pgvector** — 长期记忆存储（基于 mem0ai）
- **JWT 认证** — 带会话管理的身份验证
- **Prometheus + Grafana** — 系统监控

## 快速参考：核心规则

### 导入规则
- **所有 import 必须放在文件顶部** — 禁止在函数或类内部添加 import 语句

### 日志规则
- 使用 **structlog** 进行所有日志记录
- 日志消息必须使用 **小写加下划线** 的格式（例如：`"user_login_successful"`）
- **structlog 事件中禁止使用 f-string** — 变量应通过 kwargs 传递
- 使用 `logger.exception()` 代替 `logger.error()` 以保留完整的错误堆栈信息
- 示例：`logger.info("chat_request_received", session_id=session.id, message_count=len(messages))`

### 重试规则
- **必须使用 tenacity 库** 实现重试逻辑
- 配置指数退避策略
- 示例：`@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))`

### 输出规则
- **必须启用 rich 库** 来格式化控制台输出
- 使用 rich 实现进度条、表格、面板和格式化文本

### 缓存规则
- **只缓存成功的响应**，绝不缓存错误结果
- 根据数据变化频率设置合适的缓存 TTL（过期时间）

### FastAPI 规则
- 所有路由必须添加限流装饰器
- 使用依赖注入来管理服务、数据库连接和认证
- 所有数据库操作必须使用异步方式

## 代码风格规范

### Python/FastAPI
- 异步操作使用 `async def`
- 所有函数签名必须添加类型注解
- 优先使用 Pydantic 模型，而非原始字典
- 采用函数式、声明式编程风格；除服务层和代理层外，尽量避免使用类
- 文件命名：小写加下划线（例如：`user_routes.py`）
- 使用 RORO 模式（接收对象，返回对象）

### 错误处理
- 在函数开头处理错误
- 对错误条件使用提前返回（early return）
- 将正常逻辑（happy path）放在函数末尾
- 使用 guard clauses（前置条件检查）
- 对预期错误使用 `HTTPException` 并附带合适的状态码

## LangGraph 与 LangChain 使用模式

### 图结构
- 使用 `StateGraph` 构建 AI 代理工作流
- 使用 Pydantic 模型定义清晰的状态结构（参见 `app/schemas/graph.py`）
- 生产环境使用 `CompiledStateGraph`
- 使用 `AsyncPostgresSaver` 实现检查点与持久化
- 使用 `Command` 控制图中节点之间的流转

### 链路追踪
- 使用 LangChain 的 `CallbackHandler`（来自 Langfuse）追踪所有 LLM 调用
- 所有 LLM 操作必须启用 Langfuse 追踪

### 记忆（mem0ai）
- 使用 `AsyncMemory` 进行语义记忆存储
- 按 user_id 存储记忆，实现个性化体验
- 使用异步方法：`add()`、`get()`、`search()`、`delete()`

## 认证与安全

- 使用 JWT token 进行身份认证
- 实现基于会话的用户管理（参见 `app/api/v1/auth.py`）
- 对受保护的接口使用 `get_current_session` 依赖
- 敏感数据存放在环境变量中
- 使用 Pydantic 模型校验所有用户输入

## 数据库操作

- 使用 SQLModel 作为 ORM 模型（整合了 SQLAlchemy + Pydantic）
- 模型定义放在 `app/models/` 目录下
- 使用 asyncpg 进行异步数据库操作
- 使用 LangGraph 的 AsyncPostgresSaver 实现代理检查点

## 性能指南

- 减少阻塞式 I/O 操作
- 所有数据库和外部 API 调用都使用异步方式
- 对频繁访问的数据实现缓存
- 使用数据库连接池
- 通过流式响应优化 LLM 调用

## 可观测性

- 在所有代理操作中集成 Langfuse 进行 LLM 链路追踪
- 导出 Prometheus 指标以监控 API 性能
- 使用带上下文绑定的结构化日志（request_id、session_id、user_id）
- 跟踪 LLM 推理耗时、token 用量和费用

## 测试与评估

- 对 LLM 输出实现基于指标的评估（参见 `evals/` 目录）
- 在 `evals/metrics/prompts/` 目录下以 markdown 文件形式创建自定义评估指标
- 使用 Langfuse 的追踪数据作为评估数据源
- 生成包含成功率的 JSON 报告

## 配置管理

- 使用环境专属的配置文件（`.env.development`、`.env.staging`、`.env.production`）
- 使用 Pydantic Settings 实现类型安全的配置管理（参见 `app/core/config.py`）
- 禁止硬编码密钥或 API Key

## 核心依赖

- **FastAPI** — Web 框架
- **LangGraph** — 代理工作流编排
- **LangChain** — LLM 抽象层与工具集
- **Langfuse** — LLM 可观测性与链路追踪
- **Pydantic v2** — 数据校验与配置管理
- **structlog** — 结构化日志
- **mem0ai** — 长期记忆管理
- **PostgreSQL + pgvector** — 数据库与向量存储
- **SQLModel** — 数据库模型 ORM
- **tenacity** — 重试逻辑
- **rich** — 终端格式化输出
- **slowapi** — 接口限流
- **prometheus-client** — 指标采集

## 本项目十大铁律

1. 所有路由必须添加限流装饰器
2. 所有 LLM 操作必须启用 Langfuse 追踪
3. 所有异步操作必须有完善的错误处理
4. 所有日志必须遵循结构化格式，事件名使用小写下划线命名
5. 所有重试必须使用 tenacity 库
6. 所有控制台输出应使用 rich 格式化
7. 所有缓存只存储成功的响应
8. 所有 import 必须放在文件顶部
9. 所有数据库操作必须使用异步方式
10. 所有接口必须添加类型注解和 Pydantic 模型

## 常见错误，务必避免

- ❌ 在 structlog 事件中使用 f-string
- ❌ 在函数内部添加 import
- ❌ 路由遗漏限流装饰器
- ❌ LLM 调用缺少 Langfuse 追踪
- ❌ 缓存了错误响应
- ❌ 处理异常时使用 `logger.error()` 而非 `logger.exception()`
- ❌ 没有使用异步的阻塞式 I/O 操作
- ❌ 硬编码密钥或 API Key
- ❌ 函数签名缺少类型注解

## 修改代码前的检查清单

在修改代码之前：
1. 先阅读现有的实现代码
2. 检查代码库中是否有相关的模式可以参考
3. 确保与现有代码风格保持一致
4. 添加结构化格式的日志
5. 包含错误处理，使用提前返回
6. 添加类型注解和 Pydantic 模型
7. 确认 LLM 调用已启用 Langfuse 追踪

## 参考文档

- LangGraph 文档：https://langchain-ai.github.io/langgraph/
- LangChain 文档：https://python.langchain.com/docs/
- FastAPI 文档：https://fastapi.tiangolo.com/
- Langfuse 文档：https://langfuse.com/docs
