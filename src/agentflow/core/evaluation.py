"""Agent评估框架"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field

from agentflow.agents.base import BaseAgent, AgentResponse


class EvalTask(BaseModel):
    """评估任务"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    input: str
    expected_output: str | None = None
    expected_contains: list[str] = Field(default_factory=list)
    max_iterations: int = 10
    timeout: float = 60.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalResult(BaseModel):
    """评估结果"""
    task_id: str
    task_name: str
    agent_id: str
    agent_name: str
    actual_output: str
    expected_output: str | None = None
    score: float = 0.0
    passed: bool = False
    duration_ms: float = 0.0
    iterations: int = 0
    token_usage: int = 0
    error: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class EvalReport(BaseModel):
    """评估报告"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_name: str
    total_tasks: int = 0
    passed: int = 0
    failed: int = 0
    avg_score: float = 0.0
    avg_duration_ms: float = 0.0
    total_tokens: int = 0
    results: list[EvalResult] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total_tasks if self.total_tasks > 0 else 0.0


class Scorer:
    """评分器基类"""

    async def score(self, task: EvalTask, response: AgentResponse) -> tuple[float, dict]:
        raise NotImplementedError


class ExactMatchScorer(Scorer):
    """精确匹配评分"""

    async def score(self, task: EvalTask, response: AgentResponse) -> tuple[float, dict]:
        if task.expected_output:
            match = response.content.strip() == task.expected_output.strip()
            return (1.0 if match else 0.0), {"exact_match": match}
        return 0.5, {"reason": "no_expected_output"}


class ContainsScorer(Scorer):
    """包含匹配评分"""

    async def score(self, task: EvalTask, response: AgentResponse) -> tuple[float, dict]:
        if not task.expected_contains:
            return 1.0, {"reason": "no_requirements"}

        content_lower = response.content.lower()
        found = [kw for kw in task.expected_contains if kw.lower() in content_lower]
        score = len(found) / len(task.expected_contains)
        return score, {"found": found, "total": len(task.expected_contains)}


class LLMScorer(Scorer):
    """LLM评分（使用另一个Agent评估）"""

    def __init__(self, judge_agent: BaseAgent | None = None):
        self._judge = judge_agent

    async def score(self, task: EvalTask, response: AgentResponse) -> tuple[float, dict]:
        if not self._judge:
            return 0.5, {"reason": "no_judge_agent"}

        prompt = (
            f"请评估以下AI回答的质量（0-10分）。\n\n"
            f"问题: {task.input}\n"
            f"期望回答: {task.expected_output or '无特定期望'}\n"
            f"实际回答: {response.content}\n\n"
            f"评分标准：准确性、完整性、相关性。\n"
            f"只输出数字分数，不要其他内容。"
        )

        try:
            judge_response = await self._judge.run(prompt)
            score_text = judge_response.content.strip()
            # 提取数字
            import re
            numbers = re.findall(r'\d+\.?\d*', score_text)
            if numbers:
                score = min(float(numbers[0]) / 10.0, 1.0)
                return score, {"judge_score": float(numbers[0]), "judge_response": score_text}
        except Exception:
            pass

        return 0.5, {"reason": "judge_failed"}


class CompositeScorer(Scorer):
    """组合评分器"""

    def __init__(self, scorers: list[tuple[Scorer, float]]):
        self._scorers = scorers  # (scorer, weight)

    async def score(self, task: EvalTask, response: AgentResponse) -> tuple[float, dict]:
        total_score = 0.0
        total_weight = 0.0
        details = {}

        for scorer, weight in self._scorers:
            score, info = await scorer.score(task, response)
            total_score += score * weight
            total_weight += weight
            details[type(scorer).__name__] = {"score": score, "weight": weight, **info}

        final_score = total_score / total_weight if total_weight > 0 else 0.0
        return final_score, details


class EvalRunner:
    """评估运行器"""

    def __init__(
        self,
        agent: BaseAgent,
        scorer: Scorer | None = None,
        parallel: bool = False,
    ):
        self.agent = agent
        self.scorer = scorer or CompositeScorer([
            (ContainsScorer(), 0.6),
            (ExactMatchScorer(), 0.4),
        ])
        self.parallel = parallel

    async def run_task(self, task: EvalTask) -> EvalResult:
        """运行单个评估任务"""
        start_time = time.perf_counter()

        try:
            response = await asyncio.wait_for(
                self.agent.run(task.input),
                timeout=task.timeout,
            )
            duration = (time.perf_counter() - start_time) * 1000

            score, details = await self.scorer.score(task, response)
            passed = score >= 0.7

            return EvalResult(
                task_id=task.id,
                task_name=task.name,
                agent_id=self.agent.id,
                agent_name=self.agent.name,
                actual_output=response.content,
                expected_output=task.expected_output,
                score=score,
                passed=passed,
                duration_ms=duration,
                iterations=response.iterations,
                token_usage=response.token_usage.get("total_tokens", 0),
                details=details,
            )
        except asyncio.TimeoutError:
            return EvalResult(
                task_id=task.id,
                task_name=task.name,
                agent_id=self.agent.id,
                agent_name=self.agent.name,
                actual_output="",
                score=0.0,
                passed=False,
                error="执行超时",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )
        except Exception as e:
            return EvalResult(
                task_id=task.id,
                task_name=task.name,
                agent_id=self.agent.id,
                agent_name=self.agent.name,
                actual_output="",
                score=0.0,
                passed=False,
                error=str(e),
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

    async def run_suite(self, tasks: list[EvalTask]) -> EvalReport:
        """运行评估套件"""
        if self.parallel:
            results = await asyncio.gather(*[self.run_task(t) for t in tasks])
        else:
            results = []
            for task in tasks:
                result = await self.run_task(task)
                results.append(result)

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        avg_score = sum(r.score for r in results) / len(results) if results else 0
        avg_duration = sum(r.duration_ms for r in results) / len(results) if results else 0
        total_tokens = sum(r.token_usage for r in results)

        return EvalReport(
            agent_name=self.agent.name,
            total_tasks=len(tasks),
            passed=passed,
            failed=failed,
            avg_score=avg_score,
            avg_duration_ms=avg_duration,
            total_tokens=total_tokens,
            results=list(results),
        )


# ============ 预置评估任务集 ============

BENCHMARK_TASKS = {
    "general": [
        EvalTask(name="简单问答", input="什么是Python？", expected_contains=["编程", "语言"]),
        EvalTask(name="数学计算", input="计算 15 * 23 + 7", expected_contains=["352"]),
        EvalTask(name="逻辑推理", input="如果所有的猫都是动物，所有的动物都需要食物，那么猫需要什么？", expected_contains=["食物"]),
        EvalTask(name="总结能力", input="用一句话总结：人工智能是计算机科学的一个分支，它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。", expected_contains=["人工智能", "智能"]),
    ],
    "coding": [
        EvalTask(name="代码生成", input="写一个Python函数，计算斐波那契数列第n项", expected_contains=["def", "fibonacci", "return"]),
        EvalTask(name="代码解释", input="解释这段代码的作用: def f(n): return n if n <= 1 else f(n-1) + f(n-2)", expected_contains=["递归", "斐波那契"]),
        EvalTask(name="Bug修复", input="找出这段代码的bug: def add(a, b): return a - b", expected_contains=["减号", "应该是加号", "+"]),
    ],
    "reasoning": [
        EvalTask(name="因果推理", input="小明今天没带伞，结果淋湿了。这说明什么？", expected_contains=["下雨", "伞"]),
        EvalTask(name="类比推理", input="医生:医院 = 教师:?", expected_contains=["学校"]),
    ],
}


def create_eval_suite(suite_name: str) -> list[EvalTask]:
    """获取预置评估任务集"""
    return BENCHMARK_TASKS.get(suite_name, BENCHMARK_TASKS["general"])
