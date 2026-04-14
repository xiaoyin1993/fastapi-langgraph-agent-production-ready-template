"""AgentManager — 管理所有 Agent 的生命周期、基础设施和请求路由。

职责：
- 管理 PostgreSQL 连接池、checkpointer、store
- 注册和初始化所有 Agent
- 处理 interrupt 检测与恢复
- 提供统一的 get_response / get_stream_response / get_chat_history API
"""

import asyncio
from typing import (
    AsyncGenerator,
    Optional,
)
from urllib.parse import quote_plus

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    convert_to_openai_messages,
)
from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.postgres import AsyncPostgresStore
from langgraph.types import Command, StateSnapshot
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.infrastructure.callbacks import AgentCallbackHandler
from app.infrastructure.config import (
    Environment,
    settings,
)
from app.infrastructure.logging import logger
from app.schemas import Message
from app.utils import dump_messages

from app.core.graph.registry import (
    DEFAULT_AGENT,
    AgentGraph,
    discover_agents,
    get_agent,
    get_agent_extras,
    get_all_agents_info,
    initialize_all,
)


class AgentManager:
    """管理所有 Agent 的生命周期：连接池、checkpointer、store、记忆。"""

    def __init__(self):
        """初始化 AgentManager。"""
        self._checkpointer_pool: Optional[AsyncConnectionPool] = None
        self._store_pool: Optional[AsyncConnectionPool] = None
        self._checkpointer: Optional[AsyncPostgresSaver] = None
        self._store: Optional[AsyncPostgresStore] = None

    def _build_connection_url(self) -> str:
        """构建 PostgreSQL 连接 URL。"""
        return (
            "postgresql://"
            f"{quote_plus(settings.POSTGRES_USER)}:{quote_plus(settings.POSTGRES_PASSWORD)}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )

    async def _create_pool(self, application_name: str) -> AsyncConnectionPool:
        """创建 PostgreSQL 连接池。"""
        pool = AsyncConnectionPool(
            self._build_connection_url(),
            open=False,
            max_size=settings.POSTGRES_POOL_SIZE,
            kwargs={
                "autocommit": True,
                "connect_timeout": 5,
                "prepare_threshold": None,
                "row_factory": dict_row,
            },
        )
        await pool.open()
        logger.info("connection_pool_created", application_name=application_name, max_size=settings.POSTGRES_POOL_SIZE)
        return pool

    async def initialize(self) -> None:
        """初始化所有基础设施和 Agent。

        1. 创建连接池
        2. 初始化 checkpointer 和 store
        3. 构建并注册所有 Agent
        4. 为 Agent 注入 checkpointer 和 store
        """
        try:
            # 1. 创建连接池
            self._checkpointer_pool = await self._create_pool("checkpointer")
            self._store_pool = await self._create_pool("store")

            # 2. 初始化 checkpointer
            self._checkpointer = AsyncPostgresSaver(self._checkpointer_pool)
            await self._checkpointer.setup()
            logger.info("checkpointer_initialized")

            # 3. 初始化 store
            self._store = AsyncPostgresStore(self._store_pool)
            await self._store.setup()
            logger.info("store_initialized")

            # 4. 自动发现并初始化所有 Agent
            discover_agents()
            await initialize_all(self._checkpointer, self._store)

            logger.info(
                "agent_manager_initialized",
                agent_count=len(get_all_agents_info()),
                environment=settings.ENVIRONMENT.value,
            )
        except Exception as e:
            logger.exception("agent_manager_initialization_failed", error=str(e))
            if settings.ENVIRONMENT == Environment.PRODUCTION:
                logger.warning("continuing_with_degraded_mode")
            else:
                raise

    def _get_assistant_ref(self):
        """获取 assistant agent 的 LangGraphAgent 实例（用于 mem0ai 记忆操作）。"""
        try:
            return get_agent_extras(DEFAULT_AGENT).get("agent_ref")
        except KeyError:
            return None

    async def shutdown(self) -> None:
        """关闭所有连接池。"""
        if self._checkpointer_pool:
            await self._checkpointer_pool.close()
            logger.info("checkpointer_pool_closed")
        if self._store_pool:
            await self._store_pool.close()
            logger.info("store_pool_closed")

    def _build_config(self, session_id: str, user_id: Optional[str] = None) -> dict:
        """构建 LangGraph 运行时配置。"""
        return {
            "configurable": {
                "thread_id": session_id,
                "user_id": user_id or "",
            },
            # "callbacks": [CallbackHandler(), AgentCallbackHandler()],
            "callbacks": [CallbackHandler()],
            "metadata": {
                "user_id": user_id,
                "session_id": session_id,
                "environment": settings.ENVIRONMENT.value,
                "debug": settings.DEBUG,
            },
        }

    async def _handle_input(
        self,
        agent: AgentGraph,
        messages: list[Message],
        config: dict,
    ) -> dict | Command:
        """处理输入，检测 interrupt 并决定是恢复还是新消息。

        Args:
            agent: 编译后的图实例。
            messages: 用户消息列表。
            config: LangGraph 运行时配置。

        Returns:
            dict | Command: 正常消息输入或 interrupt 恢复 Command。
        """
        # 判断是否有中断的任务，比如让用户选择是否继续等
        state = await agent.aget_state(config=config)
        interrupted_tasks = [task for task in state.tasks if hasattr(task, "interrupts") and task.interrupts]

        if interrupted_tasks:
            # 用户消息作为 interrupt 恢复值
            logger.info("resuming_from_interrupt", session_id=config["configurable"]["thread_id"])
            return Command(resume=messages[-1].content)

        return {"messages": dump_messages(messages), "long_term_memory": ""}

    async def _prepare_input_with_memory(
        self,
        agent_id: str,
        messages: list[Message],
        user_id: Optional[str],
        config: dict,
        agent: AgentGraph,
    ) -> dict | Command:
        """准备带记忆的输入（仅 assistant agent 支持 mem0ai 记忆）。"""
        input_data = await self._handle_input(agent, messages, config)

        # 如果是 interrupt 恢复，直接返回 Command
        if isinstance(input_data, Command):
            return input_data

        # 仅 assistant agent 加载 mem0ai 长期记忆
        assistant_ref = self._get_assistant_ref()
        if agent_id == DEFAULT_AGENT and assistant_ref and user_id:
            relevant_memory = (await assistant_ref._get_relevant_memory(user_id, messages[-1].content)) or ""
            if relevant_memory:
                input_data["long_term_memory"] = relevant_memory

        return input_data

    async def get_response(
        self,
        agent_id: str,
        messages: list[Message],
        session_id: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
    ) -> list[Message]:
        """通过指定 Agent 获取回复。

        Args:
            agent_id: Agent 标识。
            messages: 用户消息列表。
            session_id: 会话 ID。
            user_id: 用户 ID。
            username: 用户名（用于 Langfuse 追踪）。

        Returns:
            list[Message]: Agent 的回复消息列表。
        """
        agent = get_agent(agent_id)
        config = self._build_config(session_id, user_id)
        input_data = await self._prepare_input_with_memory(agent_id, messages, user_id, config, agent)

        try:
            with propagate_attributes(session_id=session_id, user_id=username or str(user_id)):
                response = await agent.ainvoke(input=input_data, config=config)

            # assistant agent 异步更新 mem0ai 记忆
            assistant_ref = self._get_assistant_ref()
            if agent_id == DEFAULT_AGENT and assistant_ref and user_id:
                asyncio.create_task(
                    assistant_ref._update_long_term_memory(
                        user_id, convert_to_openai_messages(response["messages"]), config["metadata"]
                    )
                )

            return _process_messages(response["messages"])
        except Exception as e:
            logger.exception(
                "get_response_failed", agent_id=agent_id, session_id=session_id, user_id=user_id, error=str(e)
            )
            raise

    async def get_stream_response(
        self,
        agent_id: str,
        messages: list[Message],
        session_id: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """通过指定 Agent 获取流式回复。

        Args:
            agent_id: Agent 标识。
            messages: 用户消息列表。
            session_id: 会话 ID。
            user_id: 用户 ID。
            username: 用户名（用于 Langfuse 追踪）。

        Yields:
            str: LLM 回复的 token 片段。
        """
        agent = get_agent(agent_id)
        config = self._build_config(session_id, user_id)
        input_data = await self._prepare_input_with_memory(agent_id, messages, user_id, config, agent)

        try:
            with propagate_attributes(session_id=session_id, user_id=username or str(user_id)):
                async for event in agent.astream_events(input_data, config, version="v2"):
                    kind = event.get("event", "")
                    if kind == "on_chat_model_stream":
                        # 过滤 router 节点的输出
                        node_name = event.get("metadata", {}).get("langgraph_node", "")
                        if node_name == "router":
                            continue
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            yield chunk.content

            # 流式完成后异步更新 mem0ai 记忆
            assistant_ref = self._get_assistant_ref()
            if agent_id == DEFAULT_AGENT and assistant_ref and user_id:
                state: StateSnapshot = await agent.aget_state(config=config)
                if state.values and "messages" in state.values:
                    asyncio.create_task(
                        assistant_ref._update_long_term_memory(
                            user_id, convert_to_openai_messages(state.values["messages"]), config["metadata"]
                        )
                    )
        except Exception as e:
            logger.exception("stream_response_failed", agent_id=agent_id, session_id=session_id, error=str(e))
            raise

    async def get_chat_history(self, agent_id: str, session_id: str) -> list[Message]:
        """获取指定会话的聊天历史。

        Args:
            agent_id: Agent 标识。
            session_id: 会话 ID。

        Returns:
            list[Message]: 聊天历史消息列表。
        """
        agent = get_agent(agent_id)
        state: StateSnapshot = await agent.aget_state(config={"configurable": {"thread_id": session_id}})
        return _process_messages(state.values["messages"]) if state.values else []

    async def clear_chat_history(self, session_id: str) -> None:
        """清除指定会话的所有聊天历史。

        Args:
            session_id: 要清除的会话 ID。
        """
        try:
            async with self._checkpointer_pool.connection() as conn:
                for table in settings.CHECKPOINT_TABLES:
                    try:
                        await conn.execute(f"DELETE FROM {table} WHERE thread_id = %s", (session_id,))
                        logger.info("checkpoint_table_cleared", table=table, session_id=session_id)
                    except Exception as e:
                        logger.exception(
                            "checkpoint_table_clear_failed", table=table, session_id=session_id, error=str(e)
                        )
                        raise
        except Exception as e:
            logger.exception("clear_chat_history_failed", session_id=session_id, error=str(e))
            raise


def _process_messages(messages: list[BaseMessage]) -> list[Message]:
    """将 LangChain 消息转换为 API 响应格式。"""
    openai_style_messages = convert_to_openai_messages(messages)
    return [
        Message(role=message["role"], content=str(message["content"]))
        for message in openai_style_messages
        if message["role"] in ["assistant", "user"] and message["content"]
    ]


# 全局单例
agent_manager = AgentManager()
