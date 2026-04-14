"""多 Agent 相关的数据模型。"""

from typing import List

from pydantic import BaseModel, Field


class AgentInfo(BaseModel):
    """Agent 信息模型。"""

    key: str = Field(..., description="Agent 唯一标识", examples=["assistant"])
    description: str = Field(..., description="Agent 功能描述")


class ServiceMetadata(BaseModel):
    """服务元数据，包含可用 Agent 列表和默认配置。"""

    agents: List[AgentInfo] = Field(..., description="可用的 Agent 列表")
    default_agent: str = Field(..., description="默认 Agent 标识")
