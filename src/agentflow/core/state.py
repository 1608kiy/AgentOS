"""Agent状态管理"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from agentflow.core.message import Message


class AgentStatus(str, Enum):
    """Agent状态"""
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING = "waiting"
    ERROR = "error"
    COMPLETED = "completed"


class AgentState(BaseModel):
    """Agent状态"""
    agent_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_name: str = ""
    status: AgentStatus = AgentStatus.IDLE
    messages: list[Message] = Field(default_factory=list)
    working_memory: dict[str, Any] = Field(default_factory=dict)
    iteration: int = 0
    max_iterations: int = 10
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def add_message(self, message: Message) -> None:
        """添加消息"""
        self.messages.append(message)
        self.updated_at = datetime.now()

    def get_messages(self) -> list[Message]:
        """获取所有消息"""
        return self.messages

    def get_last_message(self) -> Message | None:
        """获取最后一条消息"""
        return self.messages[-1] if self.messages else None

    def set_status(self, status: AgentStatus) -> None:
        """设置状态"""
        self.status = status
        self.updated_at = datetime.now()

    def set_error(self, error: str) -> None:
        """设置错误"""
        self.error = error
        self.status = AgentStatus.ERROR
        self.updated_at = datetime.now()

    def clear_error(self) -> None:
        """清除错误"""
        self.error = None
        self.updated_at = datetime.now()

    def increment_iteration(self) -> int:
        """增加迭代次数"""
        self.iteration += 1
        self.updated_at = datetime.now()
        return self.iteration

    def is_max_iterations_reached(self) -> bool:
        """是否达到最大迭代次数"""
        return self.iteration >= self.max_iterations

    def update_working_memory(self, key: str, value: Any) -> None:
        """更新工作记忆"""
        self.working_memory[key] = value
        self.updated_at = datetime.now()

    def get_working_memory(self, key: str, default: Any = None) -> Any:
        """获取工作记忆"""
        return self.working_memory.get(key, default)

    def clear_working_memory(self) -> None:
        """清空工作记忆"""
        self.working_memory.clear()
        self.updated_at = datetime.now()

    def reset(self) -> None:
        """重置状态"""
        self.status = AgentStatus.IDLE
        self.messages.clear()
        self.working_memory.clear()
        self.iteration = 0
        self.error = None
        self.updated_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "status": self.status.value,
            "message_count": len(self.messages),
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
