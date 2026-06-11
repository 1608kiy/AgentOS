"""FastAPI服务层 - 企业级增强版（依赖注入 + 认证）"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agentflow.core.config import load_env_if_needed
# 确保 .env 尽早写入 os.environ（解决 pydantic-settings v2 嵌套 Settings 不读 .env 的问题）
load_env_if_needed()

from agentflow.agents.base import (
    AgentConfig,
    AgentResponse,
    BaseAgent,
    CoderAgent,
    ContentFilterMiddleware,
    CostTrackerMiddleware,
    PlannerAgent,
    ReActAgent,
    ResearcherAgent,
    ReviewerAgent,
    SummarizerAgent,
)
from agentflow.api.auth import TokenData, UserRole, get_current_user, optional_auth, require_admin, create_access_token
from agentflow.core.config import AgentFlowConfig
from agentflow.tools.base import create_default_registry
from agentflow.workflow.engine import WorkflowBuilder, WorkflowDefinition, WorkflowEngine, DefaultNodeExecutor, NodeType
from agentflow.workflow.orchestrator import AgentOrchestrator, OrchestrationStrategy


# ============ 应用状态（依赖注入） ============

class AppState:
    """应用状态 - 通过依赖注入替代全局变量，支持多租户隔离"""

    def __init__(self) -> None:
        self.config = AgentFlowConfig()
        # 全局注册表（向后兼容 + admin 视图）
        self.agents: dict[str, BaseAgent] = {}
        self.workflows: dict[str, WorkflowDefinition] = {}
        # 多租户隔离：user_id -> {agent_id: agent}
        self._user_agents: dict[str, dict[str, BaseAgent]] = {}
        self._user_workflows: dict[str, dict[str, WorkflowDefinition]] = {}
        self.orchestrator = AgentOrchestrator()
        self.workflow_engine = WorkflowEngine()
        self.cost_tracker = CostTrackerMiddleware()
        self.tool_registry = create_default_registry()

        # 将工具注册到工作流引擎执行器
        self.workflow_executor = DefaultNodeExecutor()
        self.workflow_executor.set_tool_registry(self.tool_registry)
        self.workflow_engine.executor = self.workflow_executor

    def create_agent(self, agent_type: str, name: str, system_prompt: str = "", model: str = "", user_id: str = "") -> BaseAgent:
        """创建Agent（自动从全局配置继承 LLM provider/key/base_url，按 user_id 隔离）"""
        config = AgentConfig(
            agent_name=name,
            system_prompt=system_prompt,
            llm_provider=self.config.llm.provider,
            llm_model=model or self.config.llm.model,
            llm_api_key=self.config.llm.api_key,
            openai_base_url=self.config.llm.openai_base_url,
            anthropic_api_key=self.config.llm.anthropic_api_key,
            anthropic_base_url=self.config.llm.anthropic_base_url,
        )

        agent_map: dict[str, type[BaseAgent]] = {
            "react": ReActAgent,
            "planner": PlannerAgent,
            "researcher": ResearcherAgent,
            "coder": CoderAgent,
            "reviewer": ReviewerAgent,
            "summarizer": SummarizerAgent,
        }

        agent_class = agent_map.get(agent_type, ReActAgent)
        agent = agent_class(config=config, tools=self.tool_registry)

        # 注册中间件
        agent.add_middleware(ContentFilterMiddleware())
        agent.add_middleware(self.cost_tracker)

        # 全局注册
        self.agents[agent.id] = agent
        self.orchestrator.register_agent(agent)
        self.workflow_executor.register_agent(name, agent)

        # 租户隔离注册
        if user_id:
            if user_id not in self._user_agents:
                self._user_agents[user_id] = {}
            self._user_agents[user_id][agent.id] = agent

        return agent

    def get_user_agents(self, user_id: str) -> list[BaseAgent]:
        """获取指定用户的 Agent 列表。"""
        return list(self._user_agents.get(user_id, {}).values())

    def get_user_agent(self, user_id: str, agent_id: str) -> BaseAgent | None:
        """获取指定用户的 Agent（同时允许访问全局 Agent）。"""
        tenant = self._user_agents.get(user_id, {})
        return tenant.get(agent_id) or self.agents.get(agent_id)

    def delete_user_agent(self, user_id: str, agent_id: str) -> bool:
        """删除指定用户的 Agent。"""
        tenant = self._user_agents.get(user_id, {})
        if agent_id in tenant:
            del tenant[agent_id]
            self.agents.pop(agent_id, None)
            return True
        return False

    def save_user_workflow(self, user_id: str, wf: WorkflowDefinition) -> None:
        """保存用户的工作流。"""
        if user_id not in self._user_workflows:
            self._user_workflows[user_id] = {}
        self._user_workflows[user_id][wf.id] = wf
        self.workflows[wf.id] = wf

    def get_user_workflows(self, user_id: str) -> list[WorkflowDefinition]:
        """获取用户的工作流列表。"""
        return list(self._user_workflows.get(user_id, {}).values())


# 全局应用状态实例
_app_state: AppState | None = None


def get_app_state() -> AppState:
    global _app_state
    if _app_state is None:
        _app_state = AppState()
        import structlog
        logger = structlog.get_logger()
        llm = _app_state.config.llm
        logger.info("app_state_initialized",
                     provider=llm.provider.value,
                     model=llm.model,
                     base_url=llm.openai_base_url,
                     has_key=bool(llm.api_key))
    return _app_state


# ============ 生命周期 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    state = get_app_state()

    # 初始化OpenTelemetry
    try:
        from agentflow.core.otel import setup_opentelemetry
        setup_opentelemetry(service_name="agentflow-api", enabled=False)
    except Exception:
        pass

    yield
    state.agents.clear()
    state.workflows.clear()


# ============ FastAPI应用 ============

app = FastAPI(
    title="AgentFlow API",
    description="企业级多Agent协作平台API",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 增强API文档
try:
    from agentflow.api.docs import enhance_api_docs
    enhance_api_docs(app)
except Exception:
    pass

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 数据模型 ============

class ChatRequest(BaseModel):
    message: str
    agent_id: str | None = None
    strategy: str = "sequential"
    stream: bool = False


class ChatResponse(BaseModel):
    response: str
    agent_id: str
    duration_ms: float = 0.0
    token_usage: dict[str, int] = {}


class AgentCreateRequest(BaseModel):
    name: str
    agent_type: str = "react"
    system_prompt: str = ""
    model: str = ""  # 空则继承 .env 配置


class AgentInfo(BaseModel):
    id: str
    name: str
    type: str
    status: str
    token_usage: int = 0


class WorkflowCreateRequest(BaseModel):
    name: str
    description: str = ""
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    entry_node: str
    exit_nodes: list[str]


class WorkflowExecuteRequest(BaseModel):
    inputs: dict[str, Any] = {}


class OrchestrationRequest(BaseModel):
    task: str
    strategy: str = "sequential"
    agent_ids: list[str] | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ============ 认证API ============

@app.post("/api/v1/auth/token", response_model=TokenResponse)
async def login(request: LoginRequest):
    """获取JWT Token（简化版，生产环境应验证密码）"""
    if request.username == "admin" and request.password == "admin":
        token = create_access_token({"sub": request.username, "role": UserRole.ADMIN})
        return TokenResponse(access_token=token)
    raise HTTPException(status_code=401, detail="用户名或密码错误")


# ============ Agent API ============

@app.post("/api/v1/agents", response_model=AgentInfo)
async def create_agent(
    request: AgentCreateRequest,
    state: AppState = Depends(get_app_state),
    user: TokenData = Depends(get_current_user),
):
    """创建Agent（按 user_id 隔离）"""
    agent = state.create_agent(
        request.agent_type, request.name, request.system_prompt, request.model,
        user_id=user.user_id,
    )
    return AgentInfo(
        id=agent.id,
        name=agent.name,
        type=request.agent_type,
        status=agent.state.status.value,
        token_usage=agent.get_token_usage(),
    )


@app.get("/api/v1/agents", response_model=list[AgentInfo])
async def list_agents(
    state: AppState = Depends(get_app_state),
    user: TokenData = Depends(optional_auth),
):
    """列出当前用户的Agent"""
    agents = state.get_user_agents(user.user_id) if user.user_id != "anonymous" else list(state.agents.values())
    return [
        AgentInfo(
            id=agent.id,
            name=agent.name,
            type=type(agent).__name__,
            status=agent.state.status.value,
            token_usage=agent.get_token_usage(),
        )
        for agent in agents
    ]


@app.get("/api/v1/agents/{agent_id}", response_model=AgentInfo)
async def get_agent(
    agent_id: str,
    state: AppState = Depends(get_app_state),
    user: TokenData = Depends(optional_auth),
):
    agent = state.get_user_agent(user.user_id, agent_id) if user.user_id != "anonymous" else state.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent不存在")
    return AgentInfo(
        id=agent.id,
        name=agent.name,
        type=type(agent).__name__,
        status=agent.state.status.value,
        token_usage=agent.get_token_usage(),
    )


@app.delete("/api/v1/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    state: AppState = Depends(get_app_state),
    user: TokenData = Depends(require_admin),
):
    if agent_id not in state.agents:
        raise HTTPException(status_code=404, detail="Agent不存在")
    state.delete_user_agent(user.user_id, agent_id)
    return {"message": "Agent已删除"}


@app.post("/api/v1/agents/{agent_id}/run", response_model=ChatResponse)
async def run_agent(
    agent_id: str,
    request: ChatRequest,
    state: AppState = Depends(get_app_state),
    user: TokenData = Depends(get_current_user),
):
    agent = state.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent不存在")
    response = await agent.run(request.message)
    return ChatResponse(
        response=response.content,
        agent_id=agent_id,
        duration_ms=response.duration_ms,
        token_usage=response.token_usage,
    )


# ============ Chat API ============

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    state: AppState = Depends(get_app_state),
    user: TokenData = Depends(get_current_user),
):
    if request.agent_id:
        agent = state.agents.get(request.agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent不存在")
        response = await agent.run(request.message)
        return ChatResponse(
            response=response.content,
            agent_id=request.agent_id,
            duration_ms=response.duration_ms,
            token_usage=response.token_usage,
        )
    else:
        strategy_map = {
            "sequential": OrchestrationStrategy.SEQUENTIAL,
            "parallel": OrchestrationStrategy.PARALLEL,
            "debate": OrchestrationStrategy.DEBATE,
            "supervisor": OrchestrationStrategy.SUPERVISOR,
        }
        state.orchestrator.strategy = strategy_map.get(request.strategy, OrchestrationStrategy.SEQUENTIAL)
        result = await state.orchestrator.run(request.message)
        return ChatResponse(
            response=result.final_output,
            agent_id="orchestrator",
            duration_ms=result.duration_ms,
        )


@app.websocket("/api/v1/chat/stream")
async def chat_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            agent_id = data.get("agent_id")
            strategy = data.get("strategy", "sequential")

            if agent_id:
                # 单 Agent 流式
                state = get_app_state()
                agent = state.agents.get(agent_id)
                if not agent:
                    await websocket.send_json({"type": "error", "message": f"Agent不存在: {agent_id}"})
                    continue
                try:
                    async for event in _stream_agent(agent, message):
                        await websocket.send_json(event)
                except Exception as exc:
                    await websocket.send_json({"type": "error", "message": str(exc)})
            else:
                # 多 Agent 编排流式
                state = get_app_state()
                strategy_map = {
                    "sequential": OrchestrationStrategy.SEQUENTIAL,
                    "parallel": OrchestrationStrategy.PARALLEL,
                    "debate": OrchestrationStrategy.DEBATE,
                    "supervisor": OrchestrationStrategy.SUPERVISOR,
                }
                state.orchestrator.strategy = strategy_map.get(strategy, OrchestrationStrategy.SEQUENTIAL)
                try:
                    async for event in _stream_orchestrator(state.orchestrator, message):
                        await websocket.send_json(event)
                except Exception as exc:
                    await websocket.send_json({"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        pass


async def _stream_agent(agent: BaseAgent, message: str):
    """对单个 Agent 执行带工具调用的流式 ReAct 循环，逐事件 yield。"""
    import time

    start_time = time.perf_counter()
    token_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    agent.conversation.add_user(message)

    for _ in range(agent.state.max_iterations):
        agent.state.increment_iteration()

        # 单步推理
        response = await agent._step()
        agent._accumulate_usage(token_usage, response)
        agent._total_tokens += response.total_tokens

        tool_calls_raw = [agent._parse_tool_call(tc) for tc in response.tool_calls]
        tool_calls = [tc for tc in tool_calls_raw if tc is not None]

        if tool_calls:
            # 思考过程（模型可能输出文字 + 同时请求工具）
            if response.content:
                yield {"type": "thinking", "agent": agent.name, "content": response.content}
                agent.conversation.add_assistant(response.content)

            # 执行工具调用
            for tc in tool_calls:
                yield {"type": "tool_call", "agent": agent.name, "tool": tc.name, "args": tc.arguments}
                result = await agent._execute_tool(tc)
                agent.logger.log_agent_action(tc.name, result.content)
                agent.conversation.add_user(
                    f"[工具 {tc.name} 的结果]\n{result.content}"
                )
                yield {
                    "type": "tool_result",
                    "agent": agent.name,
                    "tool": tc.name,
                    "result": result.content,
                }
            continue

        # 无工具调用 → 最终答案
        answer = response.content
        if not answer:
            answer = await agent._generate_answer()
        else:
            agent.conversation.add_assistant(answer)

        duration = (time.perf_counter() - start_time) * 1000
        yield {"type": "answer", "agent": agent.name, "content": answer, "duration_ms": duration, "done": True}
        return

    # 达到最大迭代
    answer = await agent._generate_answer()
    duration = (time.perf_counter() - start_time) * 1000
    yield {"type": "answer", "agent": agent.name, "content": answer, "duration_ms": duration, "done": True}


async def _stream_orchestrator(orchestrator: AgentOrchestrator, task: str):
    """流式执行多 Agent 编排，对每个 Agent 逐事件 yield。"""
    import time

    start_time = time.perf_counter()
    agents = list(orchestrator.agents.keys())
    current_input = task
    final_output = ""
    got_answer = False

    for agent_id in agents:
        agent = orchestrator.agents.get(agent_id)
        if not agent:
            continue

        yield {"type": "thinking", "agent": agent.name, "content": "开始处理..."}
        try:
            async for event in _stream_agent(agent, current_input):
                yield event
                if event.get("type") == "answer":
                    current_input = event.get("content", "")
                    final_output = current_input
                    got_answer = True
        except Exception as exc:
            yield {"type": "error", "agent": agent.name, "message": str(exc)}

    if not got_answer:
        duration = (time.perf_counter() - start_time) * 1000
        yield {"type": "answer", "agent": "orchestrator", "content": final_output, "duration_ms": duration, "done": True}


# ============ Workflow API ============

@app.post("/api/v1/workflows")
async def create_workflow(
    request: WorkflowCreateRequest,
    state: AppState = Depends(get_app_state),
    user: TokenData = Depends(get_current_user),
):
    builder = WorkflowBuilder(request.name, request.description)
    for node_data in request.nodes:
        node_type = node_data.get("node_type", "agent")
        name = node_data.get("name", "")
        config = node_data.get("config", {})
        if node_type == "agent":
            builder.add_agent_node(name, config.get("agent_type", ""), config.get("task", ""))
        elif node_type == "tool":
            builder.add_tool_node(name, config.get("tool_name", ""), config.get("arguments", {}))
        elif node_type == "condition":
            builder.add_condition_node(name, config.get("condition", ""))
    builder.set_entry(request.entry_node)
    for exit_node in request.exit_nodes:
        builder.set_exit(exit_node)
    for edge in request.edges:
        builder.connect(edge.get("from_node", ""), edge.get("to_node", ""))
    workflow = builder.build()
    state.workflows[workflow.id] = workflow
    return {"id": workflow.id, "name": workflow.name, "status": "created"}


@app.get("/api/v1/workflows")
async def list_workflows(
    state: AppState = Depends(get_app_state),
    user: TokenData = Depends(optional_auth),
):
    return [{"id": wf.id, "name": wf.name, "description": wf.description} for wf in state.workflows.values()]


@app.post("/api/v1/workflows/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    request: WorkflowExecuteRequest,
    state: AppState = Depends(get_app_state),
    user: TokenData = Depends(get_current_user),
):
    workflow = state.workflows.get(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    context = await state.workflow_engine.execute(workflow, request.inputs)
    return {
        "workflow_id": workflow_id,
        "status": context.status,
        "outputs": context.outputs,
        "node_results": {k: v.model_dump() for k, v in context.node_results.items()},
    }


# ============ Orchestration API ============

@app.post("/api/v1/orchestrate")
async def orchestrate(
    request: OrchestrationRequest,
    state: AppState = Depends(get_app_state),
    user: TokenData = Depends(get_current_user),
):
    strategy_map = {
        "sequential": OrchestrationStrategy.SEQUENTIAL,
        "parallel": OrchestrationStrategy.PARALLEL,
        "debate": OrchestrationStrategy.DEBATE,
        "supervisor": OrchestrationStrategy.SUPERVISOR,
    }
    state.orchestrator.strategy = strategy_map.get(request.strategy, OrchestrationStrategy.SEQUENTIAL)
    result = await state.orchestrator.run(request.task, request.agent_ids)
    return result.to_dict()


# ============ 健康检查 ============

@app.get("/api/v1/health")
async def health_check(state: AppState = Depends(get_app_state)):
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "agents_count": len(state.agents),
        "workflows_count": len(state.workflows),
    }


@app.get("/api/v1/metrics")
async def metrics(
    state: AppState = Depends(get_app_state),
    user: TokenData = Depends(get_current_user),
):
    return {
        "agents": {
            "total": len(state.agents),
            "by_status": {
                s: sum(1 for a in state.agents.values() if a.state.status.value == s)
                for s in ["idle", "thinking", "acting", "waiting", "error", "completed"]
            },
        },
        "workflows": {"total": len(state.workflows)},
        "cost": state.cost_tracker.get_usage(),
    }


@app.get("/api/v1/costs")
async def get_costs(
    state: AppState = Depends(get_app_state),
    user: TokenData = Depends(get_current_user),
):
    """获取Token使用成本"""
    return {
        "total_by_agent": state.cost_tracker.get_usage(),
        "total_tokens": sum(state.cost_tracker.get_usage().values()),
    }


# ============ OpenAI 兼容工具 API（Codex / 其他 OpenAI 兼容工具） ============

@app.get("/api/v1/tools")
async def list_tools_openai_format(
    state: AppState = Depends(get_app_state),
):
    """列出所有工具（OpenAI function-calling schema 格式）。

    供 Codex / OpenAI 兼容工具直接使用。
    返回格式与 OpenAI tools 参数一致。
    """
    schemas = state.tool_registry.to_function_schemas()
    return [
        {"type": "function", "function": schema}
        for schema in schemas
    ]


class ToolCallRequest(BaseModel):
    """工具调用请求"""
    arguments: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/v1/tools/{tool_name}/call")
async def call_tool(
    tool_name: str,
    request: ToolCallRequest,
    state: AppState = Depends(get_app_state),
):
    """直接调用指定工具（供 Codex 等工具通过 HTTP 调用）。"""
    tool = state.tool_registry.get(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具不存在: {tool_name}")
    try:
        result = await tool.execute(**request.arguments)
        return {"tool": tool_name, "result": result, "is_error": False}
    except Exception as e:
        return {"tool": tool_name, "result": str(e), "is_error": True}
