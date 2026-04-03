"""这个文件包含应用的聊天数据模式。"""

import re
from typing import (
    List,
    Literal,
)

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


class Message(BaseModel):
    """聊天接口的消息模型。

    属性:
        role: 消息发送者的角色（用户或助手）。
        content: 消息内容。
    """

    model_config = {"extra": "ignore"}

    role: Literal["user", "assistant", "system"] = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The content of the message", min_length=1, max_length=3000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """校验消息内容。

        参数:
            v: 待校验的内容

        返回:
            str: 校验通过的内容

        异常:
            ValueError: 内容包含不允许的模式时抛出
        """
        # 检查可能有害的内容
        if re.search(r"<script.*?>.*?</script>", v, re.IGNORECASE | re.DOTALL):
            raise ValueError("Content contains potentially harmful script tags")

        # 检查空字节
        if "\0" in v:
            raise ValueError("Content contains null bytes")

        return v


class ChatRequest(BaseModel):
    """聊天接口的请求模型。

    属性:
        messages: 对话中的消息列表。
    """

    messages: List[Message] = Field(
        ...,
        description="List of messages in the conversation",
        min_length=1,
    )


class ChatResponse(BaseModel):
    """聊天接口的响应模型。

    属性:
        messages: 对话中的消息列表。
    """

    messages: List[Message] = Field(..., description="List of messages in the conversation")


class StreamResponse(BaseModel):
    """流式聊天接口的响应模型。

    属性:
        content: 当前数据块的内容。
        done: 流式传输是否已完成。
    """

    content: str = Field(default="", description="The content of the current chunk")
    done: bool = Field(default=False, description="Whether the stream is complete")
