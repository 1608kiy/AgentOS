"""编排器测试"""

import pytest
from agentflow.agents.base import ReActAgent, AgentConfig
from agentflow.core.llm import MockLLMClient
from agentflow.workflow.orchestrator import (
    AgentOrchestrator,
    OrchestrationStrategy,
    OrchestrationResult,
)


@pytest.fixture
def mock_agents():
    agents = []
    for i in range(3):
        agent = ReActAgent(config=AgentConfig(agent_name=f"Agent_{i}"))
        agent.llm = MockLLMClient()
        agents.append(agent)
    return agents


def test_orchestrator_creation():
    orchestrator = AgentOrchestrator(strategy=OrchestrationStrategy.SEQUENTIAL)
    assert orchestrator.strategy == OrchestrationStrategy.SEQUENTIAL


def test_orchestrator_register(mock_agents):
    orchestrator = AgentOrchestrator()
    for agent in mock_agents:
        orchestrator.register_agent(agent)
    assert len(orchestrator.agents) == 3


@pytest.mark.asyncio
async def test_sequential_execution(mock_agents):
    orchestrator = AgentOrchestrator(strategy=OrchestrationStrategy.SEQUENTIAL)
    for agent in mock_agents:
        orchestrator.register_agent(agent)

    result = await orchestrator.run("Test task", agent_ids=[a.id for a in mock_agents])
    assert isinstance(result, OrchestrationResult)
    assert result.strategy == "sequential"
    assert result.final_output is not None


@pytest.mark.asyncio
async def test_parallel_execution(mock_agents):
    orchestrator = AgentOrchestrator(strategy=OrchestrationStrategy.PARALLEL)
    for agent in mock_agents:
        orchestrator.register_agent(agent)

    result = await orchestrator.run("Test task", agent_ids=[a.id for a in mock_agents])
    assert isinstance(result, OrchestrationResult)
    assert result.strategy == "parallel"


@pytest.mark.asyncio
async def test_debate_execution(mock_agents):
    orchestrator = AgentOrchestrator(strategy=OrchestrationStrategy.DEBATE)
    for agent in mock_agents:
        orchestrator.register_agent(agent)

    result = await orchestrator.run("讨论AI的未来", agent_ids=[a.id for a in mock_agents[:2]])
    assert isinstance(result, OrchestrationResult)
    assert result.strategy == "debate"


@pytest.mark.asyncio
async def test_supervisor_execution(mock_agents):
    orchestrator = AgentOrchestrator(strategy=OrchestrationStrategy.SUPERVISOR)
    for agent in mock_agents:
        orchestrator.register_agent(agent)

    result = await orchestrator.run("完成项目", agent_ids=[a.id for a in mock_agents])
    assert isinstance(result, OrchestrationResult)
    assert result.strategy == "supervisor"


def test_orchestration_result():
    result = OrchestrationResult(
        strategy="sequential",
        task="test task",
        final_output="test output",
    )
    d = result.to_dict()
    assert d["strategy"] == "sequential"
    assert d["task"] == "test task"


def test_get_agents(mock_agents):
    orchestrator = AgentOrchestrator()
    for agent in mock_agents:
        orchestrator.register_agent(agent)

    agents_info = orchestrator.get_agents()
    assert len(agents_info) == 3
    assert all("id" in a for a in agents_info)
