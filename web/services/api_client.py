import httpx

import config


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class AuthenticationError(ApiError):
    pass


class ApiClient:
    def __init__(self):
        self.base_url = config.API_BASE_URL
        self.timeout = httpx.Timeout(30.0)

    def _headers(self, token: str | None = None) -> dict:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _handle_response(self, response: httpx.Response) -> dict:
        if response.status_code == 401:
            raise AuthenticationError(401, "Authentication failed")
        if response.status_code >= 400:
            try:
                data = response.json()
                detail = data.get("detail", response.text)
            except Exception:
                detail = response.text
            raise ApiError(response.status_code, str(detail))
        if response.status_code == 204 or not response.text:
            return {}
        return response.json()

    # ==================== Auth ====================

    async def register(self, email: str, password: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/auth/register",
                json={"email": email, "password": password},
                headers=self._headers(),
            )
            return await self._handle_response(resp)

    async def login(self, email: str, password: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/auth/login",
                data={"username": email, "password": password, "grant_type": "password"},
                headers={"Accept": "application/json"},
            )
            return await self._handle_response(resp)

    # ==================== Sessions ====================

    async def create_session(self, user_token: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/auth/session",
                headers=self._headers(user_token),
            )
            return await self._handle_response(resp)

    async def list_sessions(self, user_token: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/auth/sessions",
                headers=self._headers(user_token),
            )
            return await self._handle_response(resp)

    async def rename_session(self, session_id: str, name: str, session_token: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.patch(
                f"{self.base_url}/auth/session/{session_id}/name",
                data={"name": name},
                headers=self._headers(session_token),
            )
            return await self._handle_response(resp)

    async def delete_session(self, session_id: str, session_token: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.delete(
                f"{self.base_url}/auth/session/{session_id}",
                headers=self._headers(session_token),
            )
            return await self._handle_response(resp)

    # ==================== Chat ====================

    async def send_message(self, messages: list[dict], session_token: str) -> dict:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            resp = await client.post(
                f"{self.base_url}/chatbot/chat",
                json={"messages": messages},
                headers=self._headers(session_token),
            )
            return await self._handle_response(resp)

    async def get_messages(self, session_token: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                f"{self.base_url}/chatbot/messages",
                headers=self._headers(session_token),
            )
            return await self._handle_response(resp)

    async def clear_messages(self, session_token: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.delete(
                f"{self.base_url}/chatbot/messages",
                headers=self._headers(session_token),
            )
            return await self._handle_response(resp)


api_client = ApiClient()
