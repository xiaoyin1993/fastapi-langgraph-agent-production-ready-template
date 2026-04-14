"""聊天机器人 API 接口，用于处理聊天交互。

这个模块提供了聊天交互的接口，包括普通聊天、流式聊天、消息历史管理和清除聊天记录。
支持多 Agent 路由：通过 agent_id 参数选择不同的 Agent。
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
from app.core.graph.manager import agent_manager
from app.core.graph.registry import DEFAULT_AGENT, get_all_agents_info
from app.infrastructure.limiter import limiter
from app.infrastructure.logging import logger
from app.infrastructure.metrics import llm_stream_duration_seconds
from app.models.session import Session
from app.schemas.agent import AgentInfo, ServiceMetadata
from app.services.database import DatabaseService
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    Message,
    StreamResponse,
)

router = APIRouter()
db_service = DatabaseService()


@router.get("/agents", response_model=ServiceMetadata)
async def list_agents():
    """获取所有可用 Agent 的信息。

    Returns:
        ServiceMetadata: 可用 Agent 列表及默认 Agent。
    """
    return ServiceMetadata(
        agents=get_all_agents_info(),
        default_agent=DEFAULT_AGENT,
    )


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def chat(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """使用默认 Agent 处理聊天请求。"""
    return await _handle_chat(DEFAULT_AGENT, chat_request, session)


@router.post("/{agent_id}/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def chat_with_agent(
    request: Request,
    agent_id: str,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """使用指定 Agent 处理聊天请求。

    Args:
        request: FastAPI 请求对象。
        agent_id: Agent 标识。
        chat_request: 聊天请求。
        session: 当前会话。

    Returns:
        ChatResponse: 聊天响应。
    """
    return await _handle_chat(agent_id, chat_request, session)


@router.post("/chat/stream")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat_stream"][0])
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """使用默认 Agent 处理流式聊天请求。"""
    return await _handle_stream(DEFAULT_AGENT, chat_request, session)


@router.post("/{agent_id}/chat/stream")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat_stream"][0])
async def chat_stream_with_agent(
    request: Request,
    agent_id: str,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
):
    """使用指定 Agent 处理流式聊天请求。"""
    return await _handle_stream(agent_id, chat_request, session)


@router.get("/messages", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["messages"][0])
async def get_session_messages(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """获取某个会话的所有消息。"""
    try:
        messages = await agent_manager.get_chat_history(DEFAULT_AGENT, session.id)
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
    """清除某个会话的所有消息。"""
    try:
        await agent_manager.clear_chat_history(session.id)
        return {"message": "Chat history cleared successfully"}
    except Exception as e:
        logger.error("clear_chat_history_failed", session_id=session.id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_chat(agent_id: str, chat_request: ChatRequest, session: Session) -> ChatResponse:
    """通用聊天处理逻辑。"""
    try:
        logger.info(
            "chat_request_received",
            agent_id=agent_id,
            session_id=session.id,
            message_count=len(chat_request.messages),
        )

        user = await db_service.get_user(session.user_id)
        username = user.email if user else None
        result = await agent_manager.get_response(
            agent_id, chat_request.messages, session.id, user_id=session.user_id, username=username
        )

        logger.info("chat_request_processed", agent_id=agent_id, session_id=session.id)
        return ChatResponse(messages=result)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    except Exception as e:
        logger.error("chat_request_failed", agent_id=agent_id, session_id=session.id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_stream(agent_id: str, chat_request: ChatRequest, session: Session) -> StreamingResponse:
    """通用流式聊天处理逻辑。"""
    try:
        logger.info(
            "stream_chat_request_received",
            agent_id=agent_id,
            session_id=session.id,
            message_count=len(chat_request.messages),
        )

        user = await db_service.get_user(session.user_id)
        username = user.email if user else None

        async def event_generator():
            try:
                full_response = ""
                async for chunk in agent_manager.get_stream_response(
                    agent_id, chat_request.messages, session.id, user_id=session.user_id, username=username
                ):
                    full_response += chunk
                    response = StreamResponse(content=chunk, done=False)
                    yield f"data: {json.dumps(response.model_dump())}\n\n"
                # 循环外结束标识
                final_response = StreamResponse(content="", done=True)
                yield f"data: {json.dumps(final_response.model_dump())}\n\n"

            except Exception as e:
                logger.error(
                    "stream_chat_request_failed",
                    agent_id=agent_id,
                    session_id=session.id,
                    error=str(e),
                    exc_info=True,
                )
                error_response = StreamResponse(content=str(e), done=True)
                yield f"data: {json.dumps(error_response.model_dump())}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    except Exception as e:
        logger.error(
            "stream_chat_request_failed",
            agent_id=agent_id,
            session_id=session.id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(e))
