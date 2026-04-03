from nicegui import app


class AuthState:
    """基于 app.storage.user 的认证状态管理（双 token：user + session）"""

    @staticmethod
    def _storage() -> dict:
        return app.storage.user

    @staticmethod
    def is_logged_in() -> bool:
        return bool(app.storage.user.get("user_token"))

    @staticmethod
    def has_session() -> bool:
        return bool(app.storage.user.get("session_token"))

    @staticmethod
    def get_user_token() -> str | None:
        return app.storage.user.get("user_token")

    @staticmethod
    def get_user_email() -> str | None:
        return app.storage.user.get("user_email")

    @staticmethod
    def get_session_token() -> str | None:
        return app.storage.user.get("session_token")

    @staticmethod
    def get_session_id() -> str | None:
        return app.storage.user.get("session_id")

    @staticmethod
    def get_session_name() -> str | None:
        return app.storage.user.get("session_name")

    @staticmethod
    def set_user(email: str, token: str):
        app.storage.user["user_email"] = email
        app.storage.user["user_token"] = token

    @staticmethod
    def set_session(session_id: str, name: str, token: str):
        app.storage.user["session_id"] = session_id
        app.storage.user["session_name"] = name
        app.storage.user["session_token"] = token

    @staticmethod
    def clear_session():
        app.storage.user.pop("session_id", None)
        app.storage.user.pop("session_name", None)
        app.storage.user.pop("session_token", None)

    @staticmethod
    def logout():
        app.storage.user.clear()


auth_state = AuthState()
