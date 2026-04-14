"""AgentClient SDK — 与 Agent 服务交互的同步/异步客户端。

支持 JWT 认证，可选择不同 Agent，提供 invoke/stream 两种交互方式。
"""

import json
from typing import (
    Any,
    AsyncGenerator,
    Generator,
    Optional,
)

import httpx

from app.schemas.agent import AgentInfo, ServiceMetadata
from app.schemas.chat import ChatResponse, Message, StreamResponse


class AgentClientError(Exception):
    """AgentClient 异常。"""


class AgentClient:
    """与 Agent 服务交互的 HTTP 客户端。

    支持同步和异步的 invoke（完整回复）及 stream（流式回复）方法。
    使用 JWT session token 进行认证。
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_prefix: str = "/api/v1/chatbot",
        session_token: Optional[str] = None,
        agent: Optional[str] = None,
        timeout: float = 60.0,
    ):
        """初始化 AgentClient。

        Args:
            base_url: 服务地址。
            api_prefix: API 路径前缀。
            session_token: JWT session token（从 /auth/session 获取）。
            agent: 默认使用的 Agent ID（不指定则用服务端默认值）。
            timeout: 请求超时时间（秒）。
        """
        self.base_url = base_url.rstrip("/")
        self.api_prefix = api_prefix
        self.session_token = session_token
        self.agent = agent
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.session_token:
            headers["Authorization"] = f"Bearer {self.session_token}"
        return headers

    def _url(self, path: str) -> str:
        return f"{self.base_url}{self.api_prefix}{path}"

    def _agent_path(self, endpoint: str) -> str:
        if self.agent:
            return f"/{self.agent}{endpoint}"
        return endpoint

    # ── 同步方法 ──

    def get_agents(self) -> ServiceMetadata:
        """获取可用 Agent 列表。"""
        try:
            response = httpx.get(self._url("/agents"), headers=self._headers, timeout=self.timeout)
            response.raise_for_status()
            return ServiceMetadata.model_validate(response.json())
        except httpx.HTTPError as e:
            raise AgentClientError(f"Failed to get agents: {e}")

    def invoke(
        self,
        messages: list[dict[str, str]],
    ) -> ChatResponse:
        """同步调用 Agent，返回完整回复。

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]。

        Returns:
            ChatResponse: Agent 回复。
        """
        payload = {"messages": messages}
        try:
            response = httpx.post(
                self._url(self._agent_path("/chat")),
                json=payload,
                headers=self._headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return ChatResponse.model_validate(response.json())
        except httpx.HTTPError as e:
            raise AgentClientError(f"Invoke failed: {e}")

    def stream(
        self,
        messages: list[dict[str, str]],
    ) -> Generator[str, None, None]:
        """同步流式调用 Agent，逐 token 返回。

        Args:
            messages: 消息列表。

        Yields:
            str: LLM 回复的 token 片段。
        """
        payload = {"messages": messages}
        try:
            with httpx.stream(
                "POST",
                self._url(self._agent_path("/chat/stream")),
                json=payload,
                headers=self._headers,
                timeout=self.timeout,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    parsed = self._parse_sse_line(line)
                    if parsed is None:
                        break
                    if parsed:
                        yield parsed
        except httpx.HTTPError as e:
            raise AgentClientError(f"Stream failed: {e}")

    def get_history(self) -> ChatResponse:
        """获取当前会话的聊天历史。"""
        try:
            response = httpx.get(self._url("/messages"), headers=self._headers, timeout=self.timeout)
            response.raise_for_status()
            return ChatResponse.model_validate(response.json())
        except httpx.HTTPError as e:
            raise AgentClientError(f"Get history failed: {e}")

    # ── 异步方法 ──

    async def aget_agents(self) -> ServiceMetadata:
        """异步获取可用 Agent 列表。"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self._url("/agents"), headers=self._headers, timeout=self.timeout)
                response.raise_for_status()
                return ServiceMetadata.model_validate(response.json())
            except httpx.HTTPError as e:
                raise AgentClientError(f"Failed to get agents: {e}")

    async def ainvoke(
        self,
        messages: list[dict[str, str]],
    ) -> ChatResponse:
        """异步调用 Agent，返回完整回复。"""
        payload = {"messages": messages}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self._url(self._agent_path("/chat")),
                    json=payload,
                    headers=self._headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                return ChatResponse.model_validate(response.json())
            except httpx.HTTPError as e:
                raise AgentClientError(f"Invoke failed: {e}")

    async def astream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """异步流式调用 Agent，逐 token 返回。"""
        payload = {"messages": messages}
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream(
                    "POST",
                    self._url(self._agent_path("/chat/stream")),
                    json=payload,
                    headers=self._headers,
                    timeout=self.timeout,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        parsed = self._parse_sse_line(line)
                        if parsed is None:
                            break
                        if parsed:
                            yield parsed
            except httpx.HTTPError as e:
                raise AgentClientError(f"Stream failed: {e}")

    async def aget_history(self) -> ChatResponse:
        """异步获取当前会话的聊天历史。"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self._url("/messages"), headers=self._headers, timeout=self.timeout)
                response.raise_for_status()
                return ChatResponse.model_validate(response.json())
            except httpx.HTTPError as e:
                raise AgentClientError(f"Get history failed: {e}")

    # ── 辅助方法 ──

    @staticmethod
    def _parse_sse_line(line: str) -> Optional[str]:
        """解析 SSE 行，返回 token 内容或 None（表示结束）。"""
        line = line.strip()
        if not line or not line.startswith("data: "):
            return ""
        data = line[6:]
        if data == "[DONE]":
            return None
        try:
            parsed = json.loads(data)
            content = parsed.get("content", "")
            done = parsed.get("done", False)
            if done:
                return None
            return content
        except json.JSONDecodeError:
            return ""
