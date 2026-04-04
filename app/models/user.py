"""这个文件包含应用的用户模型。"""

from typing import (
    TYPE_CHECKING,
    List,
)

import bcrypt
from sqlmodel import (
    Field,
    Relationship,
)

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.session import Session


class User(BaseModel, table=True):
    """用于存储用户账号的模型。

    属性:
        id: 主键
        email: 用户邮箱（唯一）
        hashed_password: 经过 bcrypt 加密的密码
        created_at: 用户创建时间
        sessions: 与用户聊天会话的关联关系
    """

    __table_args__ = {"comment": "用户表，存储用户账号和认证信息"}

    id: int = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"comment": "用户自增主键ID"},
    )
    email: str = Field(
        unique=True,
        index=True,
        sa_column_kwargs={"comment": "用户邮箱地址（唯一索引）"},
    )
    hashed_password: str = Field(
        sa_column_kwargs={"comment": "bcrypt加密后的密码哈希值"},
    )
    sessions: List["Session"] = Relationship(back_populates="user")

    def verify_password(self, password: str) -> bool:
        """验证提供的密码是否与存储的哈希值匹配。"""
        return bcrypt.checkpw(password.encode("utf-8"), self.hashed_password.encode("utf-8"))

    @staticmethod
    def hash_password(password: str) -> str:
        """使用 bcrypt 对密码进行哈希加密。"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


# 避免循环导入
from app.models.session import Session  # noqa: E402
