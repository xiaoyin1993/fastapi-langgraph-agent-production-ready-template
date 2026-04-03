"""应用的限流配置。

这个模块使用 slowapi 配置限流功能，默认限流规则在应用配置中定义。
限流基于客户端的远程 IP 地址。
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.infrastructure.config import settings

# 初始化限流器
limiter = Limiter(key_func=get_remote_address, default_limits=settings.RATE_LIMIT_DEFAULT)
