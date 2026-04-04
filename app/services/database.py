"""这个文件包含了应用的数据库服务。"""

from typing import (
    List,
    Optional,
)

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import (
    SQLModel,
    select,
)
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infrastructure.config import (
    Environment,
    settings,
)
from app.infrastructure.logging import logger
from app.models.session import Session as ChatSession
from app.models.user import User


class DatabaseService:
    """数据库操作的服务类。

    这个类负责处理用户、会话和消息相关的所有数据库操作。
    它使用 SQLModel 进行 ORM 操作，并维护一个异步数据库连接池。
    """

    def __init__(self):
        """初始化数据库服务，设置异步连接池。"""
        try:
            # 根据不同环境配置数据库连接池参数
            pool_size = settings.POSTGRES_POOL_SIZE
            max_overflow = settings.POSTGRES_MAX_OVERFLOW

            # 使用 psycopg3 异步驱动
            connection_url = (
                f"postgresql+psycopg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
                f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
            )

            self.engine = create_async_engine(
                connection_url,
                pool_pre_ping=True,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=30,  # 连接超时时间（秒）
                pool_recycle=1800,  # 每 30 分钟回收一次连接
            )

            logger.info(
                "database_initialized",
                environment=settings.ENVIRONMENT.value,
                pool_size=pool_size,
                max_overflow=max_overflow,
            )
        except SQLAlchemyError as e:
            logger.error("database_initialization_error", error=str(e), environment=settings.ENVIRONMENT.value)
            # 生产环境下不抛异常，即使数据库有问题也让应用正常启动
            if settings.ENVIRONMENT != Environment.PRODUCTION:
                raise

    async def create_tables(self):
        """创建数据表（仅在表不存在时才创建）。"""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def create_user(self, email: str, password: str) -> User:
        """创建一个新用户。

        Args:
            email: 用户的邮箱地址
            password: 加密后的密码

        Returns:
            User: 创建好的用户对象
        """
        async with AsyncSession(self.engine) as session:
            user = User(email=email, hashed_password=password)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            logger.info("user_created", email=email)
            return user

    async def get_user(self, user_id: int) -> Optional[User]:
        """根据用户 ID 获取用户。

        Args:
            user_id: 要查询的用户 ID

        Returns:
            Optional[User]: 如果找到则返回用户对象，否则返回 None
        """
        async with AsyncSession(self.engine) as session:
            user = await session.get(User, user_id)
            return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户。

        Args:
            email: 要查询的用户邮箱

        Returns:
            Optional[User]: 如果找到则返回用户对象，否则返回 None
        """
        async with AsyncSession(self.engine) as session:
            statement = select(User).where(User.email == email)
            result = await session.exec(statement)
            user = result.first()
            return user

    async def delete_user_by_email(self, email: str) -> bool:
        """根据邮箱删除用户。

        Args:
            email: 要删除的用户邮箱

        Returns:
            bool: 删除成功返回 True，用户不存在返回 False
        """
        async with AsyncSession(self.engine) as session:
            result = await session.exec(select(User).where(User.email == email))
            user = result.first()
            if not user:
                return False

            await session.delete(user)
            await session.commit()
            logger.info("user_deleted", email=email)
            return True

    async def create_session(self, session_id: str, user_id: int, name: str = "") -> ChatSession:
        """创建一个新的聊天会话。

        Args:
            session_id: 新会话的 ID
            user_id: 会话所属用户的 ID
            name: 会话名称，可选（默认为空字符串）

        Returns:
            ChatSession: 创建好的会话对象
        """
        async with AsyncSession(self.engine) as session:
            chat_session = ChatSession(id=session_id, user_id=user_id, name=name)
            session.add(chat_session)
            await session.commit()
            await session.refresh(chat_session)
            logger.info("session_created", session_id=session_id, user_id=user_id, name=name)
            return chat_session

    async def delete_session(self, session_id: str) -> bool:
        """根据 ID 删除会话。

        Args:
            session_id: 要删除的会话 ID

        Returns:
            bool: 删除成功返回 True，会话不存在返回 False
        """
        async with AsyncSession(self.engine) as session:
            chat_session = await session.get(ChatSession, session_id)
            if not chat_session:
                return False

            await session.delete(chat_session)
            await session.commit()
            logger.info("session_deleted", session_id=session_id)
            return True

    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """根据 ID 获取会话。

        Args:
            session_id: 要查询的会话 ID

        Returns:
            Optional[ChatSession]: 如果找到则返回会话对象，否则返回 None
        """
        async with AsyncSession(self.engine) as session:
            chat_session = await session.get(ChatSession, session_id)
            return chat_session

    async def get_user_sessions(self, user_id: int) -> List[ChatSession]:
        """获取某个用户的所有会话。

        Args:
            user_id: 用户 ID

        Returns:
            List[ChatSession]: 该用户的会话列表
        """
        async with AsyncSession(self.engine) as session:
            statement = select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.created_at)
            result = await session.exec(statement)
            sessions = result.all()
            return sessions

    async def update_session_name(self, session_id: str, name: str) -> ChatSession:
        """更新会话名称。

        Args:
            session_id: 要更新的会话 ID
            name: 新的会话名称

        Returns:
            ChatSession: 更新后的会话对象

        Raises:
            HTTPException: 如果会话不存在则抛出异常
        """
        async with AsyncSession(self.engine) as session:
            chat_session = await session.get(ChatSession, session_id)
            if not chat_session:
                raise HTTPException(status_code=404, detail="Session not found")

            chat_session.name = name
            session.add(chat_session)
            await session.commit()
            await session.refresh(chat_session)
            logger.info("session_name_updated", session_id=session_id, name=name)
            return chat_session

    async def health_check(self) -> bool:
        """检查数据库连接是否正常。

        Returns:
            bool: 数据库正常返回 True，否则返回 False
        """
        try:
            async with AsyncSession(self.engine) as session:
                await session.exec(select(1))
                return True
        except Exception as e:
            logger.error("database_health_check_failed", error=str(e))
            return False


# 创建单例实例
database_service = DatabaseService()
