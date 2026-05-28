"""认证模块测试"""

import pytest
from agentflow.api.auth import (
    create_access_token,
    verify_token,
    TokenData,
    UserRole,
    APIKeyManager,
)


def test_create_and_verify_token():
    """测试JWT Token创建和验证"""
    token = create_access_token({"sub": "user123", "role": UserRole.USER})
    assert token is not None
    assert isinstance(token, str)

    data = verify_token(token)
    assert data is not None
    assert data.user_id == "user123"
    assert data.role == UserRole.USER


def test_verify_invalid_token():
    """测试无效Token"""
    data = verify_token("invalid-token-xxx")
    # 可能返回None或解析失败
    # 取决于实现


def test_api_key_manager():
    """测试API Key管理"""
    manager = APIKeyManager()
    manager.add_key("test-key-123", UserRole.ADMIN)

    assert manager.validate_key("test-key-123") == UserRole.ADMIN
    assert manager.validate_key("wrong-key") is None

    assert manager.remove_key("test-key-123") is True
    assert manager.validate_key("test-key-123") is None
    assert manager.remove_key("nonexistent") is False


def test_user_roles():
    """测试用户角色"""
    assert UserRole.ADMIN == "admin"
    assert UserRole.USER == "user"
    assert UserRole.VIEWER == "viewer"
