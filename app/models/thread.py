"""这个文件包含应用的对话线程模型。"""

from datetime import (
    UTC,
    datetime,
)

from sqlmodel import (
    Field,
    SQLModel,
)


class Thread(SQLModel, table=True):
    """用于存储对话线程的模型。

    属性:
        id: 主键
        created_at: 线程创建时间
        messages: 与该线程中消息的关联关系
    """

    __table_args__ = {"comment": "对话线程表，存储聊天对话线程信息"}

    id: str = Field(
        primary_key=True,
        sa_column_kwargs={"comment": "线程唯一标识（主键）"},
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={"comment": "线程创建时间（UTC）"},
    )
