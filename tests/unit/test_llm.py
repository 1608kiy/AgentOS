"""LLM 客户端测试 - 覆盖 Provider 路由、缓存、重试、Mock"""

import pytest
from agentflow.core.config import LLMConfig, LLMProvider
from agentflow.core.llm import (
    LLMFactory,
    LLMResponse,
    LLMClient,
    MockLLMClient,
    ResponseCache,
)
from agentflow.core.message import Message


# ============ Provider Enum ============

def test_all_providers_present():
    expected = {"openai", "anthropic", "local", "mimo", "deepseek", "gemini"}
    actual = {p.value for p in LLMProvider}
    assert expected == actual


# ============ LLMFactory Routing ============

def test_factory_routes_openai():
    cfg = LLMConfig(provider=LLMProvider.OPENAI, api_key="test")
    client = LLMFactory.create(cfg)
    assert type(client).__name__ == "OpenAIClient"


def test_factory_routes_anthropic():
    pytest.importorskip("anthropic", reason="anthropic not installed")
    cfg = LLMConfig(provider=LLMProvider.ANTHROPIC, api_key="test", anthropic_api_key="test")
    client = LLMFactory.create(cfg)
    assert type(client).__name__ == "AnthropicClient"


def test_factory_routes_mimo_as_openai():
    cfg = LLMConfig(provider=LLMProvider.MIMO, api_key="test")
    client = LLMFactory.create(cfg)
    assert type(client).__name__ == "OpenAIClient"


def test_factory_routes_local_as_openai():
    cfg = LLMConfig(provider=LLMProvider.LOCAL, api_key="test")
    client = LLMFactory.create(cfg)
    assert type(client).__name__ == "OpenAIClient"


def test_factory_routes_deepseek_with_default_base_url():
    cfg = LLMConfig(provider=LLMProvider.DEEPSEEK, api_key="test-key", openai_base_url="")
    client = LLMFactory.create(cfg)
    assert type(client).__name__ == "OpenAIClient"
    assert "deepseek" in cfg.openai_base_url


def test_factory_routes_deepseek_preserves_custom_base_url():
    cfg = LLMConfig(provider=LLMProvider.DEEPSEEK, api_key="test", openai_base_url="https://custom/v1")
    client = LLMFactory.create(cfg)
    assert cfg.openai_base_url == "https://custom/v1"


def test_factory_raises_on_unknown_provider():
    cfg = LLMConfig(api_key="test")
    cfg.provider = "unknown_provider"
    with pytest.raises(ValueError, match="不支持"):
        LLMFactory.create(cfg)


# ============ MockLLMClient ============

@pytest.mark.asyncio
async def test_mock_llm_default_response():
    client = MockLLMClient()
    resp = await client.chat([])
    assert resp.content == "这是一个Mock响应"


@pytest.mark.asyncio
async def test_mock_llm_set_responses():
    client = MockLLMClient()
    client.set_responses(["hello", "world"])
    r1 = await client.chat([])
    r2 = await client.chat([Message.user("different")])
    r3 = await client.chat([Message.user("another")])
    assert r1.content == "hello"
    assert r2.content == "world"
    assert r3.content == "hello"  # cycles
    assert client.call_count == 3


@pytest.mark.asyncio
async def test_mock_llm_stream():
    client = MockLLMClient()
    chunks = [c async for c in client._stream_chat_impl([])]
    assert "".join(chunks) == "Mock流式响应"


@pytest.mark.asyncio
async def test_mock_llm_function_call():
    client = MockLLMClient()
    resp = await client._function_call_impl([], [])
    assert resp.tool_calls == []


# ============ ResponseCache ============

def test_cache_set_and_get():
    cache = ResponseCache(maxsize=10)
    msg = [Message.user("hello")]
    resp = LLMResponse(content="hi", model="test")
    cache.set(msg, resp)
    assert cache.get(msg) is resp


def test_cache_different_messages():
    cache = ResponseCache(maxsize=10)
    msg1 = [Message.user("a")]
    msg2 = [Message.user("b")]
    resp = LLMResponse(content="r", model="test")
    cache.set(msg1, resp)
    assert cache.get(msg1) is resp
    assert cache.get(msg2) is None


def test_cache_lru_eviction():
    cache = ResponseCache(maxsize=2)
    m1 = [Message.user("1")]
    m2 = [Message.user("2")]
    m3 = [Message.user("3")]
    r = LLMResponse(content="r", model="t")
    cache.set(m1, r)
    cache.set(m2, r)
    cache.set(m3, r)
    assert cache.get(m1) is None  # evicted
    assert cache.get(m2) is r


def test_cache_mru_promotion():
    cache = ResponseCache(maxsize=2)
    m1 = [Message.user("1")]
    m2 = [Message.user("2")]
    r = LLMResponse(content="r", model="t")
    cache.set(m1, r)
    cache.set(m2, r)
    cache.get(m1)          # promote m1
    cache.set([Message.user("3")], r)  # evicts m2, not m1
    assert cache.get(m1) is r


# ============ LLMResponse ============

def test_llm_response_total_tokens():
    r = LLMResponse(content="x", model="t", usage={"total_tokens": 42})
    assert r.total_tokens == 42


def test_llm_response_default_usage():
    r = LLMResponse(content="x", model="t")
    assert r.total_tokens == 0


# ============ LLMConfig Defaults ============

def test_llm_config_defaults():
    cfg = LLMConfig()
    assert cfg.provider in (LLMProvider.OPENAI, LLMProvider.MIMO)  # .env 可能覆盖
    assert isinstance(cfg.model, str)
    assert 0 <= cfg.temperature <= 2
    assert cfg.max_tokens > 0
    assert cfg.timeout > 0
