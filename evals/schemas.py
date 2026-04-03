"""评估模块的数据模型。"""

from pydantic import (
    BaseModel,
    Field,
)


class ScoreSchema(BaseModel):
    """评估评分的数据模型。"""

    score: float = Field(description="provide a score between 0 and 1")
    reasoning: str = Field(description="provide a one sentence reasoning")
