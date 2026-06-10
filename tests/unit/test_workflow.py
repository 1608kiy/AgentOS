"""工作流引擎测试"""

import pytest
from agentflow.workflow.engine import (
    WorkflowDefinition,
    WorkflowNode,
    WorkflowEdge,
    WorkflowEngine,
    WorkflowBuilder,
    DefaultNodeExecutor,
    NodeType,
    NodeStatus,
)
from agentflow.agents.base import ReActAgent, AgentConfig
from agentflow.core.llm import MockLLMClient
from agentflow.tools.base import create_default_registry


def test_workflow_node():
    node = WorkflowNode(name="test", node_type=NodeType.AGENT, config={"agent_type": "react"})
    assert node.name == "test"
    assert node.node_type == NodeType.AGENT


def test_workflow_definition():
    workflow = WorkflowDefinition(name="test", description="test")
    n1 = WorkflowNode(name="start", node_type=NodeType.START)
    n2 = WorkflowNode(name="end", node_type=NodeType.END)
    workflow.add_node(n1)
    workflow.add_node(n2)
    workflow.add_edge(n1.id, n2.id)

    assert len(workflow.nodes) == 2
    assert len(workflow.edges) == 1


def test_workflow_validate():
    """测试工作流验证"""
    workflow = WorkflowDefinition(name="test")
    errors = workflow.validate()
    assert "缺少入口节点" in errors

    n1 = WorkflowNode(name="start", node_type=NodeType.START)
    workflow.add_node(n1)
    workflow.entry_node = n1.id
    errors = workflow.validate()
    assert "缺少出口节点" in errors


def test_workflow_builder():
    builder = WorkflowBuilder("test", "test workflow")
    builder.add_agent_node("planner", "planner", "Plan")
    builder.add_agent_node("executor", "react", "Execute")
    builder.connect("planner", "executor")
    builder.set_entry("planner")
    builder.set_exit("executor")

    workflow = builder.build()
    assert workflow.name == "test"
    assert len(workflow.nodes) == 2
    assert workflow.validate() == []


def test_workflow_builder_types():
    """测试各种节点类型"""
    builder = WorkflowBuilder("test")
    builder.add_agent_node("agent1", "react", "task")
    builder.add_tool_node("tool1", "calculator", {"expression": "1+1"})
    builder.add_condition_node("cond1", "result == 'yes'")
    builder.add_parallel_node("par1")
    builder.add_human_node("human1", "请审核")

    assert len(builder.workflow.nodes) == 5


@pytest.mark.asyncio
async def test_workflow_engine_with_real_agent():
    """测试工作流引擎 - 真实Agent执行"""
    executor = DefaultNodeExecutor()

    agent = ReActAgent(config=AgentConfig(agent_name="test_agent"))
    agent.llm = MockLLMClient()
    executor.register_agent("test_agent", agent)

    engine = WorkflowEngine(executor=executor)

    builder = WorkflowBuilder("test")
    builder.add_agent_node("step1", "test_agent", "Hello")
    builder.set_entry("step1")
    builder.set_exit("step1")

    workflow = builder.build()
    context = await engine.execute(workflow)

    assert context.status == "completed"
    assert len(context.node_results) == 1
    result = list(context.node_results.values())[0]
    assert result.node_name == "step1"


@pytest.mark.asyncio
async def test_workflow_engine_with_tool():
    """测试工作流引擎 - 工具执行"""
    executor = DefaultNodeExecutor()
    executor.set_tool_registry(create_default_registry())

    engine = WorkflowEngine(executor=executor)

    builder = WorkflowBuilder("test")
    builder.add_tool_node("calc", "calculator", {"expression": "2+3"})
    builder.set_entry("calc")
    builder.set_exit("calc")

    workflow = builder.build()
    context = await engine.execute(workflow)

    assert context.status == "completed"


@pytest.mark.asyncio
async def test_workflow_engine_condition():
    """测试条件节点"""
    executor = DefaultNodeExecutor()
    engine = WorkflowEngine(executor=executor)

    builder = WorkflowBuilder("test")
    builder.add_condition_node("check", "score > 80")
    builder.add_agent_node("pass", "agent", "通过")
    builder.add_agent_node("fail", "agent", "未通过")
    builder.connect("check", "pass", condition="true")
    builder.connect("check", "fail", condition="false")
    builder.set_entry("check")
    builder.set_exit("pass")
    builder.set_exit("fail")

    workflow = builder.build()
    context = await engine.execute(workflow, {"score": "90"})

    assert context.status == "completed"


@pytest.mark.asyncio
async def test_workflow_engine_human_node():
    """测试人工审核节点"""
    executor = DefaultNodeExecutor()
    engine = WorkflowEngine(executor=executor)

    builder = WorkflowBuilder("test")
    builder.add_human_node("review", "请审核此内容")
    builder.set_entry("review")
    builder.set_exit("review")

    workflow = builder.build()
    context = await engine.execute(workflow)

    assert context.status == "waiting"


def test_workflow_context():
    """测试工作流上下文"""
    from agentflow.workflow.engine import WorkflowContext
    context = WorkflowContext(workflow_id="test")
    context.set_variable("key", "value")
    assert context.get_variable("key") == "value"
    assert context.get_variable("missing", "default") == "default"


@pytest.mark.asyncio
async def test_workflow_resume_human_node():
    """测试 human 节点暂停后 resume 能继续执行后续节点（修复前为空壳）。"""
    executor = DefaultNodeExecutor()
    executor.set_tool_registry(create_default_registry())
    engine = WorkflowEngine(executor=executor)

    builder = WorkflowBuilder("resume_test")
    builder.add_human_node("review", "请审核")
    builder.add_tool_node("calc", "calculator", {"expression": "6*7"})
    builder.connect("review", "calc")
    builder.set_entry("review")
    builder.set_exit("calc")

    workflow = builder.build()
    context = await engine.execute(workflow)
    assert context.status == "waiting"
    assert context.waiting_node is not None

    # 恢复执行
    resumed = await engine.resume(context.id, human_input="同意")
    assert resumed.status == "completed"
    # 后续工具节点确实被执行
    calc_node = workflow.get_node_by_name("calc")
    assert calc_node.id in resumed.node_results
    assert resumed.node_results[calc_node.id].status == NodeStatus.COMPLETED
    assert "42" in str(resumed.node_results[calc_node.id].output)


@pytest.mark.asyncio
async def test_workflow_parallel_fan_out_fan_in():
    """测试并行 fan-out 后多分支汇聚（修复前并行节点必失败）。"""
    executor = DefaultNodeExecutor()
    executor.set_tool_registry(create_default_registry())
    engine = WorkflowEngine(executor=executor)

    builder = WorkflowBuilder("parallel_test")
    builder.add_parallel_node("split")
    builder.add_tool_node("a", "calculator", {"expression": "1+1"})
    builder.add_tool_node("b", "calculator", {"expression": "2+2"})
    builder.add_tool_node("join", "calculator", {"expression": "10+10"})
    builder.connect("split", "a")
    builder.connect("split", "b")
    builder.connect("a", "join")
    builder.connect("b", "join")
    builder.set_entry("split")
    builder.set_exit("join")

    workflow = builder.build()
    context = await engine.execute(workflow)

    assert context.status == "completed"
    # 两个并行分支都执行成功
    for name, expected in (("a", "2"), ("b", "4"), ("join", "20")):
        node = workflow.get_node_by_name(name)
        assert node.id in context.node_results
        assert context.node_results[node.id].status == NodeStatus.COMPLETED
        assert expected in str(context.node_results[node.id].output)


@pytest.mark.asyncio
async def test_workflow_condition_skips_branch():
    """测试条件分支：未命中的分支被跳过，不会执行。"""
    executor = DefaultNodeExecutor()
    executor.set_tool_registry(create_default_registry())
    engine = WorkflowEngine(executor=executor)

    builder = WorkflowBuilder("cond_test")
    builder.add_condition_node("check", "score > 80")
    builder.add_tool_node("pass_branch", "calculator", {"expression": "1+1"})
    builder.add_tool_node("fail_branch", "calculator", {"expression": "9+9"})
    builder.connect("check", "pass_branch", condition="true")
    builder.connect("check", "fail_branch", condition="false")
    builder.set_entry("check")
    builder.set_exit("pass_branch")
    builder.set_exit("fail_branch")

    workflow = builder.build()
    context = await engine.execute(workflow, {"score": "90"})

    assert context.status == "completed"
    pass_node = workflow.get_node_by_name("pass_branch")
    fail_node = workflow.get_node_by_name("fail_branch")
    # true 分支执行，false 分支被跳过
    assert context.node_results[pass_node.id].status == NodeStatus.COMPLETED
    assert context.node_results[fail_node.id].status == NodeStatus.SKIPPED
