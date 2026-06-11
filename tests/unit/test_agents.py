"""Agent测试"""

import pytest
from agentflow.agents.base import (
    AgentConfig,
    ReActAgent,
    PlannerAgent,
    ResearcherAgent,
    CoderAgent,
    ReviewerAgent,
    SummarizerAgent,
    ContentFilterMiddleware,
    CostTrackerMiddleware,
)
from agentflow.core.llm import MockLLMClient
from agentflow.memory.manager import MemoryManager


def test_agent_config():
    """测试Agent配置"""
    config = AgentConfig(agent_name="TestAgent")
    assert config.agent_name == "TestAgent"
    assert config.max_iterations == 10
    assert config.max_tokens_budget == 100000


def test_agent_config_from_env(monkeypatch):
    """测试 from_env 从环境变量加载 LLM 配置（examples 依赖此能力跑真实 LLM）"""
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_API_KEY", "test-key-123")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")

    config = AgentConfig.from_env(agent_name="EnvAgent", system_prompt="测试提示")
    assert config.agent_name == "EnvAgent"
    assert config.system_prompt == "测试提示"
    assert config.llm_provider.value == "deepseek"
    assert config.llm_api_key == "test-key-123"
    assert config.llm_model == "deepseek-chat"


def test_agent_config_from_env_overrides(monkeypatch):
    """测试 from_env 的字段覆盖"""
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    config = AgentConfig.from_env(agent_name="X", temperature=0.1, max_iterations=3)
    assert config.temperature == 0.1
    assert config.max_iterations == 3


def test_agent_from_env_creates_real_client(monkeypatch):
    """测试 from_env + 有 key 时创建真实 LLM 客户端而非 MockLLM"""
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "sk-test-key")
    agent = ReActAgent(config=AgentConfig.from_env(agent_name="RealAgent"))
    assert not isinstance(agent.llm, MockLLMClient)
    assert type(agent.llm).__name__ == "OpenAIClient"


def test_react_agent_creation():
    """测试ReAct Agent创建"""
    agent = ReActAgent(config=AgentConfig(agent_name="TestAgent"))
    assert agent.name == "TestAgent"
    assert agent.id is not None


def test_all_agent_types():
    """测试所有Agent类型"""
    agents = [
        PlannerAgent(),
        ResearcherAgent(),
        CoderAgent(),
        ReviewerAgent(),
        SummarizerAgent(),
    ]
    names = [a.name for a in agents]
    assert "Planner" in names
    assert "Researcher" in names
    assert "Coder" in names
    assert "Reviewer" in names
    assert "Summarizer" in names


@pytest.mark.asyncio
async def test_agent_run():
    """测试Agent运行"""
    agent = ReActAgent(config=AgentConfig(agent_name="TestAgent"))
    agent.llm = MockLLMClient()

    response = await agent.run("Hello")
    assert response.content is not None
    assert response.agent_id == agent.id
    assert response.iterations >= 1


@pytest.mark.asyncio
async def test_agent_run_with_context():
    """测试带上下文的Agent运行"""
    agent = ReActAgent(config=AgentConfig(agent_name="TestAgent"))
    agent.llm = MockLLMClient()

    response = await agent.run("分析这段代码", context="def foo(): pass")
    assert response.content is not None


@pytest.mark.asyncio
async def test_agent_memory_integration():
    """测试Agent记忆集成"""
    memory = MemoryManager()
    agent = ReActAgent(config=AgentConfig(agent_name="TestAgent"), memory=memory)
    agent.llm = MockLLMClient()

    response = await agent.run("Hello")
    assert response.content is not None


def test_agent_state():
    """测试Agent状态"""
    agent = ReActAgent(config=AgentConfig(agent_name="TestAgent"))
    state = agent.get_state()

    assert state["agent_name"] == "TestAgent"
    assert state["status"] == "idle"


def test_agent_reset():
    """测试Agent重置"""
    agent = ReActAgent(config=AgentConfig(agent_name="TestAgent"))
    agent.state.increment_iteration()
    agent.reset()

    assert agent.state.iteration == 0


@pytest.mark.asyncio
async def test_content_filter_middleware():
    """测试内容过滤中间件"""
    agent = ReActAgent(config=AgentConfig(agent_name="TestAgent"))
    agent.add_middleware(ContentFilterMiddleware())
    agent.llm = MockLLMClient()

    response = await agent.run("rm -rf /")
    assert "安全拒绝" in response.content


@pytest.mark.asyncio
async def test_cost_tracker_middleware():
    """测试成本追踪中间件"""
    tracker = CostTrackerMiddleware()
    agent = ReActAgent(config=AgentConfig(agent_name="TestAgent"))
    agent.add_middleware(tracker)
    agent.llm = MockLLMClient()

    await agent.run("Hello")
    usage = tracker.get_usage()
    assert agent.id in usage
