"""LangGraph Store 集成，基于 AsyncPostgresStore 提供跨会话的结构化长期记忆。"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from urllib.parse import quote_plus

from langgraph.store.postgres import AsyncPostgresStore
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.infrastructure.config import settings
from app.infrastructure.logging import logger


@asynccontextmanager
async def get_postgres_store() -> AsyncGenerator[AsyncPostgresStore, None]:
    """创建并初始化 AsyncPostgresStore 实例。

    用于跨会话的结构化 KV 长期记忆（与 mem0ai 的语义记忆共存）。

    Yields:
        AsyncPostgresStore: 初始化完成的 Store 实例。
    """
    connection_url = (
        "postgresql://"
        f"{quote_plus(settings.POSTGRES_USER)}:{quote_plus(settings.POSTGRES_PASSWORD)}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )

    async with AsyncConnectionPool(
        connection_url,
        min_size=1,
        max_size=settings.POSTGRES_POOL_SIZE,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
        },
    ) as pool:
        try:
            store = AsyncPostgresStore(pool)
            await store.setup()
            logger.info("postgres_store_initialized")
            yield store
        finally:
            await pool.close()
