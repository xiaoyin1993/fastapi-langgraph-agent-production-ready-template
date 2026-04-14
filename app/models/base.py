"""所有模型的基类和公共导入。"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 声明式基类。"""

    pass


class BaseModel(Base):
    """包含公共字段的抽象基础模型。"""

    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        comment="记录创建时间（UTC）",
    )
