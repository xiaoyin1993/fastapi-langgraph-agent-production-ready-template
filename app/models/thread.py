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

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
