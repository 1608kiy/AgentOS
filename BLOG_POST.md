# 从零构建企业级多Agent协作平台 -- AgentFlow v0.3.0 发布

> 项目地址：[github.com/1608kiy/AgentOS](https://github.com/1608kiy/AgentOS)

---

## 为什么不用 LangChain，而是自己造？

2024 年 Agent 框架遍地开花，LangChain、CrewAI、AutoGen 各有一席之地。真正上手之后，我发现这些问题很难回避：

- **封装太深**：LangChain 的 `AgentExecutor` 内部至少经过 3-4 层抽象，出问题时 debug 非常痛苦。模型调用了几次、中间状态如何流转，开发者基本看不到。
- **成本黑洞**：旧版 ReAct 模式下一"步"要跑 think、should_answer、decide、answer 四次 LLM 调用，token 消耗是理论下限的 3-4 倍。
- **工作流是"假的"**：多数框架的工作流引擎返回的是 mock 数据，节点之间没有真正的 DAG 调度逻辑，fan-out/fan-in 基本靠手写。
- **Demo 级项目**：没有认证、没有监控、没有评估框架，离"企业可用"还有很远的距离。

所以，我决定从零写一个。不是为了重复造轮子，而是**每一个轮子都必须是我自己车出来的**，只有这样才能真正理解 Agent 系统的每一个细节。

AgentFlow 就这样诞生了。从 v0.1 的最简 ReAct 循环，到 v0.3.0 的 143 个测试、8 个 LLM Provider、真正的 DAG 工作流引擎，这个项目用代码回答了一个问题：**一个 Agent 平台到底需要什么？**

---

## 架构设计：四层分离，各司其职

AgentFlow 采用经典的四层架构，每一层只做一件事：

```
+-------------------------------------------------------------------+
|                        Streamlit UI                                |
|   对话   |  工作流设计器  |  监控面板  |  评估面板  |  插件管理   |
+-------------------------------------------------------------------+
|                           |                                        |
+-------------------------------------------------------------------+
|                    FastAPI Service Layer                            |
|   Auth(JWT)  |  Agent API  |  Workflow API  |  WebSocket Streaming |
+-------------------------------------------------------------------+
|                           |                                        |
+-------------------------------------------------------------------+
|                    Core Engine Layer                                |
|   Agent Orchestrator  |  Workflow Engine  |  Memory Manager        |
|   Tool Registry       |  Message Bus      |  Session Store         |
+-------------------------------------------------------------------+
|                           |                                        |
+-------------------------------------------------------------------+
|                   Infrastructure Layer                              |
|   LLM Client (8 providers)  |  Redis Cache  |  SQLite  |  OTel    |
+-------------------------------------------------------------------+
```

几个核心设计决策：

**1. 不依赖 LangChain。** 所有核心逻辑——ReAct 循环、DAG 调度、工具注册、消息总线——全部自己实现。好处是每一行代码都可控，坏处是……确实写了不少代码。

**2. LLM 抽象层统一。** 不管你用 OpenAI、Anthropic、Gemini、DeepSeek、Qwen、智谱、MiMo 还是本地 Ollama，上层代码完全一样。换 Provider 只需要改 `.env` 里的一行配置。

**3. 基础设施可插拔。** 认证用 JWT + API Key 双模式，存储默认 SQLite（可换 Redis），可观测性默认 structlog（可接 OpenTelemetry）。没有硬依赖，按需组装。

---

## 核心亮点

### 1. 原生 tool-calling 单循环

这是 v0.3.0 最大的架构改动。旧版循环长这样：

```
旧版：用户输入 → think(LLM) → should_answer(LLM) → decide(LLM) → answer(LLM)
         一"步"需要 3-4 次 LLM 调用
```

新版改为**原生 tool-calling 单循环**：

```python
async def run(self, task: str) -> AgentResponse:
    for _ in range(self.max_iterations):
        # 单次 LLM 调用：模型自主决定调用工具还是给出答案
        response = await self._step()

        tool_calls = [self._parse_tool_call(tc) for tc in response.tool_calls]
        tool_calls = [tc for tc in tool_calls if tc is not None]

        if tool_calls:
            # 执行工具，结果回灌对话，继续循环
            for tool_call in tool_calls:
                result = await self._execute_tool(tool_call)
                self.conversation.add_user(
                    f"[{tool_call.name} result]\n{result.content}"
                )
            continue

        # 没有工具调用 → 最终答案
        return AgentResponse(content=response.content, ...)
```

模型自己决定该调哪个工具，不需要额外的 think/decide 步骤。同样一个任务，token 消耗降低 3-4 倍，响应速度也快了不少。

### 2. 真正的 DAG 工作流引擎

很多框架的"工作流"其实就是个串行链，节点之间没有依赖关系的概念。AgentFlow 的工作流引擎是**真正的 DAG 调度器**：

- **fan-out**：一个节点的输出可以分发给多个下游节点
- **fan-in**：多个上游节点的输出汇聚到一个节点（等待所有入边就绪）
- **条件分支**：条件节点未命中的分支自动跳过，结果向下游传播
- **并行执行**：就绪节点通过 `asyncio.gather` 并发运行
- **Human-in-the-loop**：节点可以暂停，通过 `resume()` 注入人工输入后从断点继续

引擎基于**入度/边状态驱动**调度，不是简单的 for 循环遍历：

```python
builder = WorkflowBuilder("代码审查流")
builder.add_agent_node("review", "reviewer", "审查这段代码")
builder.add_condition_node("check", "score > 7")
builder.add_tool_node("notify", "api_call", {"url": "https://example.com/hook"})
builder.connect("review", "check")
builder.connect("check", "notify")
```

5 种节点类型（Agent / Tool / Condition / Parallel / Human），拖拖拽拽就能搭出复杂的协作流。

### 3. AST 沙箱 vs 字符串黑名单

代码执行工具（`code_executor`）是 Agent 系统的高危功能。早期版本用的是**字符串黑名单**——检查代码里有没有 `import os`、有没有 `exec()`。但这种方式太容易绕过了：

```python
# 字符串黑名单轻松被绕过
__builtins__.__dict__["exec"]("import os; os.system('rm -rf /')")
getattr(__builtins__, "exec")("...")
```

v0.3.0 改为 **AST 静态分析**，从语法树层面拦截：

```python
def _check_ast(self, code: str) -> str | None:
    for node in ast.walk(ast.parse(code)):
        if isinstance(node, ast.Import):
            if node.names[0].name.split(".")[0] in self._BLOCKED_MODULES:
                return "安全拒绝: 禁止导入受限模块"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in self._BLOCKED_CALLS:
                return "安全拒绝: 禁止调用受限函数"
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):  # 拦截 __bases__ 等 dunder 逃逸
                return "安全拒绝: 禁止访问 dunder 属性"
```

三层纵深防御：AST 静态分析（拦截 import / dunder / getattr 绕过）+ subprocess `-I` 隔离模式 + 超时控制。不是绝对安全的沙箱（真正的隔离需要容器或 gVisor），但比字符串黑名单强了几个数量级。

### 4. 8 个 LLM Provider 统一抽象

国内开发者面对的 LLM 生态比海外复杂得多——OpenAI、Anthropic、Gemini 之外，还有 DeepSeek、通义千问、智谱、MiMo 等一众国产模型。AgentFlow 的 LLM 客户端层做了统一抽象：

| Provider | 协议 | 说明 |
|----------|------|------|
| OpenAI | 原生 SDK | 默认选项 |
| Anthropic | 原生 SDK | Claude 系列 |
| Gemini | google-generativeai | Google AI |
| DeepSeek | OpenAI 兼容 | 国产性价比之选 |
| Qwen | OpenAI 兼容 | 阿里通义 |
| Zhipu | OpenAI 兼容 | 智谱 GLM |
| MiMo | OpenAI 兼容 | 小米推理模型 |
| Local/Ollama | OpenAI 兼容 | 本地部署 |

上层代码完全不感知 Provider 差异，换模型改一行 `.env` 配置即可：

```bash
# 从 DeepSeek 切换到 MiMo，只改这两行
LLM_PROVIDER=mimo
LLM_MODEL=mimo-v2.5-pro
LLM_API_KEY=你的key
```

---

## 真实端到端验证：用 MiMo v2.5 Pro 跑通全流程

光有测试不够，我们用**真实 LLM**（小米 MiMo v2.5 Pro）做了端到端验证：

**场景 1：简单对话**

输入 `"2+3?"`，Agent 直接返回 `"5"`。耗时 9.2s，消耗 2432 tokens。正常。

**场景 2：工具调用**

输入 `"sqrt(144)+10"`，Agent 自主决定调用计算器工具，工具返回 `12`，Agent 继续推理给出最终答案 `22`。工具选择和结果整合都正确。

**场景 3：多 Agent 编排**

Planner Agent 接到"实现斐波那契函数"的任务，输出步骤拆解；Coder Agent 根据步骤编写代码并用代码执行工具验证。两个 Agent 通过 Supervisor 模式协调，最终输出了正确的实现。

**场景 4：工作流 DAG**

构建一个 3 节点工作流（Agent 审查 -> 条件判断 -> 通知），Agent 返回"功能正确，建议添加类型提示"，条件节点根据评分决定后续路径，整个 DAG 执行完毕状态为 `completed`。

从 102 passed / 12 failed 到 **143 passed / 0 failed**，v0.3.0 是第一个经过真实 LLM 全面验证的版本。

---

## 快速上手：5 行代码跑起第一个 Agent

安装：

```bash
git clone https://github.com/1608kiy/AgentOS.git
cd AgentOS
pip install -e ".[full]"
cp .env.example .env   # 填入你的 API Key
```

写一个最简 Agent：

```python
import asyncio
from agentflow.agents.base import ReActAgent, AgentConfig

async def main():
    agent = ReActAgent(config=AgentConfig(
        agent_name="助手",
        system_prompt="你是一个有帮助的AI助手。",
    ))
    response = await agent.run("什么是快速排序？")
    print(response.content)

asyncio.run(main())
```

想试多 Agent 协作？加几行就行：

```python
from agentflow.workflow.orchestrator import AgentOrchestrator, OrchestrationStrategy

planner = ReActAgent(config=AgentConfig(
    agent_name="规划师",
    system_prompt="你负责把任务拆解为具体步骤。",
))
coder = ReActAgent(config=AgentConfig(
    agent_name="程序员",
    system_prompt="你负责写 Python 代码。",
))

orchestrator = AgentOrchestrator(strategy=OrchestrationStrategy.SEQUENTIAL)
orchestrator.register_agent(planner)
orchestrator.register_agent(coder)

result = await orchestrator.run("写一个函数计算斐波那契数列")
print(result.final_output)
```

启动方式也很灵活：

```bash
agentflow run "你的问题"      # CLI 一行搞定
agentflow serve                # API 服务 (http://localhost:8000/docs)
agentflow ui                   # Streamlit 可视化界面 (http://localhost:8501)
docker-compose up -d           # Docker 一键部署
```

---

## 总结与展望

AgentFlow v0.3.0 是一个里程碑版本。13 个 critical bug 修复、原生 tool-calling 循环重写、真正的 DAG 工作流引擎、AST 沙箱安全加固——这些改进让项目从"能跑"变成了"能用"。

接下来的计划：

- 流式编排输出，实时显示 Agent 的思考过程
- 多租户支持
- 工作流版本管理和回滚
- Agent 市场，共享 Agent 配置模板

项目是 MIT 协议开源，欢迎 star、提 issue、提交 PR。如果你也在做 Agent 相关的开发，希望这个项目能给你一些参考。

---

**项目地址**：[github.com/1608kiy/AgentOS](https://github.com/1608kiy/AgentOS)

**快速开始**：[docs/quickstart.md](https://github.com/1608kiy/AgentOS/blob/main/docs/quickstart.md)

**架构设计**：[docs/architecture.md](https://github.com/1608kiy/AgentOS/blob/main/docs/architecture.md)
