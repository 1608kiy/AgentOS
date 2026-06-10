"""LLM客户端抽象层 - 增强版（重试/退避/缓存）"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any, AsyncIterator

from agentflow.core.config import LLMConfig, LLMProvider
from agentflow.core.message import Message


class LLMResponse:
    """LLM响应"""

    def __init__(
        self,
        content: str,
        model: str,
        usage: dict[str, int] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.content = content
        self.model = model
        self.usage = usage or {}
        self.tool_calls = tool_calls or []
        self.metadata = metadata or {}

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


class ResponseCache:
    """LRU响应缓存"""

    def __init__(self, maxsize: int = 128):
        self._cache: OrderedDict[str, LLMResponse] = OrderedDict()
        self._maxsize = maxsize

    def _make_key(self, messages: list[Message], **kwargs: Any) -> str:
        data = json.dumps([m.to_dict() for m in messages], sort_keys=True) + json.dumps(kwargs, sort_keys=True)
        return hashlib.md5(data.encode()).hexdigest()

    def get(self, messages: list[Message], **kwargs: Any) -> LLMResponse | None:
        key = self._make_key(messages, **kwargs)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, messages: list[Message], response: LLMResponse, **kwargs: Any) -> None:
        key = self._make_key(messages, **kwargs)
        self._cache[key] = response
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)


class LLMClient(ABC):
    """LLM客户端抽象基类"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.model = config.model
        self._cache = ResponseCache()
        self._retry_config = {
            "max_retries": 3,
            "base_delay": 1.0,
            "max_delay": 30.0,
            "retryable_status": {429, 500, 502, 503},
        }

    async def _retry_with_backoff(self, func, *args, **kwargs):
        """指数退避重试"""
        max_retries = self._retry_config["max_retries"]
        base_delay = self._retry_config["base_delay"]
        max_delay = self._retry_config["max_delay"]

        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # 检查是否可重试
                is_retryable = False
                if hasattr(e, 'status_code') and e.status_code in self._retry_config["retryable_status"]:
                    is_retryable = True
                elif any(kw in error_str for kw in ["rate limit", "429", "500", "502", "503", "timeout", "connection"]):
                    is_retryable = True

                if not is_retryable or attempt == max_retries:
                    raise

                delay = min(base_delay * (2 ** attempt), max_delay)
                await asyncio.sleep(delay)

        raise last_exception  # type: ignore

    @abstractmethod
    async def _chat_impl(
        self,
        messages: list[Message],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """实际的chat实现（子类实现）"""
        ...

    @abstractmethod
    async def _stream_chat_impl(
        self,
        messages: list[Message],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """实际的stream_chat实现（子类实现）"""
        ...

    @abstractmethod
    async def _function_call_impl(
        self,
        messages: list[Message],
        functions: list[dict[str, Any]],
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """实际的function_call实现（子类实现）"""
        ...

    async def chat(
        self,
        messages: list[Message],
        temperature: float | None = None,
        max_tokens: int | None = None,
        use_cache: bool = False,
        **kwargs: Any,
    ) -> LLMResponse:
        """发送对话请求（带重试，可选缓存）

        注意: use_cache 默认关闭。在 Agent 多轮循环中，相同 messages 命中缓存会
        导致非确定性行为和难以排查的 bug，因此缓存改为显式 opt-in。
        仅在确定输入幂等（如批量评估、重复问答）时设 use_cache=True。
        """
        if use_cache:
            cached = self._cache.get(messages, temperature=temperature, max_tokens=max_tokens)
            if cached:
                return cached

        response = await self._retry_with_backoff(
            self._chat_impl, messages, temperature, max_tokens, **kwargs
        )

        if use_cache:
            self._cache.set(messages, response, temperature=temperature, max_tokens=max_tokens)

        return response

    async def stream_chat(
        self,
        messages: list[Message],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """流式对话请求"""
        async for chunk in self._stream_chat_impl(messages, temperature, max_tokens, **kwargs):
            yield chunk

    async def function_call(
        self,
        messages: list[Message],
        functions: list[dict[str, Any]],
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """函数调用请求（带重试）"""
        return await self._retry_with_backoff(
            self._function_call_impl, messages, functions, temperature, **kwargs
        )


class OpenAIClient(LLMClient):
    """OpenAI客户端（兼容 MiMo 等第三方 OpenAI 协议服务）"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            from openai import AsyncOpenAI
            kwargs: dict[str, Any] = {"api_key": config.api_key}
            if config.openai_base_url:
                kwargs["base_url"] = config.openai_base_url
            self.client = AsyncOpenAI(**kwargs)
        except ImportError:
            raise ImportError("请安装openai: pip install openai")

    async def _chat_impl(
        self,
        messages: list[Message],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[m.to_dict() for m in messages],
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            **kwargs,
        )
        choice = response.choices[0]
        content = choice.message.content or ""
        # 推理模型（MiMo等）的回复可能在 reasoning_content 里
        if not content and hasattr(choice.message, "reasoning_content"):
            content = choice.message.reasoning_content or ""
        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            tool_calls=[tc.model_dump() for tc in (choice.message.tool_calls or [])],
        )

    async def _stream_chat_impl(
        self,
        messages: list[Message],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[m.to_dict() for m in messages],
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            stream=True,
            **kwargs,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue
            content = delta.content or ""
            # 推理模型的回复可能在 reasoning_content 里
            if not content and hasattr(delta, "reasoning_content") and delta.reasoning_content:
                content = delta.reasoning_content
            if content:
                yield content

    async def _function_call_impl(
        self,
        messages: list[Message],
        functions: list[dict[str, Any]],
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[m.to_dict() for m in messages],
            tools=[{"type": "function", "function": f} for f in functions],
            temperature=temperature or self.config.temperature,
            **kwargs,
        )
        choice = response.choices[0]
        content = choice.message.content or ""
        if not content and hasattr(choice.message, "reasoning_content"):
            content = choice.message.reasoning_content or ""
        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            tool_calls=[tc.model_dump() for tc in (choice.message.tool_calls or [])],
        )


class AnthropicClient(LLMClient):
    """Anthropic客户端"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        try:
            from anthropic import AsyncAnthropic
            import os
            kwargs: dict[str, Any] = {}
            # api_key: config 显式设置 > 环境变量 ANTHROPIC_API_KEY
            key = config.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
            if key:
                kwargs["api_key"] = key
            if config.anthropic_base_url:
                kwargs["base_url"] = config.anthropic_base_url
            self.client = AsyncAnthropic(**kwargs)
        except ImportError:
            raise ImportError("请安装anthropic: pip install anthropic")

    def _split_messages(self, messages: list[Message]) -> tuple[str, list[dict]]:
        system_msg = ""
        chat_messages = []
        for m in messages:
            if m.role.value == "system":
                system_msg = m.content
            else:
                chat_messages.append({"role": m.role.value, "content": m.content})
        return system_msg, chat_messages

    async def _chat_impl(
        self,
        messages: list[Message],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        system_msg, chat_messages = self._split_messages(messages)
        response = await self.client.messages.create(
            model=self.model,
            system=system_msg,
            messages=chat_messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            **kwargs,
        )
        return LLMResponse(
            content=response.content[0].text if response.content else "",
            model=response.model,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
        )

    async def _stream_chat_impl(
        self,
        messages: list[Message],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        system_msg, chat_messages = self._split_messages(messages)
        async with self.client.messages.stream(
            model=self.model,
            system=system_msg,
            messages=chat_messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            **kwargs,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def _function_call_impl(
        self,
        messages: list[Message],
        functions: list[dict[str, Any]],
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        system_msg, chat_messages = self._split_messages(messages)
        tools = [
            {"name": f["name"], "description": f.get("description", ""), "input_schema": f.get("parameters", {})}
            for f in functions
        ]
        response = await self.client.messages.create(
            model=self.model,
            system=system_msg,
            messages=chat_messages,
            tools=tools,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            **kwargs,
        )
        content = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "arguments": block.input})
        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            tool_calls=tool_calls,
        )


class MockLLMClient(LLMClient):
    """Mock LLM客户端（用于测试）"""

    def __init__(self, config: LLMConfig | None = None):
        if config is None:
            config = LLMConfig(provider=LLMProvider.OPENAI, api_key="mock")
        super().__init__(config)
        self.responses: list[str] = []
        self.call_count = 0

    def set_responses(self, responses: list[str]) -> None:
        self.responses = responses

    async def _chat_impl(
        self,
        messages: list[Message],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        if self.responses:
            response = self.responses[self.call_count % len(self.responses)]
            self.call_count += 1
        else:
            response = "这是一个Mock响应"
        return LLMResponse(content=response, model="mock-model")

    async def _stream_chat_impl(
        self,
        messages: list[Message],
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        response = "Mock流式响应"
        for char in response:
            yield char

    async def _function_call_impl(
        self,
        messages: list[Message],
        functions: list[dict[str, Any]],
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        return LLMResponse(content="Mock函数调用", model="mock-model", tool_calls=[])


class LLMFactory:
    """LLM工厂类"""

    _clients: dict[str, type[LLMClient]] = {
        LLMProvider.OPENAI: OpenAIClient,
        LLMProvider.ANTHROPIC: AnthropicClient,
    }

    @classmethod
    def create(cls, config: LLMConfig) -> LLMClient:
        provider = config.provider
        if provider in (LLMProvider.LOCAL, LLMProvider.MIMO):
            return OpenAIClient(config)
        client_class = cls._clients.get(provider)
        if client_class is None:
            raise ValueError(f"不支持的LLM提供商: {provider}")
        return client_class(config)

    @classmethod
    def create_mock(cls) -> MockLLMClient:
        return MockLLMClient()

    @classmethod
    def register(cls, provider: str, client_class: type[LLMClient]) -> None:
        cls._clients[provider] = client_class
