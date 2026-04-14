"""这个文件包含应用的对话线程模型。"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Thread(Base):
    """用于存储对话线程的模型。

    属性:
        id: 主键
        created_at: 线程创建时间
    """

    __tablename__ = "thread"
    __table_args__ = {"comment": "对话线程表，存储聊天对话线程信息"}

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        comment="线程唯一标识（主键）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        comment="线程创建时间（UTC）",
    )
