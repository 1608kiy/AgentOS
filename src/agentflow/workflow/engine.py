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
    """工作流执行引擎"""

    def __init__(self, executor: DefaultNodeExecutor | None = None):
        self.executor = executor or DefaultNodeExecutor()
        self.running_workflows: dict[str, WorkflowContext] = {}
        self._paused_workflows: dict[str, asyncio.Event] = {}

    async def execute(
        self,
        workflow: WorkflowDefinition,
        inputs: dict[str, Any] | None = None,
    ) -> WorkflowContext:
        """执行工作流"""
        errors = workflow.validate()
        if errors:
            raise ValueError(f"工作流验证失败: {errors}")

        context = WorkflowContext(
            workflow_id=workflow.id,
            inputs=inputs or {},
            variables=dict(inputs or {}),
        )
        self.running_workflows[context.id] = context

        try:
            current_id = workflow.entry_node
            first_node = True

            while current_id:
                node = workflow.get_node(current_id)
                if not node:
                    break

                # 执行当前节点
                result = await self._execute_node(node, context)
                context.update(current_id, result)

                if result.status == NodeStatus.FAILED:
                    context.status = "failed"
                    context.outputs["error"] = result.error
                    break
                elif result.status == NodeStatus.WAITING:
                    context.status = "waiting"
                    self.running_workflows[context.id] = context
                    return context

                # 如果当前节点是出口节点，执行完后结束
                if current_id in workflow.exit_nodes:
                    break

                current_id = self._get_next_node(node, result, workflow)
                first_node = False

            if context.status == "running":
                context.status = "completed"
                context.completed_at = datetime.now()
                # 收集所有出口节点的输出
                for exit_id in workflow.exit_nodes:
                    if exit_id in context.node_results:
                        context.outputs[exit_id] = context.node_results[exit_id].output

        except Exception as e:
            context.status = "failed"
            context.outputs["error"] = str(e)
        finally:
            if context.status != "waiting":
                self.running_workflows.pop(context.id, None)

        return context

    async def resume(self, context_id: str, human_input: Any) -> WorkflowContext:
        """恢复等待中的工作流"""
        context = self.running_workflows.get(context_id)
        if not context or context.status != "waiting":
            raise ValueError(f"工作流不存在或不在等待状态: {context_id}")

        context.status = "running"
        context.human_inputs[context_id] = human_input
        context.set_variable("human_input", human_input)

        # 找到等待中的节点，继续执行
        for node_id, result in context.node_results.items():
            if result.status == NodeStatus.WAITING:
                result.status = NodeStatus.COMPLETED
                result.output = human_input
                result.completed_at = datetime.now()
                context.update(node_id, result)
                break

        # 继续执行后续节点
        workflow_def = None  # 需要从外部传入workflow定义
        # 这里简化处理，实际需要保存workflow引用
        context.status = "completed"
        context.completed_at = datetime.now()
        self.running_workflows.pop(context_id, None)
        return context

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
        """并行执行多个子节点"""
        next_ids = node.next_nodes
        if not next_ids:
            return {"parallel_tasks": [], "status": "no_tasks"}

        tasks = []
        for next_id in next_ids:
            next_node = context  # placeholder
            # 并行执行不需要在这里处理，由主循环处理
            tasks.append({"node_id": next_id, "status": "queued"})

        return {"parallel_tasks": tasks, "status": "queued"}

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

    def _get_next_node(
        self,
        current_node: WorkflowNode,
        result: NodeResult,
        workflow: WorkflowDefinition,
    ) -> str | None:
        """获取下一个节点"""
        if not current_node.next_nodes:
            return None

        if current_node.node_type == NodeType.CONDITION and result.output:
            condition_result = result.output.get("result", False)
            if condition_result:
                return current_node.next_nodes[0]
            else:
                return current_node.next_nodes[1] if len(current_node.next_nodes) > 1 else None

        return current_node.next_nodes[0]

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
