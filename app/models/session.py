"""这个文件包含应用的会话模型。"""

from typing import (
    TYPE_CHECKING,
    List,
)

from sqlmodel import (
    Field,
    Relationship,
)

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class Session(BaseModel, table=True):
    """用于存储聊天会话的模型。

    属性:
        id: 主键
        user_id: 关联用户的外键
        name: 会话名称（默认为空字符串）
        created_at: 会话创建时间
        messages: 与会话消息的关联关系
        user: 与会话所有者的关联关系
    """

    __table_args__ = {"comment": "聊天会话表，存储用户的对话会话信息"}

    id: str = Field(
        primary_key=True,
        sa_column_kwargs={"comment": "会话唯一标识（主键）"},
    )
    user_id: int = Field(
        foreign_key="user.id",
        sa_column_kwargs={"comment": "关联用户ID（外键 -> user.id）"},
    )
    name: str = Field(
        default="",
        sa_column_kwargs={"comment": "会话名称"},
    )
    user: "User" = Relationship(back_populates="sessions")
