"""Redis会话持久化"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionData(BaseModel):
    """会话数据"""
    session_id: str
    user_id: str = "anonymous"
    chat_history: list[dict[str, Any]] = Field(default_factory=list)
    agents_state: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionStore:
    """会话存储基类"""

    async def save(self, session: SessionData) -> None:
        raise NotImplementedError

    async def load(self, session_id: str) -> SessionData | None:
        raise NotImplementedError

    async def delete(self, session_id: str) -> bool:
        raise NotImplementedError

    async def list_sessions(self, user_id: str | None = None) -> list[SessionData]:
        raise NotImplementedError


class MemorySessionStore(SessionStore):
    """内存会话存储（开发用）"""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}

    async def save(self, session: SessionData) -> None:
        session.updated_at = datetime.now()
        self._sessions[session.session_id] = session

    async def load(self, session_id: str) -> SessionData | None:
        return self._sessions.get(session_id)

    async def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    async def list_sessions(self, user_id: str | None = None) -> list[SessionData]:
        sessions = list(self._sessions.values())
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)


class RedisSessionStore(SessionStore):
    """Redis会话存储"""

    def __init__(self, redis_url: str = "redis://localhost:6379", prefix: str = "agentflow:session:"):
        self._prefix = prefix
        self._redis_url = redis_url
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            except ImportError:
                raise ImportError("请安装redis: pip install redis")
        return self._redis

    async def save(self, session: SessionData) -> None:
        redis = await self._get_redis()
        session.updated_at = datetime.now()
        key = f"{self._prefix}{session.session_id}"
        data = session.model_dump_json()
        await redis.set(key, data, ex=86400)  # 24小时过期

        # 添加到用户会话索引
        user_key = f"agentflow:user_sessions:{session.user_id}"
        await redis.sadd(user_key, session.session_id)

    async def load(self, session_id: str) -> SessionData | None:
        redis = await self._get_redis()
        key = f"{self._prefix}{session_id}"
        data = await redis.get(key)
        if data:
            return SessionData.model_validate_json(data)
        return None

    async def delete(self, session_id: str) -> bool:
        redis = await self._get_redis()
        key = f"{self._prefix}{session_id}"
        result = await redis.delete(key)
        return result > 0

    async def list_sessions(self, user_id: str | None = None) -> list[SessionData]:
        redis = await self._get_redis()
        if user_id:
            user_key = f"agentflow:user_sessions:{user_id}"
            session_ids = await redis.smembers(user_key)
        else:
            keys = await redis.keys(f"{self._prefix}*")
            session_ids = [k.replace(self._prefix, "") for k in keys]

        sessions = []
        for sid in session_ids:
            session = await self.load(sid)
            if session:
                sessions.append(session)
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()


class FileSessionStore(SessionStore):
    """文件会话存储"""

    def __init__(self, data_dir: str = "./data/sessions"):
        from pathlib import Path
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, session_id: str):
        return self._dir / f"{session_id}.json"

    async def save(self, session: SessionData) -> None:
        session.updated_at = datetime.now()
        path = self._get_path(session.session_id)
        path.write_text(session.model_dump_json(indent=2), encoding="utf-8")

    async def load(self, session_id: str) -> SessionData | None:
        path = self._get_path(session_id)
        if path.exists():
            return SessionData.model_validate_json(path.read_text(encoding="utf-8"))
        return None

    async def delete(self, session_id: str) -> bool:
        path = self._get_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False

    async def list_sessions(self, user_id: str | None = None) -> list[SessionData]:
        sessions = []
        for f in self._dir.glob("*.json"):
            try:
                session = SessionData.model_validate_json(f.read_text(encoding="utf-8"))
                if user_id is None or session.user_id == user_id:
                    sessions.append(session)
            except Exception:
                continue
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)


def create_session_store(store_type: str = "memory", **kwargs) -> SessionStore:
    """创建会话存储"""
    if store_type == "redis":
        return RedisSessionStore(**kwargs)
    elif store_type == "file":
        return FileSessionStore(**kwargs)
    else:
        return MemorySessionStore()
