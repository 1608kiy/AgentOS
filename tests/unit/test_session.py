"""会话持久化测试"""

import pytest
from agentflow.core.session import (
    SessionData,
    MemorySessionStore,
    FileSessionStore,
    create_session_store,
)


@pytest.mark.asyncio
async def test_memory_session_store():
    """测试内存存储"""
    store = MemorySessionStore()

    session = SessionData(
        session_id="test-1",
        user_id="user1",
        chat_history=[{"role": "user", "content": "hello"}],
    )

    await store.save(session)
    loaded = await store.load("test-1")

    assert loaded is not None
    assert loaded.session_id == "test-1"
    assert loaded.user_id == "user1"
    assert len(loaded.chat_history) == 1


@pytest.mark.asyncio
async def test_memory_session_list():
    """测试会话列表"""
    store = MemorySessionStore()

    await store.save(SessionData(session_id="s1", user_id="u1"))
    await store.save(SessionData(session_id="s2", user_id="u1"))
    await store.save(SessionData(session_id="s3", user_id="u2"))

    all_sessions = await store.list_sessions()
    assert len(all_sessions) == 3

    user1_sessions = await store.list_sessions(user_id="u1")
    assert len(user1_sessions) == 2


@pytest.mark.asyncio
async def test_memory_session_delete():
    """测试删除会话"""
    store = MemorySessionStore()

    await store.save(SessionData(session_id="s1"))
    assert await store.delete("s1") is True
    assert await store.load("s1") is None
    assert await store.delete("nonexistent") is False


@pytest.mark.asyncio
async def test_file_session_store(tmp_path):
    """测试文件存储"""
    store = FileSessionStore(data_dir=str(tmp_path))

    session = SessionData(
        session_id="file-test",
        user_id="user1",
        chat_history=[{"role": "user", "content": "test"}],
    )

    await store.save(session)
    loaded = await store.load("file-test")

    assert loaded is not None
    assert loaded.session_id == "file-test"


def test_create_session_store():
    """测试工厂函数"""
    store = create_session_store("memory")
    assert isinstance(store, MemorySessionStore)

    store = create_session_store("file", data_dir="/tmp/test")
    assert isinstance(store, FileSessionStore)
