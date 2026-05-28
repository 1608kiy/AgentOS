"""测试配置"""

import pytest
from agentflow.core.config import AgentFlowConfig


@pytest.fixture
def config():
    """测试配置"""
    return AgentFlowConfig()


@pytest.fixture
def mock_llm_config():
    """Mock LLM配置"""
    from agentflow.core.config import LLMConfig, LLMProvider
    return LLMConfig(
        provider=LLMProvider.OPENAI,
        model="mock-model",
        api_key="mock-key",
    )
