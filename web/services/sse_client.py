import json
from collections.abc import AsyncGenerator

import httpx

import config


async def stream_chat(messages: list[dict], session_token: str) -> AsyncGenerator[str, None]:
    """SSE 流式聊天，逐 token 生成内容"""
    url = f"{config.API_BASE_URL}/chatbot/chat/stream"
    headers = {
        "Authorization": f"Bearer {session_token}",
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
    }
    body = {"messages": messages}

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        async with client.stream("POST", url, json=body, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if data.get("done"):
                    return
                content = data.get("content", "")
                if content:
                    yield content
