"""聊天机器人 API 接口，用于处理聊天交互。

这个模块提供了聊天交互的接口，包括普通聊天、流式聊天、消息历史管理和清除聊天记录。
"""

import json
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import StreamingResponse

from app.api.v1.auth import get_current_session
from app.infrastructure.config import settings
from app.core.graph import LangGraphAgent
from app.infrastructure.limiter import limiter
from app.infrastructure.logging import logger
from app.infrastructure.metrics import llm_stream_duration_seconds
from app.models.session import Session
from app.services.database import DatabaseService
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    Message,
    StreamResponse,
)

router = APIRouter()
agent = LangGraphAgent()
db_service = DatabaseService()


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def chat(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """使用 LangGraph 处理聊天请求。

    Args:
        request: FastAPI 请求对象，用于限流。
        chat_request: 包含消息的聊天请求。
        session: 从认证令牌中获取的当前会话。

    Returns:
        ChatResponse: 处理后的聊天响应。

    Raises:
        HTTPException: 处理请求出错时抛出。
    """
    try:
        logger.info(
            "chat_request_received",
            session_id=session.id,
            message_count=len(chat_request.messages),
        )

        user = await db_service.get_user(session.user_id)
        username = user.email if user else None
        result = await agent.get_response(chat_request.messages, session.id, user_id=session.user_id, username=username)

        logger.info("chat_request_processed", session_id=session.id)

        return ChatResponse(messages=result)
    except Exception as e:
        logger.error("chat_request_failed", session_id=session.id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat_stream"][0])
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """使用 LangGraph 处理聊天请求，返回流式响应。

    Args:
        request: FastAPI 请求对象，用于限流。
        chat_request: 包含消息的聊天请求。
        session: 从认证令牌中获取的当前会话。

    Returns:
        StreamingResponse: 聊天补全的流式响应。

    Raises:
        HTTPException: 处理请求出错时抛出。
    """
    try:
        logger.info(
            "stream_chat_request_received",
            session_id=session.id,
            message_count=len(chat_request.messages),
        )

        user = await db_service.get_user(session.user_id)
        username = user.email if user else None

        async def event_generator():
            """生成流式事件。

            Yields:
                str: JSON 格式的服务端推送事件。

            Raises:
                Exception: 流式传输过程中出错时抛出。
            """
            try:
                full_response = ""
                with llm_stream_duration_seconds.labels(model=agent.llm_service.get_llm().get_name()).time():
                    async for chunk in agent.get_stream_response(
                        chat_request.messages, session.id, user_id=session.user_id, username=username
                    ):
                        full_response += chunk
                        response = StreamResponse(content=chunk, done=False)
                        yield f"data: {json.dumps(response.model_dump())}\n\n"

                # 发送表示完成的最终消息
                final_response = StreamResponse(content="", done=True)
                yield f"data: {json.dumps(final_response.model_dump())}\n\n"

            except Exception as e:
                logger.error(
                    "stream_chat_request_failed",
                    session_id=session.id,
                    error=str(e),
                    exc_info=True,
                )
                error_response = StreamResponse(content=str(e), done=True)
                yield f"data: {json.dumps(error_response.model_dump())}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(
            "stream_chat_request_failed",
            session_id=session.id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/messages", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["messages"][0])
async def get_session_messages(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """获取某个会话的所有消息。

    Args:
        request: FastAPI 请求对象，用于限流。
        session: 从认证令牌中获取的当前会话。

    Returns:
        ChatResponse: 该会话中的所有消息。

    Raises:
        HTTPException: 获取消息出错时抛出。
    """
    try:
        messages = await agent.get_chat_history(session.id)
        return ChatResponse(messages=messages)
    except Exception as e:
        logger.error("get_messages_failed", session_id=session.id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/messages")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["messages"][0])
async def clear_chat_history(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """清除某个会话的所有消息。

    Args:
        request: FastAPI 请求对象，用于限流。
        session: 从认证令牌中获取的当前会话。

    Returns:
        dict: 表示聊天记录已清除的提示信息。
    """
    try:
        await agent.clear_chat_history(session.id)
        return {"message": "Chat history cleared successfully"}
    except Exception as e:
        logger.error("clear_chat_history_failed", session_id=session.id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
