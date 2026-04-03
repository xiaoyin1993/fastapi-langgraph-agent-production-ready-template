"""自定义中间件，用于跟踪指标和处理其他横切关注点。"""

import time
from typing import Callable

from fastapi import Request
from jose import (
    JWTError,
    jwt,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.infrastructure.config import settings
from app.infrastructure.logging import (
    bind_context,
    clear_context,
)
from app.infrastructure.metrics import (
    db_connections,
    http_request_duration_seconds,
    http_requests_total,
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """用于跟踪 HTTP 请求指标的中间件。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """跟踪每个请求的指标。

        Args:
            request: 传入的请求
            call_next: 下一个中间件或路由处理器

        Returns:
            Response: 应用返回的响应
        """
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.time() - start_time

            # 记录指标
            http_requests_total.labels(method=request.method, endpoint=request.url.path, status=status_code).inc()

            http_request_duration_seconds.labels(method=request.method, endpoint=request.url.path).observe(duration)

        return response


class LoggingContextMiddleware(BaseHTTPMiddleware):
    """用于将 user_id 和 session_id 添加到日志上下文的中间件。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """从已认证的请求中提取 user_id 和 session_id，并添加到日志上下文。

        Args:
            request: 传入的请求
            call_next: 下一个中间件或路由处理器

        Returns:
            Response: 应用返回的响应
        """
        try:
            # 清除上一个请求遗留的上下文
            clear_context()

            # 从 Authorization 请求头中提取 token
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

                try:
                    # 解码 token 获取 session_id（存储在 "sub" 字段中）
                    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
                    session_id = payload.get("sub")

                    if session_id:
                        # 将 session_id 绑定到日志上下文
                        bind_context(session_id=session_id)

                        # 尝试从请求状态中获取 user_id
                        # 如果端点使用了认证，user_id 会通过依赖注入设置
                        # 我们会在请求处理完成后检查

                except JWTError:
                    # token 无效，但不要让请求失败——交给认证依赖去处理
                    pass

            # 处理请求
            response = await call_next(request)

            # 请求处理完成后，检查是否有用户信息添加到请求状态中
            if hasattr(request.state, "user_id"):
                bind_context(user_id=request.state.user_id)

            return response

        finally:
            # 请求完成后务必清除上下文，避免泄漏到其他请求
            clear_context()
