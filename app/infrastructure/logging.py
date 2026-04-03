"""应用的日志配置和初始化。

这个模块使用 structlog 提供结构化的日志配置，
支持根据不同环境使用不同的格式化器和处理器。
开发环境使用友好的控制台输出，生产环境使用 JSON 格式日志。
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

import structlog

from app.infrastructure.config import (
    Environment,
    settings,
)

# 确保日志目录存在
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

# 用于存储请求级别数据的上下文变量
_request_context: ContextVar[Dict[str, Any]] = ContextVar("request_context", default={})


def bind_context(**kwargs: Any) -> None:
    """将上下文变量绑定到当前请求。

    Args:
        **kwargs: 要绑定到日志上下文的键值对
    """
    current = _request_context.get()
    _request_context.set({**current, **kwargs})


def clear_context() -> None:
    """清除当前请求的所有上下文变量。"""
    _request_context.set({})


def get_context() -> Dict[str, Any]:
    """获取当前的日志上下文。

    Returns:
        Dict[str, Any]: 当前的上下文字典
    """
    return _request_context.get()


def add_context_to_event_dict(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """将上下文变量添加到事件字典中。

    这个处理器会把已绑定的上下文变量添加到每条日志事件里。

    Args:
        logger: 日志实例
        method_name: 日志方法的名称
        event_dict: 要修改的事件字典

    Returns:
        Dict[str, Any]: 添加了上下文变量的事件字典
    """
    context = get_context()
    if context:
        event_dict.update(context)
    return event_dict


def get_log_file_path() -> Path:
    """根据日期和环境获取当前日志文件路径。

    Returns:
        Path: 日志文件的路径
    """
    env_prefix = settings.ENVIRONMENT.value
    return settings.LOG_DIR / f"{env_prefix}-{datetime.now().strftime('%Y-%m-%d')}.jsonl"


class JsonlFileHandler(logging.Handler):
    """自定义处理器，用于将 JSONL 格式日志写入按天分割的文件。"""

    def __init__(self, file_path: Path):
        """初始化 JSONL 文件处理器。

        Args:
            file_path: 日志文件的写入路径。
        """
        super().__init__()
        self.file_path = file_path

    def emit(self, record: logging.LogRecord) -> None:
        """将一条日志记录写入 JSONL 文件。"""
        try:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "filename": record.pathname,
                "line": record.lineno,
                "environment": settings.ENVIRONMENT.value,
            }
            if hasattr(record, "extra"):
                log_entry.update(record.extra)

            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        """关闭处理器。"""
        super().close()


def get_structlog_processors(include_file_info: bool = True) -> List[Any]:
    """根据配置获取 structlog 的处理器列表。

    Args:
        include_file_info: 是否在日志中包含文件信息

    Returns:
        List[Any]: structlog 处理器列表
    """
    # 设置两种输出方式共用的处理器
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        # 将上下文变量（user_id、session_id 等）添加到所有日志事件中
        add_context_to_event_dict,
    ]

    # 如果需要文件信息，添加调用位置参数
    if include_file_info:
        processors.append(
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                    structlog.processors.CallsiteParameter.MODULE,
                    structlog.processors.CallsiteParameter.PATHNAME,
                }
            )
        )

    # 添加环境信息
    processors.append(lambda _, __, event_dict: {**event_dict, "environment": settings.ENVIRONMENT.value})

    return processors


def setup_logging() -> None:
    """根据环境配置 structlog 的不同格式化器。

    开发环境：美观的控制台输出
    预发布/生产环境：结构化 JSON 日志
    """
    # 根据 DEBUG 设置确定日志级别
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    
    # 创建 JSON 日志的文件处理器
    file_handler = JsonlFileHandler(get_log_file_path())
    file_handler.setLevel(log_level)

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # 获取共用的处理器
    shared_processors = get_structlog_processors(
        # 只在开发和测试环境中包含详细的文件信息
        include_file_info=settings.ENVIRONMENT
        in [Environment.DEVELOPMENT, Environment.TEST]
    )

    # 配置标准日志
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=[file_handler, console_handler],
    )

    # 根据环境配置 structlog
    if settings.LOG_FORMAT == "console":
        # 开发环境友好的控制台日志
        structlog.configure(
            processors=[
                *shared_processors,
                # 使用 ConsoleRenderer 美化控制台输出
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # 生产环境 JSON 日志
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )


# 初始化日志
setup_logging()

# 创建日志实例
logger = structlog.get_logger()
log_level_name = "DEBUG" if settings.DEBUG else "INFO"
logger.info(
    "logging_initialized",
    environment=settings.ENVIRONMENT.value,
    log_level=log_level_name,
    log_format=settings.LOG_FORMAT,
    debug=settings.DEBUG,
)
