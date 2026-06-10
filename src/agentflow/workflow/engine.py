"""工作流引擎 - 基于DAG的工作流编排（真实执行版）"""

from __future__ import annotations

import asyncio
import operator
import time
from datetime import datetime
from enum import Enum
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """节点类型"""
    AGENT = "agent"
    TOOL = "tool"
    CONDITION = "condition"
    PARALLEL = "parallel"
    HUMAN = "human"
    START = "start"
    END = "end"


class NodeStatus(str, Enum):
    """节点状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"


class WorkflowNode(BaseModel):
    """工作流节点"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    node_type: NodeType
    config: dict[str, Any] = Field(default_factory=dict)
    next_nodes: list[str] = Field(default_factory=list)
    condition: str | None = None
    timeout: float = 300.0

    model_config = {"arbitrary_types_allowed": True}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "node_type": self.node_type.value,
            "config": self.config,
            "next_nodes": self.next_nodes,
            "condition": self.condition,
        }


class WorkflowEdge(BaseModel):
    """工作流边"""
    from_node: str
    to_node: str
    condition: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_node": self.from_node,
            "to_node": self.to_node,
            "condition": self.condition,
        }


class WorkflowDefinition(BaseModel):
    """工作流定义"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    entry_node: str = ""
    exit_nodes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def get_node(self, node_id: str) -> WorkflowNode | None:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_node_by_name(self, name: str) -> WorkflowNode | None:
        for node in self.nodes:
            if node.name == name:
                return node
        return None

    def get_next_nodes(self, node_id: str) -> list[WorkflowNode]:
        node = self.get_node(node_id)
        if not node:
            return []
        return [n for nid in node.next_nodes if (n := self.get_node(nid))]

    def add_node(self, node: WorkflowNode) -> None:
        self.nodes.append(node)

    def add_edge(self, from_node: str, to_node: str, condition: str | None = None) -> None:
        edge = WorkflowEdge(from_node=from_node, to_node=to_node, condition=condition)
        self.edges.append(edge)
        node = self.get_node(from_node)
        if node and to_node not in node.next_nodes:
            node.next_nodes.append(to_node)

    def validate(self) -> list[str]:
        """验证工作流定义"""
        errors = []
        if not self.entry_node:
            errors.append("缺少入口节点")
        if not self.exit_nodes:
            errors.append("缺少出口节点")
        if not self.get_node(self.entry_node):
            errors.append(f"入口节点不存在: {self.entry_node}")
        for exit_id in self.exit_nodes:
            if not self.get_node(exit_id):
                errors.append(f"出口节点不存在: {exit_id}")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "entry_node": self.entry_node,
            "exit_nodes": self.exit_nodes,
        }


class NodeResult(BaseModel):
    """节点执行结果"""
    node_id: str
    node_name: str = ""
    status: NodeStatus
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None


class WorkflowContext(BaseModel):
    """工作流执行上下文"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_id: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    node_results: dict[str, NodeResult] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    status: str = "running"
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    human_inputs: dict[str, Any] = Field(default_factory=dict)
    # 边状态: "from_id->to_id" -> pending|activated|skipped（用于 DAG 调度与 resume 恢复）
    edge_states: dict[str, str] = Field(default_factory=dict)
    # 正在等待人工输入的节点 id（用于 resume 定位）
    waiting_node: str | None = None

    def update(self, node_id: str, result: NodeResult) -> None:
        self.node_results[node_id] = result
        if result.output is not None:
            self.variables[f"{node_id}_output"] = result.output
            self.variables[f"{result.node_name}_output"] = result.output

    def get_variable(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)

    def set_variable(self, key: str, value: Any) -> None:
        self.variables[key] = value


class NodeExecutor(Protocol):
    """节点执行器协议"""
    async def execute_agent(self, agent_type: str, task: str, config: dict[str, Any]) -> str: ...
    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> str: ...


class DefaultNodeExecutor:
    """默认节点执行器 - 通过注册表查找真实Agent/Tool"""

    def __init__(self) -> None:
        from agentflow.agents.base import BaseAgent
        from agentflow.tools.base import ToolRegistry

        self._agents: dict[str, BaseAgent] = {}
        self._tools: ToolRegistry | None = None

    def register_agent(self, name: str, agent: Any) -> None:
        self._agents[name] = agent

    def set_tool_registry(self, registry: Any) -> None:
        self._tools = registry

    async def execute_agent(self, agent_type: str, task: str, config: dict[str, Any]) -> str:
        agent = self._agents.get(agent_type)
        if not agent:
            # 尝试模糊匹配
            for name, a in self._agents.items():
                if agent_type.lower() in name.lower():
                    agent = a
                    break
        if not agent:
            return f"[错误] 未找到Agent: {agent_type}，已注册: {list(self._agents.keys())}"

        response = await agent.run(task)
        return response.content

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        if not self._tools:
            return f"[错误] 未设置工具注册表"
        tool = self._tools.get(tool_name)
        if not tool:
            return f"[错误] 未找到工具: {tool_name}"
        return await tool.execute(**arguments)


class WorkflowEngine:
    """工作流执行引擎 - 真正的 DAG 调度器

    通过节点入度 + 边状态驱动执行：每轮收集所有「就绪」节点（其所有入边都已确定）
    并发执行，支持 fan-out（一对多）、fan-in（多入边汇聚）、条件分支跳过传播，
    以及 human 节点暂停 / resume 恢复。
    """

    def __init__(self, executor: DefaultNodeExecutor | None = None):
        self.executor = executor or DefaultNodeExecutor()
        self.running_workflows: dict[str, WorkflowContext] = {}
        # 保存 workflow 定义引用，供 resume 与并行子节点访问
        self._workflows: dict[str, WorkflowDefinition] = {}

    async def execute(
        self,
        workflow: WorkflowDefinition,
        inputs: dict[str, Any] | None = None,
    ) -> WorkflowContext:
        """执行工作流（DAG 调度）"""
        errors = workflow.validate()
        if errors:
            raise ValueError(f"工作流验证失败: {errors}")

        context = WorkflowContext(
            workflow_id=workflow.id,
            inputs=inputs or {},
            variables=dict(inputs or {}),
        )
        self.running_workflows[context.id] = context
        self._workflows[context.id] = workflow

        return await self._drive(workflow, context)

    async def resume(self, context_id: str, human_input: Any) -> WorkflowContext:
        """恢复等待人工输入的工作流，从暂停点继续 DAG 调度。"""
        context = self.running_workflows.get(context_id)
        workflow = self._workflows.get(context_id)
        if not context or workflow is None or context.status != "waiting":
            raise ValueError(f"工作流不存在或不在等待状态: {context_id}")

        # 完成等待中的 human 节点
        waiting_id = context.waiting_node
        if waiting_id and waiting_id in context.node_results:
            result = context.node_results[waiting_id]
            result.status = NodeStatus.COMPLETED
            result.output = human_input
            result.completed_at = datetime.now()
            context.update(waiting_id, result)
            context.human_inputs[waiting_id] = human_input
            context.set_variable("human_input", human_input)
            # 激活该节点的出边，使后继节点进入就绪队列
            self._propagate(workflow, context, waiting_id, result)

        context.waiting_node = None
        context.status = "running"
        return await self._drive(workflow, context)

    async def _drive(self, workflow: WorkflowDefinition, context: WorkflowContext) -> WorkflowContext:
        """DAG 主调度循环：反复执行所有就绪节点，直到无可执行节点或进入等待。"""
        try:
            while True:
                ready = self._ready_nodes(workflow, context)
                if not ready:
                    break

                # 并发执行本轮所有就绪节点
                results = await asyncio.gather(
                    *[self._execute_node(node, context) for node in ready]
                )

                paused = False
                for node, result in zip(ready, results):
                    context.update(node.id, result)

                    if result.status == NodeStatus.WAITING:
                        context.status = "waiting"
                        context.waiting_node = node.id
                        paused = True
                        continue

                    if result.status == NodeStatus.FAILED:
                        context.status = "failed"
                        context.outputs["error"] = result.error
                        self.running_workflows.pop(context.id, None)
                        return context

                    # 激活/跳过出边，驱动后继节点
                    self._propagate(workflow, context, node.id, result)

                if paused:
                    # 保留在 running_workflows 中，等待 resume
                    return context

            if context.status == "running":
                context.status = "completed"
                context.completed_at = datetime.now()
                for exit_id in workflow.exit_nodes:
                    if exit_id in context.node_results:
                        context.outputs[exit_id] = context.node_results[exit_id].output

        except Exception as e:
            context.status = "failed"
            context.outputs["error"] = str(e)
        finally:
            if context.status not in ("waiting",):
                self.running_workflows.pop(context.id, None)

        return context

    def _incoming_edges(self, workflow: WorkflowDefinition, node_id: str) -> list[WorkflowEdge]:
        """节点的所有入边（兼容仅用 next_nodes 构建、未显式登记 edges 的工作流）。"""
        edges = [e for e in workflow.edges if e.to_node == node_id]
        if edges:
            return edges
        # 回退：从 next_nodes 推断入边
        inferred: list[WorkflowEdge] = []
        for n in workflow.nodes:
            if node_id in n.next_nodes:
                inferred.append(WorkflowEdge(from_node=n.id, to_node=node_id))
        return inferred

    def _ready_nodes(self, workflow: WorkflowDefinition, context: WorkflowContext) -> list[WorkflowNode]:
        """收集就绪节点：未执行过、且所有入边状态均已确定（activated/skipped）。

        - 入口节点无入边，首次即就绪。
        - fan-in 节点需等待全部入边确定；只要有一条 activated 边即执行，全 skipped 则跳过。
        """
        ready: list[WorkflowNode] = []
        for node in workflow.nodes:
            if node.id in context.node_results:
                continue  # 已执行

            incoming = self._incoming_edges(workflow, node.id)

            # 入口节点
            if not incoming:
                if node.id == workflow.entry_node:
                    ready.append(node)
                continue

            edge_states = [
                context.edge_states.get(f"{e.from_node}->{e.to_node}", "pending")
                for e in incoming
            ]
            if any(s == "pending" for s in edge_states):
                continue  # 还有入边未确定，暂不就绪

            if all(s == "skipped" for s in edge_states):
                # 所有上游都跳过 → 本节点也跳过，并向下传播跳过
                self._mark_skipped(workflow, context, node)
                continue

            ready.append(node)
        return ready

    def _mark_skipped(self, workflow: WorkflowDefinition, context: WorkflowContext, node: WorkflowNode) -> None:
        """将节点标记为跳过，并把其所有出边置为 skipped。"""
        context.node_results[node.id] = NodeResult(
            node_id=node.id,
            node_name=node.name,
            status=NodeStatus.SKIPPED,
            completed_at=datetime.now(),
        )
        for nid in node.next_nodes:
            context.edge_states[f"{node.id}->{nid}"] = "skipped"

    def _propagate(
        self,
        workflow: WorkflowDefinition,
        context: WorkflowContext,
        node_id: str,
        result: NodeResult,
    ) -> None:
        """根据节点执行结果，设置其出边为 activated 或 skipped。

        - 条件节点：result.output["result"] 为真走第一条出边，否则走第二条。
        - 普通节点：激活所有出边（fan-out）。
        """
        node = workflow.get_node(node_id)
        if not node or not node.next_nodes:
            return

        if node.node_type == NodeType.CONDITION:
            cond_true = bool(result.output and result.output.get("result", False))
            for i, nid in enumerate(node.next_nodes):
                # 约定：next_nodes[0] = true 分支, next_nodes[1] = false 分支
                activated = (i == 0 and cond_true) or (i == 1 and not cond_true)
                context.edge_states[f"{node_id}->{nid}"] = "activated" if activated else "skipped"
        else:
            for nid in node.next_nodes:
                context.edge_states[f"{node_id}->{nid}"] = "activated"

    async def _execute_node(self, node: WorkflowNode, context: WorkflowContext) -> NodeResult:
        """执行节点"""
        start_time = time.perf_counter()
        node_status = NodeStatus.RUNNING

        try:
            if node.node_type == NodeType.AGENT:
                output = await self._execute_agent_node(node, context)
            elif node.node_type == NodeType.TOOL:
                output = await self._execute_tool_node(node, context)
            elif node.node_type == NodeType.CONDITION:
                output = await self._evaluate_condition(node, context)
            elif node.node_type == NodeType.PARALLEL:
                output = await self._execute_parallel(node, context)
            elif node.node_type == NodeType.HUMAN:
                return await self._wait_for_human(node, context)
            elif node.node_type in (NodeType.START, NodeType.END):
                output = None
            else:
                output = None

            duration = (time.perf_counter() - start_time) * 1000
            return NodeResult(
                node_id=node.id,
                node_name=node.name,
                status=NodeStatus.COMPLETED,
                output=output,
                duration_ms=duration,
                completed_at=datetime.now(),
            )

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            return NodeResult(
                node_id=node.id,
                node_name=node.name,
                status=NodeStatus.FAILED,
                error=str(e),
                duration_ms=duration,
                completed_at=datetime.now(),
            )

    async def _execute_agent_node(self, node: WorkflowNode, context: WorkflowContext) -> Any:
        """执行Agent节点 - 真实调用"""
        agent_type = node.config.get("agent_type", node.name)
        task = self._resolve_variables(node.config.get("task", ""), context)
        extra_config = {k: v for k, v in node.config.items() if k not in ("agent_type", "task")}

        return await self.executor.execute_agent(agent_type, task, extra_config)

    async def _execute_tool_node(self, node: WorkflowNode, context: WorkflowContext) -> Any:
        """执行工具节点 - 真实调用"""
        tool_name = node.config.get("tool_name", node.name)
        raw_args = node.config.get("arguments", {})

        # 替换变量
        resolved_args = {}
        for key, value in raw_args.items():
            if isinstance(value, str):
                resolved_args[key] = self._resolve_variables(value, context)
            else:
                resolved_args[key] = value

        return await self.executor.execute_tool(tool_name, resolved_args)

    async def _evaluate_condition(self, node: WorkflowNode, context: WorkflowContext) -> Any:
        """评估条件 - 安全版"""
        condition = node.condition or node.config.get("condition", "true")
        resolved = self._resolve_variables(condition, context)

        # 安全的条件评估：只允许简单的比较操作
        allowed_operators = {
            "==": operator.eq,
            "!=": operator.ne,
            ">": operator.gt,
            "<": operator.lt,
            ">=": operator.ge,
            "<=": operator.le,
        }

        try:
            # 尝试解析简单的条件表达式
            for op_str, op_func in allowed_operators.items():
                if op_str in resolved:
                    parts = resolved.split(op_str, 1)
                    if len(parts) == 2:
                        left = parts[0].strip().strip("'\"")
                        right = parts[1].strip().strip("'\"")
                        # 尝试数值比较
                        try:
                            left_num = float(left)
                            right_num = float(right)
                            return {"condition": resolved, "result": op_func(left_num, right_num)}
                        except ValueError:
                            pass
                        # 字符串比较
                        return {"condition": resolved, "result": op_func(left, right)}

            # 布尔值
            if resolved.lower() in ("true", "1", "yes"):
                return {"condition": resolved, "result": True}
            elif resolved.lower() in ("false", "0", "no"):
                return {"condition": resolved, "result": False}

            return {"condition": resolved, "result": bool(resolved)}
        except Exception:
            return {"condition": resolved, "result": False}

    async def _execute_parallel(self, node: WorkflowNode, context: WorkflowContext) -> Any:
        """并行节点 - 作为 fan-out 标记。

        DAG 调度器会在本节点完成后激活其所有出边，使后继节点在同一调度轮次中并发执行，
        因此这里无需手动执行子节点（旧实现引用了不存在的 context.workflow_def，必失败）。
        """
        return {"status": "fan_out", "branches": list(node.next_nodes)}

    async def _wait_for_human(self, node: WorkflowNode, context: WorkflowContext) -> NodeResult:
        """等待人工输入"""
        prompt = node.config.get("prompt", "请提供输入")
        start_time = time.perf_counter()

        return NodeResult(
            node_id=node.id,
            node_name=node.name,
            status=NodeStatus.WAITING,
            output={"prompt": prompt, "status": "waiting_for_input"},
            duration_ms=(time.perf_counter() - start_time) * 1000,
        )

    def _resolve_variables(self, template: str, context: WorkflowContext) -> str:
        """解析模板中的变量引用"""
        result = template
        for key, value in context.variables.items():
            placeholder = "{" + key + "}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result

    def get_running_workflows(self) -> list[WorkflowContext]:
        return list(self.running_workflows.values())


class WorkflowBuilder:
    """工作流构建器"""

    def __init__(self, name: str, description: str = ""):
        self.workflow = WorkflowDefinition(name=name, description=description)
        self._node_map: dict[str, WorkflowNode] = {}

    def add_node(self, name: str, node_type: NodeType, config: dict[str, Any] | None = None) -> WorkflowBuilder:
        """添加通用节点"""
        node = WorkflowNode(name=name, node_type=node_type, config=config or {})
        self.workflow.add_node(node)
        self._node_map[name] = node
        return self

    def add_agent_node(self, name: str, agent_type: str, task: str, **kwargs: Any) -> WorkflowBuilder:
        """添加Agent节点"""
        return self.add_node(name, NodeType.AGENT, {"agent_type": agent_type, "task": task, **kwargs})

    def add_tool_node(self, name: str, tool_name: str, arguments: dict[str, Any] | None = None) -> WorkflowBuilder:
        """添加工具节点"""
        return self.add_node(name, NodeType.TOOL, {"tool_name": tool_name, "arguments": arguments or {}})

    def add_condition_node(self, name: str, condition: str) -> WorkflowBuilder:
        """添加条件节点"""
        return self.add_node(name, NodeType.CONDITION, {"condition": condition})

    def add_parallel_node(self, name: str) -> WorkflowBuilder:
        """添加并行节点"""
        return self.add_node(name, NodeType.PARALLEL)

    def add_human_node(self, name: str, prompt: str = "请提供输入") -> WorkflowBuilder:
        """添加人工审核节点"""
        return self.add_node(name, NodeType.HUMAN, {"prompt": prompt})

    def set_entry(self, node_name: str) -> WorkflowBuilder:
        node = self._node_map.get(node_name)
        if node:
            self.workflow.entry_node = node.id
        return self

    def set_exit(self, node_name: str) -> WorkflowBuilder:
        node = self._node_map.get(node_name)
        if node and node.id not in self.workflow.exit_nodes:
            self.workflow.exit_nodes.append(node.id)
        return self

    def connect(self, from_name: str, to_name: str, condition: str | None = None) -> WorkflowBuilder:
        from_node = self._node_map.get(from_name)
        to_node = self._node_map.get(to_name)
        if from_node and to_node:
            self.workflow.add_edge(from_node.id, to_node.id, condition)
        return self

    def build(self) -> WorkflowDefinition:
        return self.workflow
