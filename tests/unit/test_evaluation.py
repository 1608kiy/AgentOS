"""评估框架测试"""

import pytest
from agentflow.agents.base import ReActAgent, AgentConfig
from agentflow.core.llm import MockLLMClient
from agentflow.core.evaluation import (
    EvalTask,
    EvalResult,
    EvalRunner,
    ContainsScorer,
    ExactMatchScorer,
    CompositeScorer,
    BENCHMARK_TASKS,
    create_eval_suite,
)


def test_eval_task():
    """测试评估任务"""
    task = EvalTask(name="test", input="hello", expected_output="world")
    assert task.name == "test"
    assert task.id is not None


def test_eval_result():
    """测试评估结果"""
    result = EvalResult(
        task_id="t1",
        task_name="test",
        agent_id="a1",
        agent_name="agent",
        actual_output="hello",
        score=0.8,
        passed=True,
    )
    assert result.passed is True
    assert result.score == 0.8


@pytest.mark.asyncio
async def test_contains_scorer():
    """测试包含匹配评分"""
    scorer = ContainsScorer()
    task = EvalTask(name="test", input="test", expected_contains=["hello", "world"])
    response = type("Response", (), {"content": "hello world how are you"})()

    score, details = await scorer.score(task, response)
    assert score == 1.0
    assert details["found"] == ["hello", "world"]


@pytest.mark.asyncio
async def test_contains_scorer_partial():
    """测试部分匹配"""
    scorer = ContainsScorer()
    task = EvalTask(name="test", input="test", expected_contains=["hello", "world", "foo"])
    response = type("Response", (), {"content": "hello world"})()

    score, details = await scorer.score(task, response)
    assert score == pytest.approx(2/3)


@pytest.mark.asyncio
async def test_exact_match_scorer():
    """测试精确匹配评分"""
    scorer = ExactMatchScorer()
    task = EvalTask(name="test", input="test", expected_output="hello world")

    response = type("Response", (), {"content": "hello world"})()
    score, _ = await scorer.score(task, response)
    assert score == 1.0

    response = type("Response", (), {"content": "goodbye"})()
    score, _ = await scorer.score(task, response)
    assert score == 0.0


@pytest.mark.asyncio
async def test_composite_scorer():
    """测试组合评分"""
    scorer = CompositeScorer([
        (ContainsScorer(), 0.6),
        (ExactMatchScorer(), 0.4),
    ])
    task = EvalTask(name="test", input="test", expected_contains=["hello"], expected_output="hello")
    response = type("Response", (), {"content": "hello"})()

    score, details = await scorer.score(task, response)
    assert score == 1.0


@pytest.mark.asyncio
async def test_eval_runner():
    """测试评估运行器"""
    agent = ReActAgent(config=AgentConfig(agent_name="TestAgent"))
    agent.llm = MockLLMClient()
    agent.llm.set_responses(["Python是一种编程语言", "答案是352"])

    runner = EvalRunner(agent=agent, scorer=ContainsScorer())

    tasks = [
        EvalTask(name="t1", input="什么是Python", expected_contains=["Python"]),
        EvalTask(name="t2", input="计算15*23+7", expected_contains=["352"]),
    ]

    report = await runner.run_suite(tasks)

    assert report.total_tasks == 2
    assert report.agent_name == "TestAgent"
    assert len(report.results) == 2


def test_benchmark_tasks():
    """测试基准任务集"""
    assert "general" in BENCHMARK_TASKS
    assert "coding" in BENCHMARK_TASKS
    assert "reasoning" in BENCHMARK_TASKS


def test_create_eval_suite():
    """测试创建评估套件"""
    tasks = create_eval_suite("general")
    assert len(tasks) > 0
    assert all(isinstance(t, EvalTask) for t in tasks)
