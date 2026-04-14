"""长期记忆管理 Mixin，基于 mem0ai 实现语义记忆的存储与检索。"""

from typing import Optional

from mem0 import AsyncMemory

from app.infrastructure.config import settings
from app.infrastructure.logging import logger


class MemoryMixin:
    """为 LangGraphAgent 提供长期记忆管理能力。

    依赖主类初始化 self.memory 属性。
    """

    memory: Optional[AsyncMemory]

    @staticmethod
    def _build_mem0_provider_config(model: str) -> dict:
        """构建 mem0ai 的 provider 配置，统一走 OpenAI 兼容协议。"""
        config: dict = {"provider": "openai", "config": {"model": model}}
        if settings.OPENAI_BASE_URL:
            config["config"]["openai_base_url"] = settings.OPENAI_BASE_URL
        return config

    async def _long_term_memory(self) -> AsyncMemory:
        """初始化长期记忆。"""
        if self.memory is None:
            self.memory = await AsyncMemory.from_config(
                config_dict={
                    "vector_store": {
                        "provider": "pgvector",
                        "config": {
                            "collection_name": settings.LONG_TERM_MEMORY_COLLECTION_NAME,
                            "embedding_model_dims": settings.LONG_TERM_MEMORY_EMBEDDING_DIMS,
                            "dbname": settings.POSTGRES_DB,
                            "user": settings.POSTGRES_USER,
                            "password": settings.POSTGRES_PASSWORD,
                            "host": settings.POSTGRES_HOST,
                            "port": settings.POSTGRES_PORT,
                        },
                    },
                    "llm": self._build_mem0_provider_config(settings.LONG_TERM_MEMORY_MODEL),
                    "embedder": self._build_mem0_provider_config(settings.LONG_TERM_MEMORY_EMBEDDER_MODEL),
                }
            )
        return self.memory

    async def _get_relevant_memory(self, user_id: str, query: str) -> str:
        """获取与用户和查询相关的记忆。

        Args:
            user_id (str): 用户 ID。
            query (str): 要搜索的查询内容。

        Returns:
            str: 相关的记忆内容。
        """
        try:
            memory = await self._long_term_memory()
            results = await memory.search(user_id=str(user_id), query=query)
            logger.debug("memory_search_results", user_id=user_id, result_count=len(results.get("results", [])))
            return "\n".join([f"* {result['memory']}" for result in results["results"]])
        except Exception as e:
            logger.error("failed_to_get_relevant_memory", error=str(e), user_id=user_id, query=query)
            return ""

    async def _update_long_term_memory(self, user_id: str, messages: list[dict], metadata: dict = None) -> None:
        """更新长期记忆。

        Args:
            user_id (str): 用户 ID。
            messages (list[dict]): 用于更新长期记忆的消息列表。
            metadata (dict): 可选的元数据。
        """
        try:
            memory = await self._long_term_memory()
            await memory.add(messages, user_id=str(user_id), metadata=metadata)
            logger.info("long_term_memory_updated_successfully", user_id=user_id)
        except Exception as e:
            logger.exception(
                "failed_to_update_long_term_memory",
                user_id=user_id,
                error=str(e),
            )
