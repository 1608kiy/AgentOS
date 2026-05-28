"""Agent通信总线"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Callable, Awaitable
from uuid import uuid4

from pydantic import BaseModel, Field


class MessageType(str):
    """消息类型常量"""
    TASK_ASSIGN = "task_assign"
    TASK_RESULT = "task_result"
    REQUEST = "request"
    RESPONSE = "response"
    BROADCAST = "broadcast"
    ERROR = "error"
    STATUS_UPDATE = "status_update"


class BusMessage(BaseModel):
    """总线消息"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    from_agent: str
    to_agent: str | None = None  # None表示广播
    message_type: str
    content: Any
    correlation_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type,
            "content": self.content,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
        }


MessageHandler = Callable[[BusMessage], Awaitable[None]]


class MessageBus:
    """Agent间消息总线"""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[MessageHandler]] = {}
        self._message_history: list[BusMessage] = []
        self._pending_responses: dict[str, asyncio.Future[BusMessage]] = {}

    async def publish(self, message: BusMessage) -> None:
        """发布消息"""
        self._message_history.append(message)

        if message.to_agent:
            # 发送给特定Agent
            handlers = self._subscribers.get(message.to_agent, [])
            for handler in handlers:
                try:
                    await handler(message)
                except Exception as e:
                    print(f"消息处理错误 [{message.to_agent}]: {e}")
        else:
            # 广播
            for agent_id, handlers in self._subscribers.items():
                if agent_id != message.from_agent:  # 不发送给自己
                    for handler in handlers:
                        try:
                            await handler(message)
                        except Exception as e:
                            print(f"消息处理错误 [{agent_id}]: {e}")

    def subscribe(self, agent_id: str, handler: MessageHandler) -> None:
        """订阅消息"""
        if agent_id not in self._subscribers:
            self._subscribers[agent_id] = []
        self._subscribers[agent_id].append(handler)

    def unsubscribe(self, agent_id: str) -> None:
        """取消订阅"""
        self._subscribers.pop(agent_id, None)

    async def request(
        self,
        from_agent: str,
        to_agent: str,
        content: Any,
        timeout: float = 30.0,
    ) -> BusMessage:
        """发送请求并等待响应"""
        correlation_id = str(uuid4())

        # 创建请求消息
        request = BusMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.REQUEST,
            content=content,
            correlation_id=correlation_id,
        )

        # 创建Future等待响应
        future: asyncio.Future[BusMessage] = asyncio.get_event_loop().create_future()
        self._pending_responses[correlation_id] = future

        # 发送请求
        await self.publish(request)

        try:
            # 等待响应
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            raise TimeoutError(f"请求超时: {from_agent} -> {to_agent}")
        finally:
            self._pending_responses.pop(correlation_id, None)

    async def respond(self, response: BusMessage) -> None:
        """发送响应"""
        correlation_id = response.correlation_id
        if correlation_id and correlation_id in self._pending_responses:
            future = self._pending_responses[correlation_id]
            if not future.done():
                future.set_result(response)
        else:
            # 普通消息
            await self.publish(response)

    def get_history(
        self,
        agent_id: str | None = None,
        message_type: str | None = None,
        limit: int = 100,
    ) -> list[BusMessage]:
        """获取消息历史"""
        messages = self._message_history

        if agent_id:
            messages = [
                m for m in messages
                if m.from_agent == agent_id or m.to_agent == agent_id
            ]

        if message_type:
            messages = [m for m in messages if m.message_type == message_type]

        return messages[-limit:]

    def clear_history(self) -> None:
        """清空消息历史"""
        self._message_history.clear()

    def get_subscribers(self) -> list[str]:
        """获取所有订阅者"""
        return list(self._subscribers.keys())

    def is_subscribed(self, agent_id: str) -> bool:
        """检查是否已订阅"""
        return agent_id in self._subscribers


class EventBus:
    """事件总线 - 基于事件的通信"""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., Awaitable[None]]]] = {}

    def on(self, event: str, handler: Callable[..., Awaitable[None]]) -> None:
        """注册事件处理器"""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    def off(self, event: str, handler: Callable[..., Awaitable[None]] | None = None) -> None:
        """取消事件处理器"""
        if handler:
            if event in self._handlers:
                self._handlers[event] = [h for h in self._handlers[event] if h != handler]
        else:
            self._handlers.pop(event, None)

    async def emit(self, event: str, data: Any = None) -> None:
        """触发事件"""
        handlers = self._handlers.get(event, [])
        for handler in handlers:
            try:
                if data is not None:
                    await handler(data)
                else:
                    await handler()
            except Exception as e:
                print(f"事件处理错误 [{event}]: {e}")

    def list_events(self) -> list[str]:
        """列出所有事件"""
        return list(self._handlers.keys())


# 全局实例
message_bus = MessageBus()
event_bus = EventBus()
