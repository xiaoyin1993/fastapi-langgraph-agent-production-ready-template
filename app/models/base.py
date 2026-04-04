"""所有模型的基类和公共导入。"""

from datetime import datetime, UTC

from sqlmodel import Field, SQLModel


class BaseModel(SQLModel):
    """包含公共字段的基础模型。"""

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={"comment": "记录创建时间（UTC）"},
    )
