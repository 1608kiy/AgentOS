"""消息系统 - 定义Agent通信的消息格式"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    """消息基类"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: MessageRole
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式（用于LLM调用）"""
        result: dict[str, Any] = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.name:
            result["name"] = self.name
        if self.role == MessageRole.TOOL and self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        return result

    @classmethod
    def system(cls, content: str, **kwargs: Any) -> Message:
        """创建系统消息"""
        return cls(role=MessageRole.SYSTEM, content=content, **kwargs)

    @classmethod
    def user(cls, content: str, **kwargs: Any) -> Message:
        """创建用户消息"""
        return cls(role=MessageRole.USER, content=content, **kwargs)

    @classmethod
    def assistant(cls, content: str, **kwargs: Any) -> Message:
        """创建助手消息"""
        return cls(role=MessageRole.ASSISTANT, content=content, **kwargs)

    @classmethod
    def tool(cls, content: str, name: str | None = None, tool_call_id: str | None = None, **kwargs: Any) -> Message:
        """创建工具消息"""
        return cls(role=MessageRole.TOOL, content=content, name=name, tool_call_id=tool_call_id, **kwargs)


class ToolCall(BaseModel):
    """工具调用请求"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
        }


class ToolResult(BaseModel):
    """工具调用结果"""
    call_id: str
    content: str
    is_error: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "call_id": self.call_id,
            "content": self.content,
            "is_error": self.is_error,
        }


class AgentMessage(BaseModel):
    """Agent间通信消息"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    from_agent: str
    to_agent: str | None = None  # None表示广播
    message_type: str
    content: Any
    correlation_id: str | None = None  # 用于追踪请求-响应
    timestamp: datetime = Field(default_factory=datetime.now)


class ConversationHistory(BaseModel):
    """对话历史"""
    messages: list[Message] = Field(default_factory=list)

    def add(self, message: Message) -> None:
        """添加消息"""
        self.messages.append(message)

    def add_user(self, content: str) -> Message:
        """添加用户消息"""
        msg = Message.user(content)
        self.messages.append(msg)
        return msg

    def add_assistant(self, content: str) -> Message:
        """添加助手消息"""
        msg = Message.assistant(content)
        self.messages.append(msg)
        return msg

    def add_system(self, content: str) -> Message:
        """添加系统消息"""
        msg = Message.system(content)
        self.messages.append(msg)
        return msg

    def add_tool(self, content: str, name: str | None = None, tool_call_id: str | None = None) -> Message:
        """添加工具消息"""
        msg = Message.tool(content, name=name, tool_call_id=tool_call_id)
        self.messages.append(msg)
        return msg

    def get_messages(self, role: MessageRole | None = None) -> list[Message]:
        """获取消息列表"""
        if role is None:
            return self.messages
        return [m for m in self.messages if m.role == role]

    def to_dicts(self) -> list[dict[str, Any]]:
        """转换为字典列表（用于LLM调用）"""
        return [m.to_dict() for m in self.messages]

    def clear(self) -> None:
        """清空对话历史"""
        self.messages.clear()

    def __len__(self) -> int:
        return len(self.messages)
