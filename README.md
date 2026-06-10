# AgentFlow - 企业级多Agent协作平台

<p align="center">
    <strong>⚡ 从零构建的企业级多Agent协作平台，支持可视化工作流、评估框架、插件系统</strong>
</p>

<p align="center">
    <img src="https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/fastapi-0.115+-009688.svg?logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/streamlit-1.40+-FF4B4B.svg?logo=streamlit&logoColor=white" alt="Streamlit">
    <img src="https://img.shields.io/badge/pydantic-2.9+-E92063.svg" alt="Pydantic">
    <img src="https://img.shields.io/badge/tests-123_passed-2ECC71.svg" alt="Tests">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
</p>

---

## 🏗️ 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        Streamlit UI                              │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │
│  │ 对话   │ │ 工作流 │ │ 监控   │ │ 评估   │ │ 插件   │       │
│  │        │ │ 设计器 │ │ 面板   │ │ 面板   │ │ 管理   │       │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘       │
│       │          │          │          │          │              │
│  ┌────┴──────────┴──────────┴──────────┴──────────┴────┐       │
│  │              FastAPI Service Layer                   │       │
│  │  ┌──────┐ ┌────────┐ ┌──────┐ ┌────────────────┐  │       │
│  │  │ Auth │ │ Agent  │ │ WF   │ │ WebSocket      │  │       │
│  │  │ JWT  │ │ API    │ │ API  │ │ Streaming      │  │       │
│  │  └──────┘ └────────┘ └──────┘ └────────────────┘  │       │
│  └────────────────────┬────────────────────────────────┘       │
│                       │                                          │
│  ┌────────────────────┴────────────────────────────────┐       │
│  │              Core Engine Layer                        │       │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │       │
│  │  │ Agent    │ │ Workflow │ │ Memory   │            │       │
│  │  │ Orch.    │ │ Engine   │ │ Manager  │            │       │
│  │  └──────────┘ └──────────┘ └──────────┘            │       │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │       │
│  │  │ Tool     │ │ Message  │ │ Session  │            │       │
│  │  │ Registry │ │ Bus      │ │ Store    │            │       │
│  │  └──────────┘ └──────────┘ └──────────┘            │       │
│  └────────────────────┬────────────────────────────────┘       │
│                       │                                          │
│  ┌────────────────────┴────────────────────────────────┐       │
│  │              Infrastructure Layer                     │       │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │       │
│  │  │ LLM    │ │ Redis  │ │ SQLite │ │ OTel   │       │       │
│  │  │ Client │ │ Cache  │ │ DB     │ │ Trace  │       │       │
│  │  └────────┘ └────────┘ └────────┘ └────────┘       │       │
│  └──────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✨ 核心特性

### 🤖 Agent系统
- **原生 tool-calling 单循环** — 每轮一次 LLM 调用自主决定「调用工具」或「给出答案」，相比传统多次 think/decide 调用，速度与成本降低约 3-4 倍
- **多 provider** — OpenAI / Anthropic / 本地(Ollama) / MiMo，统一抽象
- **分层记忆** — 短期(对话)/长期(向量，自动初始化+语义召回)/工作记忆
- **中间件管道** — 内容过滤、成本追踪、自定义钩子
- **Token预算** — 每个Agent独立的token用量追踪

### 🔄 多Agent编排
- **串行执行** — Agent链式执行
- **并行执行** — asyncio.gather并发
- **辩论模式** — 多轮讨论+总结
- **主管模式** — Supervisor 按成员**名称+能力**分配任务，Worker 执行后汇总

### 🔧 工作流引擎
- **真正的 DAG 调度** — 基于入度/边状态驱动，支持 fan-out(一对多)、fan-in(多入边汇聚)、就绪节点并发执行
- **5种节点** — Agent/Tool/Condition/Parallel/Human
- **条件分支** — 未命中分支自动跳过并向下传播
- **Human-in-the-loop** — 节点暂停 → `resume()` 注入人工输入后从断点继续
- **可视化设计器** — Canvas拖拽编辑

### 🛡️ 企业级特性
- **JWT + API Key** — 双模式认证
- **RBAC** — admin/user/viewer角色
- **LLM重试** — 指数退避(429/500/502/503)
- **响应缓存** — 可选 LRU 缓存（默认关闭，避免 Agent 循环中误命中）
- **结构化日志** — structlog + 链路追踪
- **沙箱执行** — AST 静态检查 + subprocess 隔离（拦截 import/dunder/危险内置调用绕过）

### 📊 可观测性
- **Token成本仪表盘** — Plotly图表
- **执行历史** — 耗时/状态/迭代次数
- **Agent状态** — 实时监控
- **OpenTelemetry** — 可选集成

### 🧪 评估框架
- **4种评分器** — 精确/包含/LLM/组合
- **3套基准集** — general/coding/reasoning
- **自动评分** — 一键运行评估套件

### 📚 RAG / 文档检索
- **向量语义检索** — OpenAI 兼容 embeddings 或 sentence-transformers
- **自动降级** — 无嵌入后端时退化为 TF-IDF 关键词匹配，始终可用
- **分块 + 重叠** — 段落感知切分，保留上下文

### 🔌 插件系统
- **插件注册** — Tool/Agent/Memory可插拔
- **目录加载** — ~/.agentflow/plugins/
- **Entry Points** — pip install自动注册

---

## 🚀 快速开始

### 安装

```bash
# 克隆
git clone https://github.com/1608kiy/AgentOS.git
cd AgentOS

# 安装（基础）
pip install -e .

# 安装（全功能）
pip install -e ".[full]"

# 安装（开发）
pip install -e ".[dev]"
```

### 配置

```bash
cp .env.example .env
# 编辑 .env 设置 API key
LLM_API_KEY=sk-your-key
```

### 启动

```bash
# CLI
agentflow run "分析这段代码的安全性"

# API服务
agentflow serve
# → http://localhost:8000/docs

# Streamlit UI
agentflow ui
# → http://localhost:8501

# Docker
docker-compose up -d
```

---

## 📖 使用示例

### 基础对话

```python
from agentflow.agents.base import ReActAgent, AgentConfig

agent = ReActAgent(config=AgentConfig(
    agent_name="Assistant",
    system_prompt="你是一个有帮助的AI助手。",
))
response = await agent.run("什么是快速排序？")
print(response.content)
```

### 多Agent协作

```python
from agentflow.agents.base import PlannerAgent, CoderAgent, ReviewerAgent
from agentflow.workflow.orchestrator import AgentOrchestrator, OrchestrationStrategy

orchestrator = AgentOrchestrator(strategy=OrchestrationStrategy.SUPERVISOR)
orchestrator.register_agents([PlannerAgent(), CoderAgent(), ReviewerAgent()])

result = await orchestrator.run("写一个HTTP服务器")
print(result.final_output)
```

### 自定义工具

```python
from agentflow.tools.base import Tool, ToolRegistry

class MyTool(Tool):
    name = "my_tool"
    description = "我的工具"
    parameters = {"type": "object", "properties": {"input": {"type": "string"}}}

    async def execute(self, input: str = "", **kwargs) -> str:
        return f"处理: {input}"

registry = ToolRegistry()
registry.register(MyTool())
```

### Agent评估

```python
from agentflow.core.evaluation import EvalRunner, ContainsScorer, create_eval_suite

runner = EvalRunner(agent=my_agent, scorer=ContainsScorer())
report = await runner.run_suite(create_eval_suite("general"))
print(f"通过率: {report.pass_rate:.0%}")
```

---

## 🧪 测试

```bash
# 运行测试
pytest tests/ -v

# 带覆盖率
pytest tests/ --cov=agentflow --cov-report=html

# 性能基准
python -c "
import asyncio
from agentflow.core.benchmark import run_all_benchmarks, format_benchmark_report
results = asyncio.run(run_all_benchmarks())
print(format_benchmark_report(results))
"
```

---

## 📁 项目结构

```
agentflow/
├── src/agentflow/
│   ├── core/
│   │   ├── config.py          # Pydantic配置管理
│   │   ├── llm.py             # LLM客户端(重试/缓存/多provider)
│   │   ├── message.py         # 消息系统
│   │   ├── state.py           # 状态机
│   │   ├── logging.py         # structlog + 链路追踪
│   │   ├── message_bus.py     # 发布-订阅消息总线
│   │   ├── session.py         # 会话持久化(Memory/File/Redis)
│   │   ├── evaluation.py      # Agent评估框架
│   │   ├── plugins.py         # 插件系统
│   │   ├── benchmark.py       # 性能基准测试
│   │   └── otel.py            # OpenTelemetry集成
│   ├── agents/
│   │   └── base.py            # Agent基类(ReAct/记忆/中间件)
│   ├── tools/
│   │   └── base.py            # 工具系统(沙箱/真实搜索)
│   ├── memory/
│   │   └── manager.py         # 分层记忆管理
│   ├── workflow/
│   │   ├── engine.py          # DAG工作流引擎
│   │   └── orchestrator.py    # 多Agent编排器
│   ├── api/
│   │   ├── app.py             # FastAPI(依赖注入)
│   │   ├── auth.py            # JWT + API Key认证
│   │   └── docs.py            # API文档增强
│   ├── ui/
│   │   ├── app.py             # Streamlit(暗色主题)
│   │   ├── components/
│   │   │   └── workflow_designer.py  # Canvas工作流设计器
│   │   └── pages/
│   │       ├── eval_page.py   # 评估页面
│   │       └── plugin_page.py # 插件管理
│   └── utils/
│       └── structured_output.py # JSON解析
├── tests/                     # 99个测试
├── .github/workflows/ci.yml   # CI/CD
├── Dockerfile                 # 多阶段构建
├── docker-compose.yml         # Docker编排
└── .streamlit/config.toml     # Streamlit主题
```

---

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **LLM** | OpenAI / Anthropic / 本地LLM(Ollama) |
| **框架** | Pydantic v2 / FastAPI / Streamlit |
| **存储** | SQLite / Redis / ChromaDB |
| **可观测** | structlog / OpenTelemetry / Plotly |
| **部署** | Docker / GitHub Actions |
| **测试** | pytest / pytest-asyncio |

---

## 🔒 安全说明

代码执行工具（`code_executor`）采用**纵深防御**：AST 静态分析（拦截危险 `import`、dunder 属性访问、`eval/exec/getattr` 等内置调用绕过）+ subprocess 隔离（`-I` 隔离模式、空环境变量、超时）。

这能显著降低风险，但**不是绝对安全的沙箱**。运行完全不可信的代码时，请在 OS 级隔离（容器 / gVisor / nsjail）中执行。

---

## 📄 License

MIT License
