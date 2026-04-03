"""这个文件包含了应用的图相关工具函数。"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.messages import trim_messages as _trim_messages

from app.infrastructure.config import settings
from app.infrastructure.logging import logger
from app.schemas import Message


def dump_messages(messages: list[Message]) -> list[dict]:
    """将消息列表转换为字典列表。

    Args:
        messages (list[Message]): 要转换的消息列表。

    Returns:
        list[dict]: 转换后的字典列表。
    """
    return [message.model_dump() for message in messages]


def process_llm_response(response: BaseMessage) -> BaseMessage:
    """处理 LLM 响应，解析结构化的内容块（比如 GPT-5 模型返回的格式）。

    GPT-5 模型会返回一个内容块列表，格式如下：
    [
        {'id': '...', 'summary': [], 'type': 'reasoning'},
        {'type': 'text', 'text': '实际的回复内容'}
    ]

    这个函数从这些结构中提取出真正的文本内容。

    Args:
        response: LLM 返回的原始响应

    Returns:
        处理后的 BaseMessage，内容已被提取
    """
    if isinstance(response.content, list):
        # 从内容块中提取文本
        text_parts = []
        for block in response.content:
            if isinstance(block, dict):
                # 处理文本块
                if block.get("type") == "text" and "text" in block:
                    text_parts.append(block["text"])
                # 记录推理块的调试信息
                elif block.get("type") == "reasoning":
                    logger.debug(
                        "reasoning_block_received",
                        reasoning_id=block.get("id"),
                        has_summary=bool(block.get("summary")),
                    )
            elif isinstance(block, str):
                text_parts.append(block)

        # 拼接所有文本部分
        response.content = "".join(text_parts)
        logger.debug(
            "processed_structured_content",
            block_count=len(response.content) if isinstance(response.content, list) else 1,
            extracted_length=len(response.content) if isinstance(response.content, str) else 0,
        )

    return response


def prepare_messages(messages: list[Message], llm: BaseChatModel, system_prompt: str) -> list[Message]:
    """为 LLM 准备消息列表。

    Args:
        messages (list[Message]): 要准备的消息列表。
        llm (BaseChatModel): 使用的 LLM 模型。
        system_prompt (str): 系统提示词。

    Returns:
        list[Message]: 准备好的消息列表。
    """
    try:
        trimmed_messages = _trim_messages(
            dump_messages(messages),
            strategy="last",
            token_counter=llm,
            max_tokens=settings.MAX_TOKENS,
            start_on="human",
            include_system=False,
            allow_partial=False,
        )
    except (ValueError, NotImplementedError) as e:
        logger.warning(
            "token_counting_failed_skipping_trim",
            error=str(e),
            message_count=len(messages),
        )
        trimmed_messages = dump_messages(messages)

    return [{"role": "system", "content": system_prompt}] + trimmed_messages
