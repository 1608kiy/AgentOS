# AgentFlow：从零构建企业级多Agent协作平台

> 本文介绍AgentFlow的架构设计、核心技术选型和实现细节。

## 为什么要做这个项目？

市面上已有很多Agent框架（LangChain、CrewAI、AutoGen），但大多数是**高层封装**，隐藏了底层实现。AgentFlow的目标是：

1. **从零实现** — 不依赖LangChain/LangGraph，所有核心逻辑自己写
2. **企业级特性** — 认证、日志、监控、评估，不是Demo级
3. **可扩展** — 插件系统、中间件管道、工具注册表

## 架构设计

### 整体分层

```
┌─────────────────────────────────────┐
│         UI Layer (Streamlit)         │
├─────────────────────────────────────┤
│         API Layer (FastAPI)          │
├─────────────────────────────────────┤
│         Core Engine Layer            │
│  ┌─────────┬─────────┬─────────┐   │
│  │ Agent   │ Workflow│ Memory  │   │
│  │ Orch.   │ Engine  │ Manager │   │
│  └─────────┴─────────┴─────────┘   │
├─────────────────────────────────────┤
│       Infrastructure Layer           │
│  ┌────────┬────────┬────────┐      │
│  │ LLM    │ Redis  │ SQLite │      │
│  │ Client │ Cache  │ DB     │      │
│  └────────┴────────┴────────┘      │
└─────────────────────────────────────┘
```

### 核心设计决策

#### 1. 为什么不直接用LangGraph？

LangGraph很好，但作为学习项目，自己实现能更深入理解：
- DAG执行引擎的调度逻辑
- 状态机的流转控制
- 并行执行的asyncio编排

#### 2. ReAct模式的实现

```python
async def run(self, task: str) -> AgentResponse:
    for iteration in range(self.max_iterations):
        # 1. Think
        thought = await self._think()

        # 2. Decide - 用LLM判断是否该回答
        if await self._should_answer(thought):
            return await self._generate_answer()

        # 3. Act
        tool_call = await self._decide_action(thought)
        if tool_call:
            result = await self._execute_tool(tool_call)
            # 4. Observe - 结果加入对话
            self.conversation.add_tool(result.content)
```

关键改进：`_should_answer`不用关键词匹配，而是让LLM自己判断。

#### 3. 工作流引擎的节点注入

很多框架的工作流引擎是"假执行"——节点返回mock数据。AgentFlow通过`DefaultNodeExecutor`实现真实执行：

```python
class DefaultNodeExecutor:
    def __init__(self):
        self._agents = {}
        self._tools = None

    async def execute_agent(self, agent_type, task, config):
        agent = self._agents.get(agent_type)
        response = await agent.run(task)
        return response.content
```

节点创建时指定`agent_type`，执行时从注册表查找真实Agent实例。

#### 4. 中间件管道

Agent执行前后可以插入中间件：

```python
class AgentMiddleware(ABC):
    async def before_run(self, agent, task) -> str | None: ...
    async def after_run(self, agent, response) -> AgentResponse: ...
    async def on_error(self, agent, error) -> bool: ...
```

内置两个中间件：
- `ContentFilterMiddleware` — 过滤危险操作
- `CostTrackerMiddleware` — 追踪token用量

## 技术亮点

### 1. LLM调用的健壮性

```python
async def _retry_with_backoff(self, func, *args, **kwargs):
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if not is_retryable or attempt == max_retries:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            await asyncio.sleep(delay)
```

- 指数退避：1s → 2s → 4s
- 可重试状态码：429, 500, 502, 503
- LRU缓存避免重复调用

### 2. 沙箱化代码执行

```python
class CodeExecutorTool(Tool):
    _BLOCKED = frozenset(["os.system", "subprocess", "__import__", ...])

    async def execute(self, code, timeout=10):
        # 预检查
        for blocked in self._BLOCKED:
            if blocked in code.lower():
                return f"安全拒绝: {blocked}"

        # subprocess隔离执行
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, timeout=timeout,
            env={},  # 清空环境变量
        )
```

三层防护：黑名单检查 → subprocess隔离 → 超时控制。

### 3. 评估框架

```python
class EvalRunner:
    async def run_suite(self, tasks: list[EvalTask]) -> EvalReport:
        results = []
        for task in tasks:
            response = await self.agent.run(task.input)
            score, details = await self.scorer.score(task, response)
            results.append(EvalResult(score=score, passed=score >= 0.7))

        return EvalReport(
            passed=sum(1 for r in results if r.passed),
            avg_score=mean(r.score for r in results),
            ...
        )
```

支持4种评分器组合，一键运行基准测试集。

## 测试策略

```
tests/
├── unit/           # 单元测试（核心组件）
│   ├── test_agents.py
│   ├── test_tools.py
│   ├── test_workflow.py
│   ├── test_orchestrator.py
│   ├── test_auth.py
│   ├── test_session.py
│   ├── test_evaluation.py
│   ├── test_plugins.py
│   ├── test_otel.py
│   └── test_benchmark.py
└── integration/    # 集成测试（API端到端）
    └── test_api.py
```

99个测试，覆盖所有核心模块。

## 性能基准

```
📊 Agent创建         avg: 0.15ms | P95: 0.25ms | 吞吐: 6500 ops/s
📊 Agent执行(MockLLM) avg: 45ms   | P95: 68ms  | 吞吐: 22 ops/s
📊 工具执行(Calculator) avg: 0.02ms | P95: 0.05ms | 吞吐: 50000 ops/s
📊 编排器(3 Agent)    avg: 135ms  | P95: 180ms | 吞吐: 7.4 ops/s
📊 工作流引擎(3节点)   avg: 140ms  | P95: 190ms | 吞吐: 7.1 ops/s
```

## 部署

### Docker

```bash
docker-compose up -d
# API: http://localhost:8000/docs
# UI: http://localhost:8501
```

### GitHub Actions

```yaml
lint → test → build → docker
```

每次push自动运行lint检查、测试、构建。

## 未来规划

- [ ] 流式编排输出（实时显示Agent思考过程）
- [ ] 多租户支持
- [ ] 更多LLM provider（Gemini、本地模型）
- [ ] 工作流版本管理
- [ ] Agent市场（共享Agent配置）

## 总结

AgentFlow不是一个"又一个ChatGPT wrapper"，而是一个**从零构建的企业级Agent平台**。核心价值在于：

1. **自己实现核心引擎** — 不依赖LangChain
2. **企业级特性完整** — 认证、日志、监控、评估
3. **代码质量高** — 99个测试、类型注解、文档完整
4. **可扩展性强** — 插件系统、中间件、工具注册

项目地址：[github.com/1608kiy/AgentOS](https://github.com/1608kiy/AgentOS)
