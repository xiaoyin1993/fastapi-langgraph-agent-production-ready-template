"""LangGraphAgent — 意图路由 Agent 的图构建器。

只负责构建 StateGraph 并编译，不管理基础设施（连接池、checkpointer 等由 AgentManager 管理）。
"""

from typing import Optional

from langgraph.graph import (
    END,
    StateGraph,
)
from langgraph.graph.state import CompiledStateGraph

from app.core.tools import tools
from app.infrastructure.config import settings
from app.infrastructure.logging import logger
from app.schemas import GraphState
from app.services.llm import llm_service

from app.core.graph.memory import MemoryMixin
from app.core.graph.nodes import NodesMixin

ASSISTANT_DESCRIPTION = "智能助手，支持意图路由（闲聊/问答/任务/工具/数据分析），自动分类并调用对应策略。"


class LangGraphAgent(MemoryMixin, NodesMixin):
    """意图路由 Agent 的图构建器。

    负责定义 StateGraph 节点和边，编译后注册到 AgentManager。
    MemoryMixin 提供 mem0ai 长期记忆，NodesMixin 提供节点实现。
    """

    def __init__(self):
        """初始化 Agent 及其工具绑定。"""
        self.llm_service = llm_service
        self.llm_service.bind_tools(tools)
        self.tools_by_name = {tool.name: tool for tool in tools}
        self.memory = None
        logger.info(
            "langgraph_agent_initialized",
            model=settings.DEFAULT_LLM_MODEL,
            environment=settings.ENVIRONMENT.value,
        )

    def build_graph(self, checkpointer=None) -> Optional[CompiledStateGraph]:
        """构建并编译 LangGraph 工作流。

        Args:
            checkpointer: 外部传入的 checkpointer 实例（由 AgentManager 管理）。

        Returns:
            CompiledStateGraph: 编译好的图实例。
        """
        try:
            graph_builder = StateGraph(GraphState)

            # 意图路由节点
            graph_builder.add_node(
                "router",
                self._router,
                destinations=("chat_node", "qa_node", "task_node", "tool_node", "data_node"),
            )

            # 各意图处理节点
            graph_builder.add_node("chat_node", self._chat_node, destinations=(END,))
            graph_builder.add_node("qa_node", self._qa_node, destinations=("tool_call", END))
            graph_builder.add_node("task_node", self._task_node, destinations=(END,))
            graph_builder.add_node("tool_node", self._tool_node, destinations=("tool_call", END))
            graph_builder.add_node("data_node", self._data_node, destinations=("tool_call", END))

            # 工具执行节点
            graph_builder.add_node(
                "tool_call",
                self._tool_call,
                destinations=("qa_node", "tool_node", "data_node"),
            )

            # 入口点：所有请求先经过 router
            graph_builder.set_entry_point("router")

            compiled = graph_builder.compile(
                checkpointer=checkpointer,
                name=f"{settings.PROJECT_NAME} Assistant ({settings.ENVIRONMENT.value})",
            )

            logger.info(
                "assistant_graph_built",
                graph_name=f"{settings.PROJECT_NAME} Assistant",
                environment=settings.ENVIRONMENT.value,
                has_checkpointer=checkpointer is not None,
            )
            return compiled
        except Exception as e:
            logger.exception("assistant_graph_build_failed", error=str(e))
            raise
