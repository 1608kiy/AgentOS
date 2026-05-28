"""性能基准测试"""

import pytest
from agentflow.core.benchmark import (
    BenchmarkResult,
    benchmark_agent_creation,
    benchmark_agent_run,
    benchmark_tool_execution,
    benchmark_orchestrator,
    benchmark_workflow_engine,
    run_all_benchmarks,
    format_benchmark_report,
)


@pytest.mark.asyncio
async def test_benchmark_agent_creation():
    """测试Agent创建基准"""
    result = await benchmark_agent_creation(iterations=10)
    assert result.name == "Agent创建"
    assert result.iterations == 10
    assert result.avg_time_ms > 0
    assert result.throughput > 0


@pytest.mark.asyncio
async def test_benchmark_agent_run():
    """测试Agent执行基准"""
    result = await benchmark_agent_run(iterations=5)
    assert result.name == "Agent执行(MockLLM)"
    assert result.iterations == 5


@pytest.mark.asyncio
async def test_benchmark_tool_execution():
    """测试工具执行基准"""
    result = await benchmark_tool_execution(iterations=20)
    assert result.name == "工具执行(Calculator)"
    assert result.iterations == 20


@pytest.mark.asyncio
async def test_benchmark_orchestrator():
    """测试编排器基准"""
    result = await benchmark_orchestrator(iterations=3)
    assert result.name == "编排器(3 Agent串行)"


@pytest.mark.asyncio
async def test_benchmark_workflow_engine():
    """测试工作流引擎基准"""
    result = await benchmark_workflow_engine(iterations=3)
    assert result.name == "工作流引擎(3节点)"


@pytest.mark.asyncio
async def test_run_all_benchmarks():
    """测试运行所有基准"""
    results = await run_all_benchmarks()
    assert len(results) == 5


def test_format_report():
    """测试报告格式化"""
    results = [
        BenchmarkResult(
            name="test",
            iterations=10,
            total_time_ms=100.0,
            avg_time_ms=10.0,
            p50_ms=9.0,
            p95_ms=15.0,
            p99_ms=18.0,
            min_ms=5.0,
            max_ms=20.0,
            throughput=100.0,
        )
    ]
    report = format_benchmark_report(results)
    assert "test" in report
    assert "10.00ms" in report


def test_benchmark_result_to_dict():
    """测试结果转字典"""
    result = BenchmarkResult(
        name="test",
        iterations=10,
        total_time_ms=100.0,
        avg_time_ms=10.0,
    )
    d = result.to_dict()
    assert d["name"] == "test"
    assert d["iterations"] == 10
