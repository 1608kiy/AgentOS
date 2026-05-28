"""Agent编排器 - 多Agent协作的核心"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from agentflow.agents.base import AgentConfig, AgentResponse, BaseAgent
from agentflow.core.message_bus import BusMessage, MessageBus, MessageType


class OrchestrationStrategy(str, Enum):
    """编排策略"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DEBATE = "debate"
    SUPERVISOR = "supervisor"


class OrchestrationResult(BaseModel):
    """编排结果"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    strategy: str
    task: str
    results: dict[str, Any] = Field(default_factory=dict)
    final_output: str = ""
    duration_ms: float = 0.0
    completed_at: datetime = Field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "strategy": self.strategy,
            "task": self.task,
            "results": self.results,
            "final_output": self.final_output,
            "duration_ms": self.duration_ms,
            "completed_at": self.completed_at.isoformat(),
        }


class AgentOrchestrator:
    """多Agent编排器"""

    def __init__(self, strategy: OrchestrationStrategy = OrchestrationStrategy.SEQUENTIAL):
        self.strategy = strategy
        self.agents: dict[str, BaseAgent] = {}
        self.message_bus = MessageBus()

    def register_agent(self, agent: BaseAgent) -> None:
        """注册Agent"""
        self.agents[agent.id] = agent
        self.message_bus.subscribe(agent.id, self._create_handler(agent))

    def register_agents(self, agents: list[BaseAgent]) -> None:
        """批量注册Agent"""
        for agent in agents:
            self.register_agent(agent)

    def _create_handler(self, agent: BaseAgent):
        """创建消息处理器"""
        async def handler(message: BusMessage):
            if message.message_type == MessageType.TASK_ASSIGN:
                result = await agent.run(message.content)
                await self.message_bus.respond(BusMessage(
                    from_agent=agent.id,
                    to_agent=message.from_agent,
                    message_type=MessageType.TASK_RESULT,
                    content=result.content,
                    correlation_id=message.correlation_id,
                ))
        return handler

    async def run(self, task: str, agent_ids: list[str] | None = None) -> OrchestrationResult:
        """执行编排"""
        import time
        start_time = time.perf_counter()

        agents = agent_ids or list(self.agents.keys())

        if self.strategy == OrchestrationStrategy.SEQUENTIAL:
            result = await self._run_sequential(agents, task)
        elif self.strategy == OrchestrationStrategy.PARALLEL:
            result = await self._run_parallel(agents, task)
        elif self.strategy == OrchestrationStrategy.DEBATE:
            result = await self._run_debate(agents, task)
        elif self.strategy == OrchestrationStrategy.SUPERVISOR:
            result = await self._run_supervisor(agents, task)
        else:
            raise ValueError(f"未知的编排策略: {self.strategy}")

        duration = (time.perf_counter() - start_time) * 1000
        result.duration_ms = duration
        return result

    async def _run_sequential(self, agent_ids: list[str], task: str) -> OrchestrationResult:
        """串行执行 - Agent链"""
        result = OrchestrationResult(
            strategy=OrchestrationStrategy.SEQUENTIAL.value,
            task=task,
        )

        current_input = task
        for agent_id in agent_ids:
            agent = self.agents.get(agent_id)
            if not agent:
                continue

            response = await agent.run(current_input)
            result.results[agent_id] = {
                "output": response.content,
                "iterations": response.iterations,
                "duration_ms": response.duration_ms,
            }
            current_input = response.content

        result.final_output = current_input
        return result

    async def _run_parallel(self, agent_ids: list[str], task: str) -> OrchestrationResult:
        """并行执行 - 多Agent同时工作"""
        result = OrchestrationResult(
            strategy=OrchestrationStrategy.PARALLEL.value,
            task=task,
        )

        async def run_agent(agent_id: str) -> tuple[str, AgentResponse]:
            agent = self.agents.get(agent_id)
            if not agent:
                return agent_id, AgentResponse(agent_id=agent_id, content="", iterations=0)
            response = await agent.run(task)
            return agent_id, response

        tasks = [run_agent(aid) for aid in agent_ids]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        outputs = []
        for resp in responses:
            if isinstance(resp, Exception):
                continue
            agent_id, response = resp
            result.results[agent_id] = {
                "output": response.content,
                "iterations": response.iterations,
                "duration_ms": response.duration_ms,
            }
            outputs.append(response.content)

        result.final_output = "\n\n---\n\n".join(outputs)
        return result

    async def _run_debate(self, agent_ids: list[str], topic: str, rounds: int = 3) -> OrchestrationResult:
        """辩论模式 - Agent互相讨论得出结论"""
        result = OrchestrationResult(
            strategy=OrchestrationStrategy.DEBATE.value,
            task=topic,
        )

        discussion = [f"讨论主题: {topic}"]

        for round_num in range(rounds):
            round_responses = []
            for agent_id in agent_ids:
                agent = self.agents.get(agent_id)
                if not agent:
                    continue

                context = "\n".join(discussion)
                prompt = f"第 {round_num + 1} 轮讨论:\n{context}\n\n请发表你的观点:"
                response = await agent.run(prompt)
                round_responses.append(f"[{agent.name}] {response.content}")

                result.results[f"{agent_id}_round{round_num + 1}"] = {
                    "output": response.content,
                    "round": round_num + 1,
                }

            discussion.extend(round_responses)

        # 最终总结
        if agent_ids:
            summarizer = self.agents.get(agent_ids[0])
            if summarizer:
                summary_prompt = f"请总结以下讨论结果，给出最终结论:\n\n{chr(10).join(discussion)}"
                summary = await summarizer.run(summary_prompt)
                result.final_output = summary.content

        return result

    async def _run_supervisor(self, agent_ids: list[str], task: str) -> OrchestrationResult:
        """主管模式 - Supervisor分配任务给Workers"""
        result = OrchestrationResult(
            strategy=OrchestrationStrategy.SUPERVISOR.value,
            task=task,
        )

        if len(agent_ids) < 2:
            raise ValueError("主管模式至少需要2个Agent")

        # 第一个Agent作为Supervisor
        supervisor_id = agent_ids[0]
        worker_ids = agent_ids[1:]

        supervisor = self.agents.get(supervisor_id)
        if not supervisor:
            raise ValueError(f"Supervisor不存在: {supervisor_id}")

        # Supervisor分解任务
        plan_prompt = (
            f"你是一个主管，需要将以下任务分配给团队成员。\n"
            f"团队成员: {', '.join(worker_ids)}\n"
            f"任务: {task}\n\n"
            f"请输出JSON格式的任务分配计划:\n"
            f'[{{"worker_id": "成员ID", "subtask": "子任务描述"}}]'
        )

        plan_response = await supervisor.run(plan_prompt)
        result.results[supervisor_id] = {"role": "supervisor", "plan": plan_response.content}

        # 解析任务分配
        try:
            content = plan_response.content
            start = content.find("[")
            end = content.rfind("]") + 1
            if start != -1 and end > start:
                assignments = json.loads(content[start:end])
            else:
                assignments = [{"worker_id": wid, "subtask": task} for wid in worker_ids]
        except Exception:
            assignments = [{"worker_id": wid, "subtask": task} for wid in worker_ids]

        # 分配并执行子任务
        subtask_results = {}
        for assignment in assignments:
            worker_id = assignment.get("worker_id", "")
            subtask = assignment.get("subtask", "")

            worker = self.agents.get(worker_id)
            if worker:
                worker_response = await worker.run(subtask)
                subtask_results[worker_id] = worker_response.content
                result.results[worker_id] = {
                    "role": "worker",
                    "subtask": subtask,
                    "output": worker_response.content,
                }

        # Supervisor汇总结果
        summary_prompt = (
            f"请汇总以下子任务的结果，生成最终报告:\n\n"
            f"原始任务: {task}\n\n"
            f"子任务结果:\n" +
            "\n".join(f"[{wid}] {output}" for wid, output in subtask_results.items())
        )

        summary = await supervisor.run(summary_prompt)
        result.final_output = summary.content

        return result

    def get_agents(self) -> list[dict[str, Any]]:
        """获取所有注册的Agent"""
        return [
            {
                "id": agent.id,
                "name": agent.name,
                "status": agent.state.status.value,
            }
            for agent in self.agents.values()
        ]
