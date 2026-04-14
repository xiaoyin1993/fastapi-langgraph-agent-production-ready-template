"""Chatbot Agent — 简单闲聊机器人，轻松友好地回复，不调用任何工具。"""

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.func import entrypoint

from app.core.graph.registry import agent
from app.infrastructure.config import settings
from app.services.llm import LLMRegistry

CHATBOT_DESCRIPTION = "简单闲聊机器人，轻松友好地回复，不调用任何工具。"


@entrypoint()
async def _chatbot_graph(
    inputs: dict[str, list[BaseMessage]],
    *,
    previous: dict[str, list[BaseMessage]],
    config: RunnableConfig,
):
    """简单闲聊 Agent，直接调用 LLM 生成回复。"""
    messages = inputs["messages"]
    if previous:
        messages = previous["messages"] + messages

    model = LLMRegistry.get(settings.DEFAULT_LLM_MODEL)
    response = await model.ainvoke(messages)

    return entrypoint.final(
        value={"messages": [response]},
        save={"messages": messages + [response]},
    )


@agent("chatbot", description=CHATBOT_DESCRIPTION)
async def build_chatbot(checkpointer, store):
    """构建 chatbot agent，注入 checkpointer 和 store。"""
    _chatbot_graph.checkpointer = checkpointer
    if store:
        _chatbot_graph.store = store
    return _chatbot_graph
