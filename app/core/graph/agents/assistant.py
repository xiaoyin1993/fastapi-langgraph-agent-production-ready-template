"""Assistant Agent — 意图路由智能助手，支持闲聊/问答/任务/工具/数据分析。"""

from app.core.graph.agent import ASSISTANT_DESCRIPTION, LangGraphAgent
from app.core.graph.registry import agent


@agent("assistant", description=ASSISTANT_DESCRIPTION)
async def build_assistant(checkpointer, store):
    """构建 assistant agent 图。extras 中存放 LangGraphAgent 实例供 mem0ai 使用。"""
    agent_instance = LangGraphAgent()
    graph = agent_instance.build_graph(checkpointer=checkpointer)
    if graph and store:
        graph.store = store
    return graph, {"agent_ref": agent_instance}
