"""API v1 路由配置。

这个模块负责设置主路由，并把认证、聊天机器人等各个子路由挂载进来。
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.chatbot import router as chatbot_router
from app.infrastructure.logging import logger

api_router = APIRouter()

# 挂载子路由
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(chatbot_router, prefix="/chatbot", tags=["chatbot"])


@api_router.get("/health")
async def health_check():
    """健康检查接口。

    Returns:
        dict: 健康状态信息。
    """
    logger.info("health_check_called")
    return {"status": "healthy", "version": "1.0.0"}
