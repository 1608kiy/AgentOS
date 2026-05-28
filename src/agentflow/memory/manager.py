"""记忆系统 - 分层记忆管理"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from agentflow.core.message import Message


class Memory(BaseModel):
    """记忆条目"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    relevance_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "relevance_score": self.relevance_score,
        }


class ShortTermMemory:
    """短期记忆 - 对话上下文"""

    def __init__(self, max_messages: int = 50):
        self.messages: list[Message] = []
        self.max_messages = max_messages

    def add(self, message: Message) -> None:
        """添加消息"""
        self.messages.append(message)
        # 超过限制时移除最旧的消息
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def get_context(self, last_n: int | None = None) -> list[Message]:
        """获取上下文"""
        if last_n:
            return self.messages[-last_n:]
        return self.messages.copy()

    def get_context_string(self, last_n: int | None = None) -> str:
        """获取上下文字符串"""
        messages = self.get_context(last_n)
        return "\n".join(f"[{m.role.value}] {m.content}" for m in messages)

    def clear(self) -> None:
        """清空"""
        self.messages.clear()

    def __len__(self) -> int:
        return len(self.messages)


class LongTermMemory:
    """长期记忆 - 基于向量存储"""

    def __init__(self, store_path: str = "./data/chroma"):
        self.store_path = store_path
        self._memories: list[Memory] = []
        self._initialized = False

    async def initialize(self) -> None:
        """初始化向量存储"""
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=self.store_path)
            self._collection = self._client.get_or_create_collection(
                name="agent_memory",
                metadata={"hnsw:space": "cosine"},
            )
            self._initialized = True
        except ImportError:
            # 如果没有chromadb，使用内存存储
            self._initialized = False

    async def store(self, content: str, metadata: dict[str, Any] | None = None) -> Memory:
        """存储记忆"""
        memory = Memory(content=content, metadata=metadata or {})
        self._memories.append(memory)

        if self._initialized:
            try:
                self._collection.add(
                    documents=[content],
                    metadatas=[metadata or {}],
                    ids=[memory.id],
                )
            except Exception:
                pass  # 降级到内存存储

        return memory

    async def retrieve(self, query: str, top_k: int = 5) -> list[Memory]:
        """检索相关记忆"""
        if not self._memories:
            return []

        if self._initialized:
            try:
                results = self._collection.query(
                    query_texts=[query],
                    n_results=min(top_k, len(self._memories)),
                )
                if results and results["ids"]:
                    memory_ids = set(results["ids"][0])
                    return [m for m in self._memories if m.id in memory_ids][:top_k]
            except Exception:
                pass

        # 降级：简单关键词匹配
        scored = []
        query_lower = query.lower()
        for memory in self._memories:
            score = sum(
                1 for word in query_lower.split()
                if word in memory.content.lower()
            )
            scored.append((score, memory))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:top_k]]

    async def forget(self, memory_id: str) -> bool:
        """删除记忆"""
        self._memories = [m for m in self._memories if m.id != memory_id]
        if self._initialized:
            try:
                self._collection.delete(ids=[memory_id])
            except Exception:
                pass
        return True

    async def clear(self) -> None:
        """清空所有记忆"""
        self._memories.clear()
        if self._initialized:
            try:
                self._client.delete_collection("agent_memory")
                self._collection = self._client.get_or_create_collection(
                    name="agent_memory",
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception:
                pass

    def __len__(self) -> int:
        return len(self._memories)


class WorkingMemory:
    """工作记忆 - 当前任务上下文"""

    def __init__(self) -> None:
        self.scratch_pad: dict[str, Any] = {}
        self.task_stack: list[str] = []
        self.sub_goals: list[str] = []
        self.context: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        """设置工作记忆"""
        self.scratch_pad[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取工作记忆"""
        return self.scratch_pad.get(key, default)

    def push_task(self, task: str) -> None:
        """压入任务栈"""
        self.task_stack.append(task)

    def pop_task(self) -> str | None:
        """弹出任务栈"""
        return self.task_stack.pop() if self.task_stack else None

    def current_task(self) -> str | None:
        """获取当前任务"""
        return self.task_stack[-1] if self.task_stack else None

    def add_sub_goal(self, goal: str) -> None:
        """添加子目标"""
        self.sub_goals.append(goal)

    def complete_sub_goal(self, goal: str) -> bool:
        """完成子目标"""
        if goal in self.sub_goals:
            self.sub_goals.remove(goal)
            return True
        return False

    def update_context(self, key: str, value: Any) -> None:
        """更新上下文"""
        self.context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """获取上下文"""
        return self.context.get(key, default)

    def clear(self) -> None:
        """清空工作记忆"""
        self.scratch_pad.clear()
        self.task_stack.clear()
        self.sub_goals.clear()
        self.context.clear()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "scratch_pad": self.scratch_pad,
            "task_stack": self.task_stack,
            "sub_goals": self.sub_goals,
            "context": self.context,
        }


class MemoryManager:
    """记忆管理器 - 统一接口"""

    def __init__(
        self,
        max_short_term: int = 50,
        long_term_path: str = "./data/chroma",
    ):
        self.short_term = ShortTermMemory(max_messages=max_short_term)
        self.long_term = LongTermMemory(store_path=long_term_path)
        self.working = WorkingMemory()
        self._initialized = False

    async def initialize(self) -> None:
        """初始化记忆系统"""
        await self.long_term.initialize()
        self._initialized = True

    async def remember(self, content: str, memory_type: str = "short", metadata: dict[str, Any] | None = None) -> Memory | None:
        """记住信息"""
        if memory_type == "short":
            self.short_term.add(Message.assistant(content))
            return None
        elif memory_type == "long":
            return await self.long_term.store(content, metadata)
        else:
            raise ValueError(f"未知的记忆类型: {memory_type}")

    async def recall(self, query: str, memory_type: str = "all", top_k: int = 5) -> list[Memory]:
        """回忆信息"""
        results: list[Memory] = []

        if memory_type in ("all", "long"):
            long_term_results = await self.long_term.retrieve(query, top_k)
            results.extend(long_term_results)

        if memory_type in ("all", "short"):
            # 短期记忆简单搜索
            for msg in self.short_term.get_context():
                if query.lower() in msg.content.lower():
                    results.append(Memory(content=msg.content, metadata={"source": "short_term"}))

        return results[:top_k]

    async def consolidate(self) -> None:
        """整合记忆 - 将重要短期记忆转入长期记忆"""
        messages = self.short_term.get_context()
        if not messages:
            return

        # 简单策略：将所有消息整合为一条长期记忆
        summary = "\n".join(f"[{m.role.value}] {m.content}" for m in messages[-10:])
        await self.long_term.store(
            content=summary,
            metadata={"type": "consolidated", "source": "short_term"},
        )

    async def clear(self) -> None:
        """清空所有记忆"""
        self.short_term.clear()
        await self.long_term.clear()
        self.working.clear()

    def get_context_string(self) -> str:
        """获取完整上下文字符串"""
        parts = []

        # 工作记忆
        if self.working.current_task():
            parts.append(f"当前任务: {self.working.current_task()}")

        # 短期记忆
        short_context = self.short_term.get_context_string(last_n=10)
        if short_context:
            parts.append(f"最近对话:\n{short_context}")

        return "\n\n".join(parts)
