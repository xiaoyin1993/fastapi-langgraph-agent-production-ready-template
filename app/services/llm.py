"""LLM 服务，负责管理 LLM 调用的重试和降级机制。"""

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from openai import (
    APIError,
    APITimeoutError,
    OpenAIError,
    RateLimitError,
)
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.infrastructure.config import (
    Environment,
    settings,
)
from app.infrastructure.logging import logger


class LLMRegistry:
    """可用 LLM 模型的注册表，包含预初始化的实例。

    这个类维护了一个 LLM 配置列表，提供按名称检索模型的方法，
    并支持覆盖默认参数。
    """

    # 类级别变量，包含所有可用的 LLM 模型
    LLMS: List[Dict[str, Any]] = [
        {
            "name": "gpt-5-mini",
            "llm": ChatOpenAI(
                model="gpt-5-mini",
                api_key=settings.OPENAI_API_KEY,
                max_tokens=settings.MAX_TOKENS,
                reasoning={"effort": "low"},
            ),
        },
        {
            "name": "gpt-5",
            "llm": ChatOpenAI(
                model="gpt-5",
                api_key=settings.OPENAI_API_KEY,
                max_tokens=settings.MAX_TOKENS,
                reasoning={"effort": "medium"},
            ),
        },
        {
            "name": "gpt-5-nano",
            "llm": ChatOpenAI(
                model="gpt-5-nano",
                api_key=settings.OPENAI_API_KEY,
                max_tokens=settings.MAX_TOKENS,
                reasoning={"effort": "minimal"},
            ),
        },
        {
            "name": "gpt-4o",
            "llm": ChatOpenAI(
                model="gpt-4o",
                temperature=settings.DEFAULT_LLM_TEMPERATURE,
                api_key=settings.OPENAI_API_KEY,
                max_tokens=settings.MAX_TOKENS,
                top_p=0.95 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.8,
                presence_penalty=0.1 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.0,
                frequency_penalty=0.1 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.0,
            ),
        },
        {
            "name": "gpt-4o-mini",
            "llm": ChatOpenAI(
                model="gpt-4o-mini",
                temperature=settings.DEFAULT_LLM_TEMPERATURE,
                api_key=settings.OPENAI_API_KEY,
                max_tokens=settings.MAX_TOKENS,
                top_p=0.9 if settings.ENVIRONMENT == Environment.PRODUCTION else 0.8,
            ),
        },
    ]

    @classmethod
    def get(cls, model_name: str, **kwargs) -> BaseChatModel:
        """根据名称获取一个 LLM，可选择覆盖默认参数。

        Args:
            model_name: 要获取的模型名称
            **kwargs: 可选参数，用于覆盖默认的模型配置

        Returns:
            BaseChatModel 实例

        Raises:
            ValueError: 如果在注册表中找不到该模型名称
        """
        # 在注册表中查找模型
        model_entry = None
        for entry in cls.LLMS:
            if entry["name"] == model_name:
                model_entry = entry
                break

        if not model_entry:
            available_models = [entry["name"] for entry in cls.LLMS]
            raise ValueError(
                f"model '{model_name}' not found in registry. available models: {', '.join(available_models)}"
            )

        # 如果用户传入了自定义参数，就用这些参数创建一个新实例
        if kwargs:
            logger.debug("creating_llm_with_custom_args", model_name=model_name, custom_args=list(kwargs.keys()))
            return ChatOpenAI(model=model_name, api_key=settings.OPENAI_API_KEY, **kwargs)

        # 返回默认实例
        logger.debug("using_default_llm_instance", model_name=model_name)
        return model_entry["llm"]

    @classmethod
    def get_all_names(cls) -> List[str]:
        """按顺序获取所有已注册的 LLM 名称。

        Returns:
            LLM 名称列表
        """
        return [entry["name"] for entry in cls.LLMS]

    @classmethod
    def get_model_at_index(cls, index: int) -> Dict[str, Any]:
        """根据索引获取模型配置。

        Args:
            index: 模型在 LLMS 列表中的索引

        Returns:
            模型配置字典
        """
        if 0 <= index < len(cls.LLMS):
            return cls.LLMS[index]
        return cls.LLMS[0]  # 超出范围时回到第一个模型


class LLMService:
    """管理 LLM 调用的服务，支持重试和循环降级。

    这个服务处理所有 LLM 交互，包括自动重试逻辑、
    限流处理，以及在所有可用模型之间循环降级。
    """

    def __init__(self):
        """初始化 LLM 服务。"""
        self._llm: Optional[BaseChatModel] = None
        self._current_model_index: int = 0

        # 在注册表中查找默认模型的索引
        all_names = LLMRegistry.get_all_names()
        try:
            self._current_model_index = all_names.index(settings.DEFAULT_LLM_MODEL)
            self._llm = LLMRegistry.get(settings.DEFAULT_LLM_MODEL)
            logger.info(
                "llm_service_initialized",
                default_model=settings.DEFAULT_LLM_MODEL,
                model_index=self._current_model_index,
                total_models=len(all_names),
                environment=settings.ENVIRONMENT.value,
            )
        except (ValueError, Exception) as e:
            # 找不到默认模型，使用第一个模型
            self._current_model_index = 0
            self._llm = LLMRegistry.LLMS[0]["llm"]
            logger.warning(
                "default_model_not_found_using_first",
                requested=settings.DEFAULT_LLM_MODEL,
                using=all_names[0] if all_names else "none",
                error=str(e),
            )

    def _get_next_model_index(self) -> int:
        """获取下一个模型的索引（循环方式）。

        Returns:
            下一个模型的索引（到达末尾时回到 0）
        """
        total_models = len(LLMRegistry.LLMS)
        next_index = (self._current_model_index + 1) % total_models
        return next_index

    def _switch_to_next_model(self) -> bool:
        """切换到注册表中的下一个模型（循环方式）。

        Returns:
            切换成功返回 True，否则返回 False
        """
        try:
            next_index = self._get_next_model_index()
            next_model_entry = LLMRegistry.get_model_at_index(next_index)

            logger.warning(
                "switching_to_next_model",
                from_index=self._current_model_index,
                to_index=next_index,
                to_model=next_model_entry["name"],
            )

            self._current_model_index = next_index
            self._llm = next_model_entry["llm"]

            logger.info("model_switched", new_model=next_model_entry["name"], new_index=next_index)
            return True
        except Exception as e:
            logger.error("model_switch_failed", error=str(e))
            return False

    @retry(
        stop=stop_after_attempt(settings.MAX_LLM_CALL_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        before_sleep=before_sleep_log(logger, "WARNING"),
        reraise=True,
    )
    async def _call_llm_with_retry(self, messages: List[BaseMessage]) -> BaseMessage:
        """调用 LLM，带有自动重试逻辑。

        Args:
            messages: 发送给 LLM 的消息列表

        Returns:
            LLM 返回的 BaseMessage 响应

        Raises:
            OpenAIError: 如果所有重试都失败了
        """
        if not self._llm:
            raise RuntimeError("llm not initialized")

        try:
            response = await self._llm.ainvoke(messages)
            logger.debug("llm_call_successful", message_count=len(messages))
            return response
        except (RateLimitError, APITimeoutError, APIError) as e:
            logger.warning(
                "llm_call_failed_retrying",
                error_type=type(e).__name__,
                error=str(e),
                exc_info=True,
            )
            raise
        except OpenAIError as e:
            logger.error(
                "llm_call_failed",
                error_type=type(e).__name__,
                error=str(e),
            )
            raise

    async def call(
        self,
        messages: List[BaseMessage],
        model_name: Optional[str] = None,
        **model_kwargs,
    ) -> BaseMessage:
        """使用指定的消息调用 LLM，支持循环降级。

        Args:
            messages: 发送给 LLM 的消息列表
            model_name: 可选，指定使用的模型。如果为 None，则使用当前模型。
            **model_kwargs: 可选参数，用于覆盖默认模型配置

        Returns:
            LLM 返回的 BaseMessage 响应

        Raises:
            RuntimeError: 如果所有模型在重试后都失败了
        """
        # 如果用户指定了模型，从注册表中获取它
        if model_name:
            try:
                self._llm = LLMRegistry.get(model_name, **model_kwargs)
                # 更新索引以匹配请求的模型
                all_names = LLMRegistry.get_all_names()
                try:
                    self._current_model_index = all_names.index(model_name)
                except ValueError:
                    pass  # 如果模型名不在列表中，保持当前索引
                logger.info("using_requested_model", model_name=model_name, has_custom_kwargs=bool(model_kwargs))
            except ValueError as e:
                logger.error("requested_model_not_found", model_name=model_name, error=str(e))
                raise

        # 记录已尝试过的模型，防止无限循环
        total_models = len(LLMRegistry.LLMS)
        models_tried = 0
        starting_index = self._current_model_index
        last_error = None

        while models_tried < total_models:
            try:
                response = await self._call_llm_with_retry(messages)
                return response
            except OpenAIError as e:
                last_error = e
                models_tried += 1

                current_model_name = LLMRegistry.LLMS[self._current_model_index]["name"]
                logger.error(
                    "llm_call_failed_after_retries",
                    model=current_model_name,
                    models_tried=models_tried,
                    total_models=total_models,
                    error=str(e),
                )

                # 如果所有模型都试过了，放弃
                if models_tried >= total_models:
                    logger.error(
                        "all_models_failed",
                        models_tried=models_tried,
                        starting_model=LLMRegistry.LLMS[starting_index]["name"],
                    )
                    break

                # 循环切换到下一个模型
                if not self._switch_to_next_model():
                    logger.error("failed_to_switch_to_next_model")
                    break

                # 继续循环尝试下一个模型

        # 所有模型都失败了
        raise RuntimeError(
            f"failed to get response from llm after trying {models_tried} models. last error: {str(last_error)}"
        )

    def get_llm(self) -> Optional[BaseChatModel]:
        """获取当前的 LLM 实例。

        Returns:
            当前的 BaseChatModel 实例，如果未初始化则返回 None
        """
        return self._llm

    def bind_tools(self, tools: List) -> "LLMService":
        """将工具绑定到当前 LLM。

        Args:
            tools: 要绑定的工具列表

        Returns:
            返回自身，支持链式调用
        """
        if self._llm:
            self._llm = self._llm.bind_tools(tools)
            logger.debug("tools_bound_to_llm", tool_count=len(tools))
        return self


# 创建全局 LLM 服务实例
llm_service = LLMService()
