"""这个文件包含应用的会话模型。"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class Session(BaseModel):
    """用于存储聊天会话的模型。

    属性:
        id: 主键
        user_id: 关联用户的外键
        name: 会话名称（默认为空字符串）
        created_at: 会话创建时间
        user: 与会话所有者的关联关系
    """

    __tablename__ = "session"
    __table_args__ = {"comment": "聊天会话表，存储用户的对话会话信息"}

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        comment="会话唯一标识（主键）",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"),
        comment="关联用户ID（外键 -> user.id）",
    )
    name: Mapped[str] = mapped_column(
        String,
        default="",
        comment="会话名称",
    )
    user: Mapped["User"] = relationship(back_populates="sessions")
