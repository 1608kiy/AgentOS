"""性能基准测试"""

from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import Any

from agentflow.agents.base import ReActAgent, AgentConfig
from agentflow.core.llm import MockLLMClient
from agentflow.tools.base import CalculatorTool, ToolRegistry
from agentflow.workflow.engine import DefaultNodeExecutor, WorkflowBuilder, WorkflowEngine, NodeType
from agentflow.workflow.orchestrator import AgentOrchestrator, OrchestrationStrategy


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    throughput: float = 0.0  # ops/sec
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time_ms": round(self.total_time_ms, 2),
            "avg_time_ms": round(self.avg_time_ms, 2),
            "p50_ms": round(self.p50_ms, 2),
            "p95_ms": round(self.p95_ms, 2),
            "p99_ms": round(self.p99_ms, 2),
            "min_ms": round(self.min_ms, 2),
            "max_ms": round(self.max_ms, 2),
            "throughput": round(self.throughput, 2),
        }


def _calculate_stats(times: list[float]) -> dict[str, float]:
    """计算统计数据"""
    if not times:
        return {"avg": 0, "p50": 0, "p95": 0, "p99": 0, "min": 0, "max": 0}

    sorted_times = sorted(times)
    n = len(sorted_times)

    return {
        "avg": statistics.mean(sorted_times),
        "p50": sorted_times[int(n * 0.5)] if n > 0 else 0,
        "p95": sorted_times[int(n * 0.95)] if n > 1 else sorted_times[-1],
        "p99": sorted_times[int(n * 0.99)] if n > 2 else sorted_times[-1],
        "min": sorted_times[0],
        "max": sorted_times[-1],
    }


async def benchmark_agent_creation(iterations: int = 100) -> BenchmarkResult:
    """基准测试：Agent创建性能"""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        agent = ReActAgent(config=AgentConfig(agent_name="bench"))
        agent.llm = MockLLMClient()
        times.append((time.perf_counter() - start) * 1000)

    stats = _calculate_stats(times)
    return BenchmarkResult(
        name="Agent创建",
        iterations=iterations,
        total_time_ms=sum(times),
        avg_time_ms=stats["avg"],
        p50_ms=stats["p50"],
        p95_ms=stats["p95"],
        p99_ms=stats["p99"],
        min_ms=stats["min"],
        max_ms=stats["max"],
        throughput=iterations / (sum(times) / 1000) if sum(times) > 0 else 0,
    )


async def benchmark_agent_run(iterations: int = 20) -> BenchmarkResult:
    """基准测试：Agent执行性能"""
    agent = ReActAgent(config=AgentConfig(agent_name="bench", max_iterations=3))
    agent.llm = MockLLMClient()
    agent.llm.set_responses(["思考中...", "答案是42"])

    times = []
    for _ in range(iterations):
        agent.reset()
        start = time.perf_counter()
        await agent.run("测试任务")
        times.append((time.perf_counter() - start) * 1000)

    stats = _calculate_stats(times)
    return BenchmarkResult(
        name="Agent执行(MockLLM)",
        iterations=iterations,
        total_time_ms=sum(times),
        avg_time_ms=stats["avg"],
        p50_ms=stats["p50"],
        p95_ms=stats["p95"],
        p99_ms=stats["p99"],
        min_ms=stats["min"],
        max_ms=stats["max"],
        throughput=iterations / (sum(times) / 1000) if sum(times) > 0 else 0,
    )


async def benchmark_tool_execution(iterations: int = 100) -> BenchmarkResult:
    """基准测试：工具执行性能"""
    tool = CalculatorTool()
    times = []

    for i in range(iterations):
        start = time.perf_counter()
        await tool.execute(expression=f"{i} + {i} * 2")
        times.append((time.perf_counter() - start) * 1000)

    stats = _calculate_stats(times)
    return BenchmarkResult(
        name="工具执行(Calculator)",
        iterations=iterations,
        total_time_ms=sum(times),
        avg_time_ms=stats["avg"],
        p50_ms=stats["p50"],
        p95_ms=stats["p95"],
        p99_ms=stats["p99"],
        min_ms=stats["min"],
        max_ms=stats["max"],
        throughput=iterations / (sum(times) / 1000) if sum(times) > 0 else 0,
    )


async def benchmark_orchestrator(iterations: int = 10) -> BenchmarkResult:
    """基准测试：编排器性能"""
    orchestrator = AgentOrchestrator(strategy=OrchestrationStrategy.SEQUENTIAL)
    for i in range(3):
        agent = ReActAgent(config=AgentConfig(agent_name=f"agent_{i}"))
        agent.llm = MockLLMClient()
        orchestrator.register_agent(agent)

    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        await orchestrator.run("测试任务", agent_ids=list(orchestrator.agents.keys())[:3])
        times.append((time.perf_counter() - start) * 1000)

    stats = _calculate_stats(times)
    return BenchmarkResult(
        name="编排器(3 Agent串行)",
        iterations=iterations,
        total_time_ms=sum(times),
        avg_time_ms=stats["avg"],
        p50_ms=stats["p50"],
        p95_ms=stats["p95"],
        p99_ms=stats["p99"],
        min_ms=stats["min"],
        max_ms=stats["max"],
        throughput=iterations / (sum(times) / 1000) if sum(times) > 0 else 0,
    )


async def benchmark_workflow_engine(iterations: int = 10) -> BenchmarkResult:
    """基准测试：工作流引擎性能"""
    executor = DefaultNodeExecutor()
    agent = ReActAgent(config=AgentConfig(agent_name="wf_agent"))
    agent.llm = MockLLMClient()
    executor.register_agent("wf_agent", agent)
    executor.set_tool_registry(ToolRegistry())
    executor._tools.register(CalculatorTool())

    engine = WorkflowEngine(executor=executor)

    builder = WorkflowBuilder("bench")
    builder.add_agent_node("step1", "wf_agent", "task1")
    builder.add_tool_node("step2", "calculator", {"expression": "1+1"})
    builder.add_agent_node("step3", "wf_agent", "task3")
    builder.connect("step1", "step2")
    builder.connect("step2", "step3")
    builder.set_entry("step1")
    builder.set_exit("step3")
    workflow = builder.build()

    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        await engine.execute(workflow)
        times.append((time.perf_counter() - start) * 1000)

    stats = _calculate_stats(times)
    return BenchmarkResult(
        name="工作流引擎(3节点)",
        iterations=iterations,
        total_time_ms=sum(times),
        avg_time_ms=stats["avg"],
        p50_ms=stats["p50"],
        p95_ms=stats["p95"],
        p99_ms=stats["p99"],
        min_ms=stats["min"],
        max_ms=stats["max"],
        throughput=iterations / (sum(times) / 1000) if sum(times) > 0 else 0,
    )


async def run_all_benchmarks() -> list[BenchmarkResult]:
    """运行所有基准测试"""
    results = []
    results.append(await benchmark_agent_creation())
    results.append(await benchmark_agent_run())
    results.append(await benchmark_tool_execution())
    results.append(await benchmark_orchestrator())
    results.append(await benchmark_workflow_engine())
    return results


def format_benchmark_report(results: list[BenchmarkResult]) -> str:
    """格式化基准测试报告"""
    lines = [
        "=" * 80,
        "AgentFlow 性能基准测试报告",
        "=" * 80,
        "",
    ]

    for r in results:
        lines.extend([
            f"📊 {r.name}",
            f"   迭代次数: {r.iterations}",
            f"   平均耗时: {r.avg_time_ms:.2f}ms",
            f"   P50: {r.p50_ms:.2f}ms | P95: {r.p95_ms:.2f}ms | P99: {r.p99_ms:.2f}ms",
            f"   最小: {r.min_ms:.2f}ms | 最大: {r.max_ms:.2f}ms",
            f"   吞吐量: {r.throughput:.1f} ops/sec",
            "",
        ])

    lines.append("=" * 80)
    return "\n".join(lines)
