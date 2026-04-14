"""LangGraph 图节点实现 Mixin，包含意图路由、各意图处理节点和工具调用。"""

import json

from langchain_core.messages import ToolMessage
from langgraph.graph import END
from langgraph.graph.state import Command
from langgraph.types import RunnableConfig

from app.infrastructure.config import settings
from app.infrastructure.logging import logger
from app.infrastructure.metrics import llm_inference_duration_seconds
from app.core.prompts import load_intent_prompt, load_router_prompt, load_system_prompt
from app.schemas import GraphState
from app.services.llm import LLMRegistry
from app.utils import prepare_messages, process_llm_response


class NodesMixin:
    """为 LangGraphAgent 提供图节点实现。

    依赖主类初始化 self.tools_by_name 和 self.llm_service 属性。
    """

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
