"""本文件包含 LangGraph 智能体/工作流以及与大语言模型的交互逻辑。"""

import asyncio
import json
from typing import (
    AsyncGenerator,
    Optional,
)
from urllib.parse import quote_plus

from asgiref.sync import sync_to_async
from langchain_core.messages import (
    BaseMessage,
    ToolMessage,
    convert_to_openai_messages,
)
from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import (
    END,
    StateGraph,
)
from langgraph.graph.state import (
    Command,
    CompiledStateGraph,
)
from langgraph.types import (
    RunnableConfig,
    StateSnapshot,
)
from mem0 import AsyncMemory
from psycopg_pool import AsyncConnectionPool

from app.infrastructure.config import (
    Environment,
    settings,
)
from app.core.tools import tools
from app.infrastructure.logging import logger
from app.infrastructure.metrics import llm_inference_duration_seconds
from app.core.prompts import load_intent_prompt, load_router_prompt, load_system_prompt
from app.schemas import (
    GraphState,
    Message,
)
from app.services.llm import LLMRegistry, llm_service
from app.utils import (
    dump_messages,
    prepare_messages,
    process_llm_response,
)


class LangGraphAgent:
    """管理 LangGraph 智能体/工作流以及与大语言模型的交互。

    这个类负责创建和管理 LangGraph 工作流，
    包括大语言模型交互、数据库连接和响应处理。
    """

    def __init__(self):
        """初始化 LangGraph 智能体及其必要组件。"""
        # 使用绑定了工具的大语言模型服务
        self.llm_service = llm_service
        self.llm_service.bind_tools(tools)
        self.tools_by_name = {tool.name: tool for tool in tools}
        self._connection_pool: Optional[AsyncConnectionPool] = None
        self._graph: Optional[CompiledStateGraph] = None
        self.memory: Optional[AsyncMemory] = None
        logger.info(
            "langgraph_agent_initialized",
            model=settings.DEFAULT_LLM_MODEL,
            environment=settings.ENVIRONMENT.value,
        )

    @staticmethod
    def _build_mem0_provider_config(model: str) -> dict:
        """构建 mem0ai 的 provider 配置。"""
        config = {"provider": settings.LLM_PROVIDER, "config": {"model": model}}
        if settings.LLM_PROVIDER == "ollama":
            config["config"]["ollama_base_url"] = settings.OLLAMA_BASE_URL
        return config

    async def _long_term_memory(self) -> AsyncMemory:
        """初始化长期记忆。"""
        if self.memory is None:
            self.memory = await AsyncMemory.from_config(
                config_dict={
                    "vector_store": {
                        "provider": "pgvector",
                        "config": {
                            "collection_name": settings.LONG_TERM_MEMORY_COLLECTION_NAME,
                            "embedding_model_dims": settings.LONG_TERM_MEMORY_EMBEDDING_DIMS,
                            "dbname": settings.POSTGRES_DB,
                            "user": settings.POSTGRES_USER,
                            "password": settings.POSTGRES_PASSWORD,
                            "host": settings.POSTGRES_HOST,
                            "port": settings.POSTGRES_PORT,
                        },
                    },
                    "llm": self._build_mem0_provider_config(settings.LONG_TERM_MEMORY_MODEL),
                    "embedder": self._build_mem0_provider_config(settings.LONG_TERM_MEMORY_EMBEDDER_MODEL),
                }
            )
        return self.memory

    async def _get_connection_pool(self) -> AsyncConnectionPool:
        """获取 PostgreSQL 连接池，使用环境相关的配置。

        Returns:
            AsyncConnectionPool: PostgreSQL 数据库的连接池。
        """
        if self._connection_pool is None:
            try:
                # 根据环境配置连接池大小
                max_size = settings.POSTGRES_POOL_SIZE

                connection_url = (
                    "postgresql://"
                    f"{quote_plus(settings.POSTGRES_USER)}:{quote_plus(settings.POSTGRES_PASSWORD)}"
                    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
                )

                self._connection_pool = AsyncConnectionPool(
                    connection_url,
                    open=False,
                    max_size=max_size,
                    kwargs={
                        "autocommit": True,
                        "connect_timeout": 5,
                        "prepare_threshold": None,
                    },
                )
                await self._connection_pool.open()
                logger.info("connection_pool_created", max_size=max_size, environment=settings.ENVIRONMENT.value)
            except Exception as e:
                logger.error("connection_pool_creation_failed", error=str(e), environment=settings.ENVIRONMENT.value)
                # 生产环境下可能需要优雅降级
                if settings.ENVIRONMENT == Environment.PRODUCTION:
                    logger.warning("continuing_without_connection_pool", environment=settings.ENVIRONMENT.value)
                    return None
                raise e
        return self._connection_pool

    async def _get_relevant_memory(self, user_id: str, query: str) -> str:
        """获取与用户和查询相关的记忆。

        Args:
            user_id (str): 用户 ID。
            query (str): 要搜索的查询内容。

        Returns:
            str: 相关的记忆内容。
        """
        try:
            memory = await self._long_term_memory()
            results = await memory.search(user_id=str(user_id), query=query)
            print(results)
            return "\n".join([f"* {result['memory']}" for result in results["results"]])
        except Exception as e:
            logger.error("failed_to_get_relevant_memory", error=str(e), user_id=user_id, query=query)
            return ""

    async def _update_long_term_memory(self, user_id: str, messages: list[dict], metadata: dict = None) -> None:
        """更新长期记忆。

        Args:
            user_id (str): 用户 ID。
            messages (list[dict]): 用于更新长期记忆的消息列表。
            metadata (dict): 可选的元数据。
        """
        try:
            memory = await self._long_term_memory()
            await memory.add(messages, user_id=str(user_id), metadata=metadata)
            logger.info("long_term_memory_updated_successfully", user_id=user_id)
        except Exception as e:
            logger.exception(
                "failed_to_update_long_term_memory",
                user_id=user_id,
                error=str(e),
            )

    async def _tool_call(self, state: GraphState) -> Command:
        """处理最后一条消息中的工具调用。

        Args:
            state: 包含消息和工具调用的当前智能体状态。

        Returns:
            Command: 包含更新后消息并路由回对应意图节点的 Command 对象。
        """
        outputs = []
        for tool_call in state.messages[-1].tool_calls:
            tool_result = await self.tools_by_name[tool_call["name"]].ainvoke(tool_call["args"])
            outputs.append(
                ToolMessage(
                    content=tool_result,
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )
        # 根据意图路由回对应的处理节点
        intent_to_node = {
            "qa": "qa_node",
            "tool": "tool_node",
            "data_analysis": "data_node",
        }
        goto = intent_to_node.get(state.intent, "tool_node")
        return Command(update={"messages": outputs}, goto=goto)

    async def _router(self, state: GraphState) -> Command:
        """意图分类节点：使用轻量 LLM 判断用户意图。

        Args:
            state: 当前对话状态。

        Returns:
            Command: 包含 intent 和 intent_confidence 的状态更新。
        """
        # 提取最新的用户消息
        user_message = ""
        for msg in reversed(state.messages):
            if hasattr(msg, "type") and msg.type == "human":
                user_message = msg.content
                break
            elif hasattr(msg, "role") and msg.role == "user":
                user_message = msg.content
                break

        if not user_message:
            return Command(
                update={"intent": "chat", "intent_confidence": 0.5},
                goto="chat_node",
            )

        # 使用默认模型做意图分类
        router_prompt = load_router_prompt(user_message=user_message)
        router_llm = LLMRegistry.get(settings.DEFAULT_LLM_MODEL)

        try:
            response = await router_llm.ainvoke([{"role": "user", "content": router_prompt}])
            content = response.content.strip()

            # 清理可能的 markdown 代码块包裹
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            result = json.loads(content)
            intent = result.get("intent", "qa")
            confidence = result.get("confidence", 0.5)

            # 验证 intent 是否合法
            valid_intents = {"chat", "qa", "task", "tool", "data_analysis"}
            if intent not in valid_intents:
                intent = "qa"
                confidence = 0.3

            logger.info(
                "intent_classified",
                intent=intent,
                confidence=confidence,
                user_message=user_message[:50],
            )
        except Exception as e:
            logger.exception("intent_classification_failed", error=str(e))
            intent = "qa"
            confidence = 0.0

        # 意图到节点的映射
        intent_to_node = {
            "chat": "chat_node",
            "qa": "qa_node",
            "task": "task_node",
            "tool": "tool_node",
            "data_analysis": "data_node",
        }
        goto = intent_to_node.get(intent, "qa_node")

        return Command(
            update={"intent": intent, "intent_confidence": confidence},
            goto=goto,
        )

    async def _chat_node(self, state: GraphState, config: RunnableConfig) -> Command:
        """闲聊节点：轻松友好地回复，不调用工具。"""
        prompt = load_intent_prompt("chat", long_term_memory=state.long_term_memory)
        return await self._llm_respond(state, config, prompt)

    async def _qa_node(self, state: GraphState, config: RunnableConfig) -> Command:
        """知识问答节点：准确严谨地回答，可能调用搜索工具。"""
        prompt = load_intent_prompt("qa", long_term_memory=state.long_term_memory)
        return await self._llm_respond(state, config, prompt, allow_tools=True)

    async def _task_node(self, state: GraphState, config: RunnableConfig) -> Command:
        """任务执行节点：专业高效地完成创作任务。"""
        prompt = load_intent_prompt("task", long_term_memory=state.long_term_memory)
        return await self._llm_respond(state, config, prompt)

    async def _tool_node(self, state: GraphState, config: RunnableConfig) -> Command:
        """工具编排节点：调用外部工具获取信息。"""
        prompt = load_system_prompt(long_term_memory=state.long_term_memory)
        return await self._llm_respond(state, config, prompt, allow_tools=True)

    async def _data_node(self, state: GraphState, config: RunnableConfig) -> Command:
        """数据分析节点：查询数据并生成分析结果。"""
        prompt = load_intent_prompt("data_analysis", long_term_memory=state.long_term_memory)
        return await self._llm_respond(state, config, prompt, allow_tools=True)

    async def _llm_respond(
        self,
        state: GraphState,
        config: RunnableConfig,
        system_prompt: str,
        allow_tools: bool = False,
    ) -> Command:
        """通用 LLM 响应方法，供各节点复用。

        Args:
            state: 当前对话状态。
            config: LangGraph 运行时配置。
            system_prompt: 该节点使用的系统提示词。
            allow_tools: 是否允许工具调用。

        Returns:
            Command: 包含 LLM 响应的 Command 对象。
        """
        current_llm = self.llm_service.get_llm()
        model_name = (
            current_llm.model_name
            if current_llm and hasattr(current_llm, "model_name")
            else settings.DEFAULT_LLM_MODEL
        )

        messages = prepare_messages(state.messages, current_llm, system_prompt)

        try:
            with llm_inference_duration_seconds.labels(model=model_name).time():
                response_message = await self.llm_service.call(messages)

            response_message = process_llm_response(response_message)

            logger.info(
                "llm_response_generated",
                intent=state.intent,
                session_id=config["configurable"]["thread_id"],
                model=model_name,
                environment=settings.ENVIRONMENT.value,
            )

            # 根据是否允许工具调用和是否有工具调用来决定下一步
            if allow_tools and response_message.tool_calls:
                goto = "tool_call"
            else:
                goto = END

            return Command(update={"messages": [response_message]}, goto=goto)
        except Exception as e:
            logger.error(
                "llm_call_failed_all_models",
                intent=state.intent,
                session_id=config["configurable"]["thread_id"],
                error=str(e),
                environment=settings.ENVIRONMENT.value,
            )
            raise Exception(f"failed to get llm response after trying all models: {str(e)}")

    async def create_graph(self) -> Optional[CompiledStateGraph]:
        """创建并配置 LangGraph 工作流。

        Returns:
            Optional[CompiledStateGraph]: 配置好的 LangGraph 实例，如果初始化失败则返回 None。
        """
        if self._graph is None:
            try:
                graph_builder = StateGraph(GraphState)

                # 意图路由节点
                graph_builder.add_node(
                    "router", self._router,
                    destinations=("chat_node", "qa_node", "task_node", "tool_node", "data_node"),
                )

                # 各意图处理节点
                graph_builder.add_node(
                    "chat_node", self._chat_node,
                    destinations=(END,),
                )
                graph_builder.add_node(
                    "qa_node", self._qa_node,
                    destinations=("tool_call", END),
                )
                graph_builder.add_node(
                    "task_node", self._task_node,
                    destinations=(END,),
                )
                graph_builder.add_node(
                    "tool_node", self._tool_node,
                    destinations=("tool_call", END),
                )
                graph_builder.add_node(
                    "data_node", self._data_node,
                    destinations=("tool_call", END),
                )

                # 工具执行节点
                graph_builder.add_node(
                    "tool_call", self._tool_call,
                    destinations=("qa_node", "tool_node", "data_node"),
                )

                # 入口点：所有请求先经过 router
                graph_builder.set_entry_point("router")

                # 获取连接池（生产环境下如果数据库不可用可能返回 None）
                connection_pool = await self._get_connection_pool()
                if connection_pool:
                    checkpointer = AsyncPostgresSaver(connection_pool)
                    await checkpointer.setup()
                else:
                    # 生产环境下，即使没有 checkpointer 也继续运行
                    checkpointer = None
                    if settings.ENVIRONMENT != Environment.PRODUCTION:
                        raise Exception("Connection pool initialization failed")

                self._graph = graph_builder.compile(
                    checkpointer=checkpointer, name=f"{settings.PROJECT_NAME} Agent ({settings.ENVIRONMENT.value})"
                )

                logger.info(
                    "graph_created",
                    graph_name=f"{settings.PROJECT_NAME} Agent",
                    environment=settings.ENVIRONMENT.value,
                    has_checkpointer=checkpointer is not None,
                )
            except Exception as e:
                logger.error("graph_creation_failed", error=str(e), environment=settings.ENVIRONMENT.value)
                # 生产环境下不要让应用崩溃
                if settings.ENVIRONMENT == Environment.PRODUCTION:
                    logger.warning("continuing_without_graph")
                    return None
                raise e

        return self._graph

    async def get_response(
        self,
        messages: list[Message],
        session_id: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
    ) -> list[dict]:
        """从大语言模型获取回复。

        Args:
            messages (list[Message]): 发送给大语言模型的消息列表。
            session_id (str): 用于 Langfuse 追踪的会话 ID。
            user_id (Optional[str]): 用于 Langfuse 追踪的用户 ID。

        Returns:
            list[dict]: 大语言模型的回复。
        """
        if self._graph is None:
            self._graph = await self.create_graph()
        config = {
            "configurable": {"thread_id": session_id},
            "callbacks": [CallbackHandler()],
            "metadata": {
                "user_id": user_id,
                "session_id": session_id,
                "environment": settings.ENVIRONMENT.value,
                "debug": settings.DEBUG,
            },
        }

        relevant_memory = (
            await self._get_relevant_memory(user_id, messages[-1].content)
        ) or "No relevant memory found."

        try:
            with propagate_attributes(session_id=session_id, user_id=username or str(user_id)):
                response = await self._graph.ainvoke(
                    input={"messages": dump_messages(messages), "long_term_memory": relevant_memory},
                    config=config,
                )
            # 在后台异步更新记忆，不阻塞响应
            asyncio.create_task(
                self._update_long_term_memory(
                    user_id, convert_to_openai_messages(response["messages"]), config["metadata"]
                )
            )
            return self.__process_messages(response["messages"])
        except Exception as e:
            logger.error(f"Error getting response: {str(e)}")

    async def get_stream_response(
        self, messages: list[Message], session_id: str, user_id: Optional[str] = None, username: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """从大语言模型获取流式回复。

        Args:
            messages (list[Message]): 发送给大语言模型的消息列表。
            session_id (str): 对话的会话 ID。
            user_id (Optional[str]): 对话的用户 ID。

        Yields:
            str: 大语言模型回复的 token 片段。
        """
        config = {
            "configurable": {"thread_id": session_id},
            "callbacks": [CallbackHandler()],
            "metadata": {
                "user_id": user_id,
                "session_id": session_id,
                "environment": settings.ENVIRONMENT.value,
                "debug": settings.DEBUG,
            },
        }
        if self._graph is None:
            self._graph = await self.create_graph()

        relevant_memory = (
            await self._get_relevant_memory(user_id, messages[-1].content)
        ) or "No relevant memory found."

        try:
            with propagate_attributes(session_id=session_id, user_id=username or str(user_id)):
                async for event in self._graph.astream_events(
                    {"messages": dump_messages(messages), "long_term_memory": relevant_memory},
                    config,
                    version="v2",
                ):
                    kind = event.get("event", "")
                    if kind == "on_chat_model_stream":
                        # 过滤 router 节点的输出（意图分类 JSON 不发给用户）
                        node_name = event.get("metadata", {}).get("langgraph_node", "")
                        if node_name == "router":
                            continue
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            yield chunk.content

            # 流式传输完成后，获取最终状态并在后台更新记忆
            state: StateSnapshot = await sync_to_async(self._graph.get_state)(config=config)
            if state.values and "messages" in state.values:
                asyncio.create_task(
                    self._update_long_term_memory(
                        user_id, convert_to_openai_messages(state.values["messages"]), config["metadata"]
                    )
                )
        except Exception as stream_error:
            logger.error("Error in stream processing", error=str(stream_error), session_id=session_id)
            raise stream_error

    async def get_chat_history(self, session_id: str) -> list[Message]:
        """获取指定会话 ID 的聊天历史记录。

        Args:
            session_id (str): 对话的会话 ID。

        Returns:
            list[Message]: 聊天历史记录。
        """
        if self._graph is None:
            self._graph = await self.create_graph()

        state: StateSnapshot = await sync_to_async(self._graph.get_state)(
            config={"configurable": {"thread_id": session_id}}
        )
        return self.__process_messages(state.values["messages"]) if state.values else []

    def __process_messages(self, messages: list[BaseMessage]) -> list[Message]:
        openai_style_messages = convert_to_openai_messages(messages)
        # 只保留 assistant 和 user 的消息
        return [
            Message(role=message["role"], content=str(message["content"]))
            for message in openai_style_messages
            if message["role"] in ["assistant", "user"] and message["content"]
        ]

    async def clear_chat_history(self, session_id: str) -> None:
        """清除指定会话 ID 的所有聊天历史记录。

        Args:
            session_id: 要清除历史记录的会话 ID。

        Raises:
            Exception: 清除聊天历史记录时发生错误。
        """
        try:
            # 确保连接池在当前事件循环中已初始化
            conn_pool = await self._get_connection_pool()

            # 为这个操作使用一个新的连接
            async with conn_pool.connection() as conn:
                for table in settings.CHECKPOINT_TABLES:
                    try:
                        await conn.execute(f"DELETE FROM {table} WHERE thread_id = %s", (session_id,))
                        logger.info(f"Cleared {table} for session {session_id}")
                    except Exception as e:
                        logger.error(f"Error clearing {table}", error=str(e))
                        raise

        except Exception as e:
            logger.error("Failed to clear chat history", error=str(e))
            raise
