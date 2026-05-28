# AgentFlow — 企业级多Agent协作平台 蓝图

> **目标**: 构建一个可写进简历的、企业级的多Agent协作平台  
> **技术栈**: Python 3.11+ / LangGraph / FastAPI / Streamlit / Redis / SQLite  
> **预计工期**: 4-6周（每周10-15小时）

---

## 项目亮点（简历卖点）

1. **多Agent协作引擎** — 基于DAG的任务编排，支持串行/并行/条件分支
2. **可视化工作流设计器** — 拖拽式Agent编排UI
3. **企业级特性** — 完整的日志、监控、错误处理、重试机制
4. **真实业务场景** — 内置3个可演示的业务场景
5. **生产级架构** — 清晰的分层设计、设计模式、单元测试

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit UI Layer                        │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ 对话界面  │  │ 工作流设计器  │  │ 监控Dashboard      │    │
│  └──────────┘  └──────────────┘  └────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Service Layer                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Agent API │  │ Workflow │  │ Auth     │  │ WebSocket│   │
│  │          │  │ API      │  │ API      │  │ Streaming│   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Core Engine Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Agent        │  │ Workflow     │  │ Memory       │     │
│  │ Orchestrator │  │ Engine       │  │ Manager      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Tool         │  │ Message      │  │ Event        │     │
│  │ Registry     │  │ Bus          │  │ System       │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ SQLite   │  │ Redis    │  │ LLM      │  │ File     │   │
│  │ (持久化)  │  │ (缓存)   │  │ Clients  │  │ Storage  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 实施步骤

### Phase 1: 基础框架搭建（第1周）

#### Step 1.1: 项目初始化与目录结构
**依赖**: 无  
**模型**: default  
**文件**: `pyproject.toml`, `src/`, `tests/`

```
agentflow/
├── pyproject.toml          # 项目配置（uv/pip）
├── README.md               # 项目说明
├── docker-compose.yml      # Docker编排
├── Dockerfile              # 容器化
├── .env.example            # 环境变量模板
├── src/
│   └── agentflow/
│       ├── __init__.py
│       ├── core/           # 核心引擎
│       ├── agents/         # Agent实现
│       ├── tools/          # 工具系统
│       ├── memory/         # 记忆系统
│       ├── workflow/       # 工作流引擎
│       ├── api/            # FastAPI服务
│       ├── ui/             # Streamlit界面
│       └── utils/          # 工具函数
├── tests/
│   ├── unit/
│   └── integration/
├── examples/               # 示例场景
├── docs/                   # 文档
└── scripts/                # 脚本工具
```

**任务清单**:
- [ ] 初始化 `pyproject.toml`，配置依赖
- [ ] 创建目录结构
- [ ] 配置 `.env.example`
- [ ] 编写 `README.md`（项目介绍、快速开始）
- [ ] 配置 `Dockerfile` 和 `docker-compose.yml`

**验证命令**:
```bash
uv sync  # 或 pip install -e .
python -c "import agentflow; print('OK')"
```

---

#### Step 1.2: 配置管理系统
**依赖**: Step 1.1  
**模型**: default  
**文件**: `src/agentflow/core/config.py`

设计一个分层配置系统，支持：
- 环境变量覆盖
- YAML配置文件
- 多环境（dev/staging/prod）

```python
# 核心类设计
class AgentFlowConfig(BaseSettings):
    """主配置类"""
    app_name: str = "AgentFlow"
    environment: str = "development"
    
    # LLM配置
    llm_provider: str = "openai"  # openai/anthropic/local
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    
    # 数据库配置
    database_url: str = "sqlite:///./agentflow.db"
    redis_url: str = "redis://localhost:6379"
    
    # Agent配置
    max_iterations: int = 10
    timeout_seconds: int = 300
    
    class Config:
        env_file = ".env"
```

**任务清单**:
- [ ] 实现 `AgentFlowConfig` 类
- [ ] 实现配置验证和默认值
- [ ] 编写配置加载测试

---

#### Step 1.3: 日志与可观测性系统
**依赖**: Step 1.2  
**模型**: default  
**文件**: `src/agentflow/core/logging.py`, `src/agentflow/core/tracing.py`

企业级日志系统：
- 结构化JSON日志
- 请求链路追踪（Trace ID）
- Agent执行日志
- 性能指标收集

```python
# 核心设计
class AgentLogger:
    """Agent专用日志器"""
    def log_agent_start(self, agent_id: str, task: str): ...
    def log_agent_thinking(self, agent_id: str, thought: str): ...
    def log_agent_action(self, agent_id: str, action: str, result: str): ...
    def log_agent_error(self, agent_id: str, error: Exception): ...
    def log_agent_complete(self, agent_id: str, result: str): ...

class TracingManager:
    """链路追踪管理器"""
    def start_trace(self, trace_id: str): ...
    def add_span(self, name: str, metadata: dict): ...
    def end_trace(self): ...
```

**任务清单**:
- [ ] 实现 `AgentLogger` 类
- [ ] 实现 `TracingManager` 类
- [ ] 集成 `structlog` 或自定义日志
- [ ] 编写日志测试

---

### Phase 2: 核心引擎开发（第2-3周）

#### Step 2.1: LLM客户端抽象层
**依赖**: Step 1.2  
**模型**: default  
**文件**: `src/agentflow/core/llm.py`

统一的LLM调用接口，支持多provider切换：

```python
# 核心设计
class LLMClient(ABC):
    """LLM客户端抽象基类"""
    @abstractmethod
    async def chat(self, messages: list[Message], **kwargs) -> str: ...
    
    @abstractmethod
    async def stream_chat(self, messages: list[Message], **kwargs) -> AsyncIterator[str]: ...
    
    @abstractmethod
    async def function_call(self, messages: list[Message], functions: list[Function]) -> FunctionCall: ...

class OpenAIClient(LLMClient): ...
class AnthropicClient(LLMClient): ...
class LocalLLMClient(LLMClient): ...  # Ollama/llama.cpp

class LLMFactory:
    """LLM工厂类"""
    @staticmethod
    def create(provider: str, **kwargs) -> LLMClient: ...
```

**任务清单**:
- [ ] 定义 `LLMClient` 抽象接口
- [ ] 实现 `OpenAIClient`
- [ ] 实现 `AnthropicClient`
- [ ] 实现 `LLMFactory`
- [ ] 编写Mock测试

---

#### Step 2.2: 消息与状态系统
**依赖**: Step 2.1  
**模型**: default  
**文件**: `src/agentflow/core/message.py`, `src/agentflow/core/state.py`

定义Agent通信的消息格式和状态管理：

```python
# 消息系统
class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    metadata: dict = {}
    timestamp: datetime = Field(default_factory=datetime.now)

class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict

class ToolResult(BaseModel):
    call_id: str
    content: str
    is_error: bool = False

# 状态管理
class AgentState(BaseModel):
    agent_id: str
    messages: list[Message] = []
    working_memory: dict = {}
    status: Literal["idle", "thinking", "acting", "waiting", "error"] = "idle"
    iteration: int = 0
    max_iterations: int = 10
```

**任务清单**:
- [ ] 实现 `Message` 类层次
- [ ] 实现 `AgentState` 状态机
- [ ] 实现状态持久化接口
- [ ] 编写序列化测试

---

#### Step 2.3: 工具系统（Tool Registry）
**依赖**: Step 2.2  
**模型**: default  
**文件**: `src/agentflow/tools/base.py`, `src/agentflow/tools/registry.py`

可扩展的工具注册与调用系统：

```python
# 工具定义
class Tool(ABC):
    """工具抽象基类"""
    name: str
    description: str
    parameters: dict  # JSON Schema格式
    
    @abstractmethod
    async def execute(self, **kwargs) -> str: ...
    
    def to_function_schema(self) -> dict:
        """转换为LLM函数调用格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

# 工具注册表
class ToolRegistry:
    """工具注册中心"""
    def register(self, tool: Tool): ...
    def get(self, name: str) -> Tool: ...
    def list_tools(self) -> list[dict]: ...
    def to_function_schemas(self) -> list[dict]: ...

# 内置工具
class WebSearchTool(Tool): ...
class CalculatorTool(Tool): ...
class CodeExecutorTool(Tool): ...
class FileReadWriteTool(Tool): ...
class APICallTool(Tool): ...
```

**任务清单**:
- [ ] 定义 `Tool` 抽象接口
- [ ] 实现 `ToolRegistry`
- [ ] 实现5个内置工具
- [ ] 编写工具执行测试

---

#### Step 2.4: Agent基类与基础Agent
**依赖**: Step 2.1, 2.2, 2.3  
**模型**: default  
**文件**: `src/agentflow/agents/base.py`

Agent的核心抽象，支持ReAct模式：

```python
class BaseAgent(ABC):
    """Agent基类"""
    def __init__(self, config: AgentConfig):
        self.llm = LLMFactory.create(config.llm_provider)
        self.tools = ToolRegistry()
        self.state = AgentState(agent_id=config.agent_id)
        self.memory = MemoryManager()
        self.logger = AgentLogger(config.agent_id)
    
    async def run(self, task: str) -> str:
        """主执行循环 - ReAct模式"""
        self.state.add_message(Message(role="user", content=task))
        
        for i in range(self.state.max_iterations):
            # 1. Think - 思考下一步
            thought = await self.think()
            self.logger.log_agent_thinking(self.id, thought)
            
            # 2. Decide - 决定是否需要行动
            if self.should_answer(thought):
                answer = await self.generate_answer()
                self.logger.log_agent_complete(self.id, answer)
                return answer
            
            # 3. Act - 执行工具调用
            action = await self.decide_action(thought)
            result = await self.execute_action(action)
            self.logger.log_agent_action(self.id, action, result)
            
            # 4. Observe - 观察结果
            self.state.add_message(Message(role="tool", content=result))
        
        raise MaxIterationsError("Agent exceeded maximum iterations")
    
    @abstractmethod
    async def think(self) -> str: ...
    
    @abstractmethod
    async def decide_action(self, thought: str) -> Action: ...
    
    @abstractmethod
    async def generate_answer(self) -> str: ...

class ReActAgent(BaseAgent):
    """标准ReAct Agent实现"""
    ...
```

**任务清单**:
- [ ] 定义 `BaseAgent` 抽象类
- [ ] 实现 `ReActAgent`
- [ ] 实现Agent配置类
- [ ] 编写Agent执行测试

---

#### Step 2.5: 记忆系统（Memory Manager）
**依赖**: Step 2.2  
**模型**: default  
**文件**: `src/agentflow/memory/manager.py`, `src/agentflow/memory/short_term.py`, `src/agentflow/memory/long_term.py`

分层记忆系统：

```python
class ShortTermMemory:
    """短期记忆 - 对话上下文"""
    def __init__(self, max_tokens: int = 4000):
        self.messages: list[Message] = []
        self.max_tokens = max_tokens
    
    def add(self, message: Message): ...
    def get_context(self) -> list[Message]: ...
    def summarize_and_compress(self) -> str: ...

class LongTermMemory:
    """长期记忆 - 向量数据库"""
    def __init__(self, embedding_model: str = "text-embedding-3-small"):
        self.vector_store = Chroma(...)  # 或 FAISS
    
    def store(self, key: str, value: str, metadata: dict = {}): ...
    def retrieve(self, query: str, top_k: int = 5) -> list[Memory]: ...
    def forget(self, key: str): ...

class WorkingMemory:
    """工作记忆 - 当前任务上下文"""
    def __init__(self):
        self.scratch_pad: dict = {}
        self.task_stack: list[str] = []
        self.sub_goals: list[str] = []

class MemoryManager:
    """记忆管理器 - 统一接口"""
    def __init__(self):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        self.working = WorkingMemory()
    
    def remember(self, content: str, memory_type: str = "short"): ...
    def recall(self, query: str, memory_type: str = "all") -> list: ...
    def consolidate(self): ...  # 短期 -> 长期
```

**任务清单**:
- [ ] 实现 `ShortTermMemory`
- [ ] 实现 `LongTermMemory`（向量存储）
- [ ] 实现 `WorkingMemory`
- [ ] 实现 `MemoryManager` 统一接口
- [ ] 编写记忆测试

---

### Phase 3: 多Agent协作引擎（第3-4周）

#### Step 3.1: Agent通信总线（Message Bus）
**依赖**: Step 2.4  
**模型**: default  
**文件**: `src/agentflow/core/message_bus.py`

Agent间通信基础设施：

```python
class MessageType(Enum):
    TASK_ASSIGN = "task_assign"
    TASK_RESULT = "task_result"
    REQUEST = "request"
    RESPONSE = "response"
    BROADCAST = "broadcast"
    ERROR = "error"

class AgentMessage(BaseModel):
    from_agent: str
    to_agent: str | None  # None = broadcast
    message_type: MessageType
    content: Any
    correlation_id: str  # 用于追踪请求-响应

class MessageBus:
    """Agent间消息总线"""
    def __init__(self):
        self.subscribers: dict[str, list[Callable]] = {}
        self.message_history: list[AgentMessage] = []
    
    async def publish(self, message: AgentMessage): ...
    def subscribe(self, agent_id: str, handler: Callable): ...
    async def request(self, from_agent: str, to_agent: str, content: Any) -> Any: ...
```

**任务清单**:
- [ ] 实现 `AgentMessage` 类型
- [ ] 实现 `MessageBus` 发布-订阅
- [ ] 实现请求-响应模式
- [ ] 编写消息总线测试

---

#### Step 3.2: 工作流引擎（Workflow Engine）
**依赖**: Step 3.1  
**模型**: opus（架构关键）  
**文件**: `src/agentflow/workflow/engine.py`, `src/agentflow/workflow/graph.py`

基于DAG的工作流编排引擎：

```python
class NodeType(Enum):
    AGENT = "agent"        # Agent节点
    TOOL = "tool"          # 工具节点
    CONDITION = "condition" # 条件分支
    PARALLEL = "parallel"  # 并行执行
    HUMAN = "human"        # 人工审核

class WorkflowNode(BaseModel):
    id: str
    node_type: NodeType
    config: dict  # 节点配置
    next_nodes: list[str] = []  # 下游节点
    condition: str | None = None  # 条件表达式

class WorkflowEdge(BaseModel):
    from_node: str
    to_node: str
    condition: str | None = None

class WorkflowDefinition(BaseModel):
    id: str
    name: str
    description: str
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    entry_node: str
    exit_nodes: list[str]

class WorkflowEngine:
    """工作流执行引擎"""
    def __init__(self, message_bus: MessageBus):
        self.bus = message_bus
        self.running_workflows: dict[str, WorkflowContext] = {}
    
    async def execute(self, workflow: WorkflowDefinition, inputs: dict) -> dict:
        """执行工作流"""
        context = WorkflowContext(workflow, inputs)
        self.running_workflows[context.id] = context
        
        # 从入口节点开始
        current = workflow.entry_node
        
        while current not in workflow.exit_nodes:
            node = workflow.get_node(current)
            
            # 根据节点类型执行
            if node.node_type == NodeType.AGENT:
                result = await self.execute_agent_node(node, context)
            elif node.node_type == NodeType.TOOL:
                result = await self.execute_tool_node(node, context)
            elif node.node_type == NodeType.CONDITION:
                result = await self.evaluate_condition(node, context)
            elif node.node_type == NodeType.PARALLEL:
                result = await self.execute_parallel(node, context)
            elif node.node_type == NodeType.HUMAN:
                result = await self.wait_for_human(node, context)
            
            context.update(node.id, result)
            current = self.get_next_node(node, result, workflow)
        
        return context.outputs
    
    async def execute_parallel(self, node: WorkflowNode, context: WorkflowContext):
        """并行执行多个节点"""
        tasks = [self.execute_node(n, context) for n in node.next_nodes]
        return await asyncio.gather(*tasks)
```

**任务清单**:
- [ ] 定义 `WorkflowNode`, `WorkflowEdge` 数据模型
- [ ] 实现 `WorkflowDefinition` 解析
- [ ] 实现 `WorkflowEngine` 执行引擎
- [ ] 实现并行执行逻辑
- [ ] 实现条件分支逻辑
- [ ] 编写工作流测试

---

#### Step 3.3: Agent编排器（Orchestrator）
**依赖**: Step 3.1, 3.2  
**模型**: opus  
**文件**: `src/agentflow/core/orchestrator.py`

多Agent协作的核心编排逻辑：

```python
class OrchestrationStrategy(Enum):
    SEQUENTIAL = "sequential"  # 串行执行
    PARALLEL = "parallel"      # 并行执行
    DEBATE = "debate"          # 辩论模式
    SUPERVISOR = "supervisor"  # 主管模式
    HIERARCHICAL = "hierarchical"  # 层级模式

class AgentOrchestrator:
    """多Agent编排器"""
    def __init__(self, strategy: OrchestrationStrategy):
        self.strategy = strategy
        self.agents: dict[str, BaseAgent] = {}
        self.message_bus = MessageBus()
        self.workflow_engine = WorkflowEngine(self.message_bus)
    
    def register_agent(self, agent: BaseAgent):
        """注册Agent"""
        self.agents[agent.id] = agent
        self.message_bus.subscribe(agent.id, agent.handle_message)
    
    async def run_sequential(self, agents: list[str], task: str) -> str:
        """串行执行 - Agent链"""
        result = task
        for agent_id in agents:
            agent = self.agents[agent_id]
            result = await agent.run(result)
        return result
    
    async def run_parallel(self, agents: list[str], task: str) -> list[str]:
        """并行执行 - 多Agent同时工作"""
        tasks = [self.agents[aid].run(task) for aid in agents]
        return await asyncio.gather(*tasks)
    
    async def run_debate(self, agents: list[str], topic: str, rounds: int = 3) -> str:
        """辩论模式 - Agent互相讨论得出结论"""
        discussion = [topic]
        for round_num in range(rounds):
            responses = []
            for agent_id in agents:
                agent = self.agents[agent_id]
                context = "\n".join(discussion)
                response = await agent.run(f"Round {round_num + 1}: {context}")
                responses.append(response)
            discussion.extend(responses)
        
        # 最终总结
        summarizer = self.agents[agents[0]]
        return await summarizer.run(f"总结讨论结果: {discussion}")
    
    async def run_supervisor(self, supervisor: str, workers: list[str], task: str) -> str:
        """主管模式 - Supervisor分配任务给Workers"""
        supervisor_agent = self.agents[supervisor]
        
        # Supervisor分解任务
        plan = await supervisor_agent.run(
            f"将以下任务分解为子任务，分配给可用的Worker: {task}\n"
            f"可用Workers: {workers}\n"
            f"输出JSON格式的子任务分配计划"
        )
        
        subtasks = json.loads(plan)
        results = {}
        
        # 分配并执行子任务
        for subtask in subtasks:
            worker_id = subtask["assigned_to"]
            worker = self.agents[worker_id]
            result = await worker.run(subtask["task"])
            results[subtask["id"]] = result
        
        # Supervisor汇总结果
        return await supervisor_agent.run(
            f"汇总以下子任务结果: {json.dumps(results, ensure_ascii=False)}"
        )
```

**任务清单**:
- [ ] 实现 `OrchestrationStrategy` 枚举
- [ ] 实现串行执行
- [ ] 实现并行执行
- [ ] 实现辩论模式
- [ ] 实现主管模式
- [ ] 编写编排器测试

---

#### Step 3.4: 预置Agent实现
**依赖**: Step 2.4  
**模型**: default  
**文件**: `src/agentflow/agents/`

实现几个可复用的专业Agent：

```python
class PlannerAgent(BaseAgent):
    """规划Agent - 任务分解"""
    system_prompt = """你是一个任务规划专家。你的职责是：
    1. 分析复杂任务
    2. 将其分解为可执行的子任务
    3. 确定子任务间的依赖关系
    4. 输出结构化的执行计划"""
    
    async def plan(self, task: str) -> ExecutionPlan: ...

class ResearcherAgent(BaseAgent):
    """研究Agent - 信息收集"""
    system_prompt = """你是一个信息研究专家。你的职责是：
    1. 使用搜索工具收集信息
    2. 验证信息的可靠性
    3. 整理和总结发现
    4. 提供有据可查的结论"""
    
    tools = [WebSearchTool(), FileReadWriteTool()]

class CoderAgent(BaseAgent):
    """编码Agent - 代码生成"""
    system_prompt = """你是一个编程专家。你的职责是：
    1. 理解编码需求
    2. 编写高质量的代码
    3. 进行代码审查
    4. 编写测试用例"""
    
    tools = [CodeExecutorTool(), FileReadWriteTool()]

class ReviewerAgent(BaseAgent):
    """审查Agent - 质量检查"""
    system_prompt = """你是一个质量审查专家。你的职责是：
    1. 审查代码/文档质量
    2. 发现潜在问题
    3. 提供改进建议
    4. 验证是否符合标准"""

class SummarizerAgent(BaseAgent):
    """总结Agent - 信息整合"""
    system_prompt = """你是一个信息整合专家。你的职责是：
    1. 理解多个输入源的信息
    2. 识别关键要点
    3. 生成清晰简洁的总结
    4. 突出重要发现"""
```

**任务清单**:
- [ ] 实现 `PlannerAgent`
- [ ] 实现 `ResearcherAgent`
- [ ] 实现 `CoderAgent`
- [ ] 实现 `ReviewerAgent`
- [ ] 实现 `SummarizerAgent`
- [ ] 编写Agent单元测试

---

### Phase 4: 业务场景实现（第4周）

#### Step 4.1: 场景1 - 智能客服系统
**依赖**: Step 3.3, 3.4  
**模型**: default  
**文件**: `examples/customer_service/`

多Agent协作的客服场景：

```
用户咨询 → Router Agent（意图识别）
                ↓
    ┌───────────┼───────────┐
    ↓           ↓           ↓
Order Agent  Tech Agent  Sales Agent
(订单查询)   (技术支持)   (销售咨询)
    ↓           ↓           ↓
    └───────────┼───────────┘
                ↓
         Summary Agent（总结回复）
```

**任务清单**:
- [ ] 定义客服工作流
- [ ] 实现Router Agent（意图路由）
- [ ] 实现Order Agent（订单查询）
- [ ] 实现Tech Agent（技术支持）
- [ ] 实现Sales Agent（销售咨询）
- [ ] 编写集成测试

---

#### Step 4.2: 场景2 - 代码审查助手
**依赖**: Step 3.3, 3.4  
**模型**: default  
**文件**: `examples/code_review/`

多Agent协作的代码审查场景：

```
提交代码 → Security Agent（安全扫描）
              ↓
         Quality Agent（质量检查）
              ↓
         Performance Agent（性能分析）
              ↓
         Reviewer Agent（综合评审）
              ↓
         生成审查报告
```

**任务清单**:
- [ ] 定义代码审查工作流
- [ ] 实现Security Agent
- [ ] 实现Quality Agent
- [ ] 实现Performance Agent
- [ ] 实现审查报告生成
- [ ] 编写集成测试

---

#### Step 4.3: 场景3 - 数据分析流水线
**依赖**: Step 3.3, 3.4  
**模型**: default  
**文件**: `examples/data_analysis/`

多Agent协作的数据分析场景：

```
分析需求 → Planner Agent（分析规划）
              ↓
         Data Agent（数据提取）
              ↓
         Analyst Agent（数据分析）
              ↓
         Visualizer Agent（可视化）
              ↓
         Reporter Agent（报告生成）
```

**任务清单**:
- [ ] 定义数据分析工作流
- [ ] 实现Data Agent
- [ ] 实现Analyst Agent
- [ ] 实现Visualizer Agent
- [ ] 实现Reporter Agent
- [ ] 编写集成测试

---

### Phase 5: API与UI层（第5周）

#### Step 5.1: FastAPI服务层
**依赖**: Step 3.3  
**模型**: default  
**文件**: `src/agentflow/api/`

RESTful API + WebSocket实时通信：

```python
# API端点设计
POST /api/v1/agents                    # 创建Agent
GET  /api/v1/agents                    # 列出Agent
POST /api/v1/agents/{id}/run           # 运行Agent

POST /api/v1/workflows                 # 创建工作流
GET  /api/v1/workflows                 # 列出工作流
POST /api/v1/workflows/{id}/execute    # 执行工作流

POST /api/v1/chat                      # 对话接口
WS   /api/v1/chat/stream               # 流式对话

GET  /api/v1/health                    # 健康检查
GET  /api/v1/metrics                   # 指标数据
```

**任务清单**:
- [ ] 实现Agent API端点
- [ ] 实现Workflow API端点
- [ ] 实现Chat API（含WebSocket）
- [ ] 实现认证中间件
- [ ] 编写API测试

---

#### Step 5.2: Streamlit UI
**依赖**: Step 5.1  
**模型**: default  
**文件**: `src/agentflow/ui/`

三个主要页面：

1. **对话界面** — 与Agent交互
2. **工作流设计器** — 可视化编排Agent
3. **监控面板** — 查看执行状态和日志

**任务清单**:
- [ ] 实现对话界面
- [ ] 实现工作流设计器（拖拽）
- [ ] 实现监控面板
- [ ] 实现流式输出显示

---

### Phase 6: 测试与部署（第6周）

#### Step 6.1: 测试覆盖
**依赖**: 所有步骤  
**模型**: default  
**文件**: `tests/`

测试策略：
- 单元测试：核心组件
- 集成测试：Agent协作
- 端到端测试：完整场景

**任务清单**:
- [ ] 编写核心组件单元测试
- [ ] 编写Agent集成测试
- [ ] 编写工作流集成测试
- [ ] 编写API端到端测试
- [ ] 达到80%+测试覆盖率

---

#### Step 6.2: Docker部署
**依赖**: Step 6.1  
**模型**: default  
**文件**: `Dockerfile`, `docker-compose.yml`

容器化部署方案：

```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///./data/agentflow.db
      - REDIS_URL=redis://redis:6379
  
  ui:
    build: .
    command: streamlit run src/agentflow/ui/app.py
    ports:
      - "8501:8501"
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

**任务清单**:
- [ ] 编写Dockerfile
- [ ] 编写docker-compose.yml
- [ ] 编写部署文档
- [ ] 测试容器化部署

---

#### Step 6.3: 文档完善
**依赖**: 所有步骤  
**模型**: default  
**文件**: `docs/`, `README.md`

文档清单：
- [ ] README.md（项目介绍、快速开始、架构图）
- [ ] API文档（自动生成）
- [ ] 开发指南
- [ ] 部署指南
- [ ] 示例教程

---

## 关键设计决策

### 1. 为什么选择LangGraph而不是原生实现？
- LangGraph提供了成熟的图执行引擎
- 内置持久化、流式输出、人机协作
- 简历加分：展示对主流框架的掌握

### 2. 为什么用FastAPI而不是Flask？
- 异步支持，适合Agent并发执行
- 自动生成OpenAPI文档
- WebSocket原生支持
- 简历加分：展示现代Python API开发能力

### 3. 为什么用Streamlit而不是React？
- Python全栈，降低学习成本
- 快速原型开发
- 丰富的组件库
- 简历加分：展示全栈能力

### 4. 为什么用SQLite而不是PostgreSQL？
- 零配置，开箱即用
- 单文件部署
- 足够支撑演示和小规模使用
- 可平滑迁移到PostgreSQL

---

## 简历描述模板

```
AgentFlow - 企业级多Agent协作平台

技术栈：Python 3.11, LangGraph, FastAPI, Streamlit, Redis, SQLite

项目描述：
设计并实现了一个企业级多Agent协作平台，支持多种Agent协作模式
（串行、并行、辩论、主管模式），内置可视化工作流设计器和实时
监控面板。

核心贡献：
• 基于DAG的工作流引擎，支持条件分支和并行执行
• 可扩展的工具注册系统，支持动态加载和热插拔
• 分层记忆系统（短期/长期/工作记忆），支持上下文管理和知识持久化
• 3个完整业务场景：智能客服、代码审查、数据分析
• 结构化日志和链路追踪，支持生产级可观测性
• Docker容器化部署，支持一键启动

技术亮点：
• ReAct模式Agent实现，支持多轮推理和工具调用
• 发布-订阅消息总线，实现Agent间松耦合通信
• 可视化工作流设计器，支持拖拽式Agent编排
• WebSocket流式输出，实时展示Agent思考过程
```

---

## 依赖清单

```toml
[project]
dependencies = [
    "langgraph>=0.2.0",
    "langchain>=0.3.0",
    "langchain-openai>=0.2.0",
    "langchain-anthropic>=0.2.0",
    "fastapi>=0.115.0",
    "uvicorn>=0.32.0",
    "streamlit>=1.40.0",
    "pydantic>=2.9.0",
    "structlog>=24.0.0",
    "redis>=5.0.0",
    "chromadb>=0.5.0",
    "python-dotenv>=1.0.0",
    "httpx>=0.28.0",
    "websockets>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
]
```

---

## 并行执行建议

以下步骤可以并行执行：
- Step 2.1 (LLM客户端) 和 Step 2.3 (工具系统) 可并行
- Step 2.2 (消息系统) 和 Step 2.5 (记忆系统) 可并行
- Step 4.1, 4.2, 4.3 (三个业务场景) 可并行
- Step 5.1 (API) 和 Step 5.2 (UI) 可并行

---

## 检查清单

### 完成标准
- [ ] 所有核心组件实现并测试通过
- [ ] 3个业务场景可运行演示
- [ ] 测试覆盖率 >= 80%
- [ ] Docker部署成功
- [ ] README文档完整
- [ ] API文档自动生成

### 简历准备
- [ ] 录制演示视频/GIF
- [ ] 准备架构图
- [ ] 准备技术亮点说明
- [ ] 代码上传GitHub
