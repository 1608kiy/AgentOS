# 快速上手

5 分钟从零跑起 AgentFlow，体验真实 LLM 驱动的多 Agent 协作。

## 前提条件

- Python 3.11+
- 任一 LLM API Key（OpenAI / Anthropic / 兼容 OpenAI 协议的服务如 MiMo）

## 1. 安装

```bash
git clone https://github.com/1608kiy/AgentOS.git
cd AgentOS
pip install -e ".[full]"
```

## 2. 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 API Key：

```bash
# OpenAI 用户
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-你的key

# 或者 MiMo 用户
LLM_PROVIDER=mimo
LLM_MODEL=mimo-v2.5-pro
LLM_API_KEY=你的key
LLM_OPENAI_BASE_URL=https://你的endpoint/v1
```

## 3. CLI 快速体验

```bash
# 最简单的一次对话
agentflow run "什么是快速排序？用一句话说明"
```

## 4. API 服务

```bash
agentflow serve
# 打开 http://localhost:8000/docs 查看 Swagger UI
```

认证：`POST /api/v1/auth/token`，username=`admin`，password=`admin`

```bash
# 获取 token
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'

# 创建 Agent（自动继承 .env 里的 LLM 配置）
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"my_agent","system_prompt":"你是一个有帮助的助手"}'

# 对话
curl -X POST http://localhost:8000/api/v1/agents/AGENT_ID/run \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"帮我算一下 2 的 10 次方"}'
```

## 5. Streamlit UI

```bash
agentflow ui
# 打开 http://localhost:8501
```

在"对话"标签页选择 Agent，输入问题即可开始。支持工具调用结果可视化、Token 用量追踪。

## 6. 多 Agent 编排（Python）

```python
import asyncio
from agentflow.agents.base import ReActAgent, AgentConfig
from agentflow.workflow.orchestrator import AgentOrchestrator, OrchestrationStrategy

async def main():
    # 自动使用 .env 里的 LLM 配置
    planner = ReActAgent(config=AgentConfig(
        agent_name="规划师",
        system_prompt="你负责把任务拆解为具体步骤。",
    ))
    coder = ReActAgent(config=AgentConfig(
        agent_name="程序员",
        system_prompt="你负责写 Python 代码，用代码执行工具验证。",
    ))

    orchestrator = AgentOrchestrator(strategy=OrchestrationStrategy.SEQUENTIAL)
    orchestrator.register_agent(planner)
    orchestrator.register_agent(coder)

    result = await orchestrator.run("写一个函数计算斐波那契数列")
    print(result.final_output)

asyncio.run(main())
```

## 7. 工作流引擎（Python）

```python
from agentflow.workflow.engine import WorkflowBuilder, WorkflowEngine, DefaultNodeExecutor

builder = WorkflowBuilder("代码审查流")
builder.add_agent_node("review", "my_agent", "审查这段代码: def add(a,b): return a+b")
builder.add_condition_node("check", "score > 7")
builder.add_tool_node("notify", "api_call", {"url": "https://example.com/hook"})
builder.connect("review", "check")
builder.connect("check", "notify")
builder.set_entry("review")
builder.set_exit("check")
builder.set_exit("notify")

workflow = builder.build()
engine = WorkflowEngine()
context = await engine.execute(workflow)
print(context.status)  # "completed"
```

## 常见问题

**Q: 启动时 `.env` 的配置不生效？**

A: 确认变量名有正确的前缀：
- LLM 配置：`LLM_`（如 `LLM_API_KEY`、`LLM_MODEL`）
- Agent 配置：`AGENT_`（如 `AGENT_MAX_ITERATIONS`）
- 详见 `.env.example` 里的注释

**Q: 工具调用后 Agent 没有继续循环？**

A: 检查 LLM 是否支持 function-calling。不支持的模型（如某些本地模型）会直接返回答案而不调用工具。

**Q: 如何接入本地 LLM（Ollama）？**

```bash
LLM_PROVIDER=local
LLM_LOCAL_BASE_URL=http://localhost:11434
LLM_LOCAL_MODEL=llama3
```

---

更多内容：[架构设计](architecture.md) | [API 文档](http://localhost:8000/docs) | [GitHub](https://github.com/1608kiy/AgentOS)
