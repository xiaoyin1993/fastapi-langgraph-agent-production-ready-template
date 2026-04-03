"""这个文件包含应用的认证数据模式。"""

import re
from datetime import datetime

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
)


class Token(BaseModel):
    """认证令牌模型。

    属性:
        access_token: JWT 访问令牌。
        token_type: 令牌类型（固定为 "bearer"）。
        expires_at: 令牌过期时间戳。
    """

    access_token: str = Field(..., description="The JWT access token")
    token_type: str = Field(default="bearer", description="The type of token")
    expires_at: datetime = Field(..., description="The token expiration timestamp")


class TokenResponse(BaseModel):
    """登录接口的响应模型。

    属性:
        access_token: JWT 访问令牌
        token_type: 令牌类型（固定为 "bearer"）
        expires_at: 令牌过期时间
    """

    access_token: str = Field(..., description="The JWT access token")
    token_type: str = Field(default="bearer", description="The type of token")
    expires_at: datetime = Field(..., description="When the token expires")


class UserCreate(BaseModel):
    """用户注册的请求模型。

    属性:
        email: 用户的邮箱地址
        password: 用户的密码
    """

    email: EmailStr = Field(..., description="User's email address")
    password: SecretStr = Field(..., description="User's password", min_length=8, max_length=64)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: SecretStr) -> SecretStr:
        """校验密码强度。

        参数:
            v: 待校验的密码

        返回:
            SecretStr: 校验通过的密码

        异常:
            ValueError: 密码强度不够时抛出
        """
        password = v.get_secret_value()

        # 检查常见的密码要求
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")

        if not re.search(r"[A-Z]", password):
            raise ValueError("Password must contain at least one uppercase letter")

        if not re.search(r"[a-z]", password):
            raise ValueError("Password must contain at least one lowercase letter")

        if not re.search(r"[0-9]", password):
            raise ValueError("Password must contain at least one number")

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValueError("Password must contain at least one special character")

        return v


class UserResponse(BaseModel):
    """用户操作的响应模型。

    属性:
        id: 用户 ID
        email: 用户邮箱地址
        token: 认证令牌
    """

    id: int = Field(..., description="User's ID")
    email: str = Field(..., description="User's email address")
    token: Token = Field(..., description="Authentication token")


class SessionResponse(BaseModel):
    """创建会话的响应模型。

    属性:
        session_id: 聊天会话的唯一标识符
        name: 会话名称（默认为空字符串）
        token: 会话的认证令牌
    """

    session_id: str = Field(..., description="The unique identifier for the chat session")
    name: str = Field(default="", description="Name of the session", max_length=100)
    token: Token = Field(..., description="The authentication token for the session")

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        """清理会话名称中的特殊字符。

        参数:
            v: 待清理的名称

        返回:
            str: 清理后的名称
        """
        # 移除可能有害的字符
        sanitized = re.sub(r'[<>{}[\]()\'"`]', "", v)
        return sanitized
