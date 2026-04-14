"""LangChain/LangGraph 自定义 Callback 中间件骨架。

与 Langfuse CallbackHandler 并列注入到 LangGraph config 的 callbacks 列表中，
用于结构化日志记录 LLM / Chain / Tool 的全生命周期事件。
"""

import time
from typing import Any, Optional
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from app.infrastructure.logging import logger


class AgentCallbackHandler(AsyncCallbackHandler):
    """LangChain/LangGraph 通用 callback 中间件骨架。

    每个 hook 使用 structlog 记录结构化日志，方便后续按需扩展业务逻辑。
    """

    def __init__(self) -> None:
        super().__init__()
        self._timers: dict[UUID, float] = {}

    def _start_timer(self, run_id: UUID) -> None:
        self._timers[run_id] = time.perf_counter()

    def _elapsed_ms(self, run_id: UUID) -> Optional[float]:
        start = self._timers.pop(run_id, None)
        if start is None:
            return None
        return round((time.perf_counter() - start) * 1000, 2)

    # ── LLM 生命周期 ──────────────────────────────────────────

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        self._start_timer(run_id)
        logger.debug(
            "llm_start",
            run_id=str(run_id),
            parent_run_id=str(parent_run_id) if parent_run_id else None,
            model=serialized.get("kwargs", {}).get("model_name"),
            prompt_count=len(prompts),
        )

    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        elapsed = self._elapsed_ms(run_id)
        token_usage = (response.llm_output or {}).get("token_usage", {}) if response.llm_output else {}
        logger.info(
            "llm_end",
            run_id=str(run_id),
            parent_run_id=str(parent_run_id) if parent_run_id else None,
            elapsed_ms=elapsed,
            total_tokens=token_usage.get("total_tokens"),
            prompt_tokens=token_usage.get("prompt_tokens"),
            completion_tokens=token_usage.get("completion_tokens"),
        )

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        elapsed = self._elapsed_ms(run_id)
        logger.exception(
            "llm_error",
            run_id=str(run_id),
            parent_run_id=str(parent_run_id) if parent_run_id else None,
            elapsed_ms=elapsed,
            error=str(error),
        )

    async def on_llm_new_token(
        self,
        token: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        pass

    # ── Chain / Node 生命周期 ─────────────────────────────────

    async def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        self._start_timer(run_id)
        node_name = (kwargs.get("metadata") or {}).get("langgraph_node")
        logger.debug(
            "chain_start",
            run_id=str(run_id),
            parent_run_id=str(parent_run_id) if parent_run_id else None,
            node=node_name,
            chain_name=serialized.get("name"),
        )

    async def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        elapsed = self._elapsed_ms(run_id)
        node_name = (kwargs.get("metadata") or {}).get("langgraph_node")
        logger.info(
            "chain_end",
            run_id=str(run_id),
            parent_run_id=str(parent_run_id) if parent_run_id else None,
            node=node_name,
            elapsed_ms=elapsed,
        )

    async def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        elapsed = self._elapsed_ms(run_id)
        node_name = (kwargs.get("metadata") or {}).get("langgraph_node")
        logger.exception(
            "chain_error",
            run_id=str(run_id),
            parent_run_id=str(parent_run_id) if parent_run_id else None,
            node=node_name,
            elapsed_ms=elapsed,
            error=str(error),
        )

    # ── 工具生命周期 ──────────────────────────────────────────

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        self._start_timer(run_id)
        logger.info(
            "tool_start",
            run_id=str(run_id),
            parent_run_id=str(parent_run_id) if parent_run_id else None,
            tool_name=serialized.get("name"),
        )

    async def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        elapsed = self._elapsed_ms(run_id)
        logger.info(
            "tool_end",
            run_id=str(run_id),
            parent_run_id=str(parent_run_id) if parent_run_id else None,
            elapsed_ms=elapsed,
        )

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        elapsed = self._elapsed_ms(run_id)
        logger.exception(
            "tool_error",
            run_id=str(run_id),
            parent_run_id=str(parent_run_id) if parent_run_id else None,
            elapsed_ms=elapsed,
            error=str(error),
        )

    # ── 重试 ─────────────────────────────────────────────────

    async def on_retry(
        self,
        retry_state: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        logger.warning(
            "callback_retry",
            run_id=str(run_id),
            parent_run_id=str(parent_run_id) if parent_run_id else None,
            attempt=getattr(retry_state, "attempt_number", None),
        )
