"""认证与鉴权模块"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# ============ 配置 ============

class AuthConfig(BaseSettings):
    """认证配置"""
    secret_key: str = "change-this-to-a-random-secret-key-in-production"
    api_keys: str = ""  # 逗号分隔的API keys
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    model_config = {"env_prefix": "AUTH_"}


# ============ 数据模型 ============

class UserRole(str):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class TokenData(BaseModel):
    """JWT Token数据"""
    user_id: str
    role: str = UserRole.USER
    exp: datetime | None = None


class APIKeyData(BaseModel):
    """API Key数据"""
    key_prefix: str
    role: str = UserRole.USER
    created_at: datetime = Field(default_factory=datetime.now)


# ============ JWT工具 ============

def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """创建JWT Token"""
    try:
        from jose import jwt

        config = AuthConfig()
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=config.access_token_expire_minutes))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, config.secret_key, algorithm=config.algorithm)
    except ImportError:
        # 如果没有jose，使用简单的token生成
        config = AuthConfig()
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=config.access_token_expire_minutes))
        to_encode.update({"exp": expire.isoformat()})
        import base64
        import json
        token_data = json.dumps(to_encode)
        return base64.urlsafe_b64encode(token_data.encode()).decode()


def verify_token(token: str) -> TokenData | None:
    """验证JWT Token"""
    try:
        from jose import jwt, JWTError

        config = AuthConfig()
        try:
            payload = jwt.decode(token, config.secret_key, algorithms=[config.algorithm])
            user_id: str = payload.get("sub", "")
            role: str = payload.get("role", UserRole.USER)
            if not user_id:
                return None
            return TokenData(user_id=user_id, role=role)
        except JWTError:
            return None
    except ImportError:
        # 简单token验证
        try:
            import base64
            import json
            decoded = json.loads(base64.urlsafe_b64decode(token.encode()))
            exp_str = decoded.get("exp")
            if exp_str:
                exp = datetime.fromisoformat(exp_str)
                if exp < datetime.utcnow():
                    return None
            return TokenData(
                user_id=decoded.get("sub", ""),
                role=decoded.get("role", UserRole.USER),
            )
        except Exception:
            return None


# ============ API Key管理 ============

class APIKeyManager:
    """API Key管理器"""

    def __init__(self) -> None:
        config = AuthConfig()
        self._valid_keys: dict[str, str] = {}  # key -> role
        if config.api_keys:
            for key in config.api_keys.split(","):
                key = key.strip()
                if key:
                    self._valid_keys[key] = UserRole.ADMIN

    def validate_key(self, api_key: str) -> str | None:
        """验证API key，返回角色或None"""
        return self._valid_keys.get(api_key)

    def add_key(self, api_key: str, role: str = UserRole.USER) -> None:
        self._valid_keys[api_key] = role

    def remove_key(self, api_key: str) -> bool:
        if api_key in self._valid_keys:
            del self._valid_keys[api_key]
            return True
        return False


# ============ FastAPI依赖 ============

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

_api_key_manager = APIKeyManager()


async def get_current_user(
    request: Request,
    api_key: str | None = Security(api_key_header),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> TokenData:
    """FastAPI依赖：获取当前用户（支持API Key和JWT）"""

    # 1. 尝试API Key
    if api_key:
        role = _api_key_manager.validate_key(api_key)
        if role:
            return TokenData(user_id="api_key_user", role=role)
        raise HTTPException(status_code=401, detail="无效的API Key")

    # 2. 尝试JWT Token
    if credentials and credentials.credentials:
        token_data = verify_token(credentials.credentials)
        if token_data:
            return token_data
        raise HTTPException(status_code=401, detail="无效的Token")

    # 3. 无认证信息
    raise HTTPException(
        status_code=401,
        detail="缺少认证信息。请提供 X-API-Key 或 Authorization: Bearer <token>",
    )


async def require_admin(user: TokenData = Depends(get_current_user)) -> TokenData:
    """FastAPI依赖：要求管理员权限"""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def optional_auth(
    request: Request,
    api_key: str | None = Security(api_key_header),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> TokenData | None:
    """FastAPI依赖：可选认证（无认证返回默认用户）"""
    try:
        return await get_current_user(request, api_key, credentials)
    except HTTPException:
        return TokenData(user_id="anonymous", role=UserRole.VIEWER)
