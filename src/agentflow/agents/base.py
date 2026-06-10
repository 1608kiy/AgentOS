"""Agent基类 - ReAct模式实现（企业级增强版）"""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from agentflow.core.config import LLMConfig, LLMProvider
from agentflow.core.llm import LLMClient, LLMFactory, LLMResponse, MockLLMClient
from agentflow.core.logging import AgentLogger, tracing_manager
from agentflow.core.message import ConversationHistory, Message, ToolCall, ToolResult
from agentflow.core.state import AgentState, AgentStatus
from agentflow.memory.manager import MemoryManager
from agentflow.tools.base import Tool, ToolRegistry, create_default_registry


class AgentConfig(BaseModel):
    """Agent配置"""
    agent_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_name: str = ""
    system_prompt: str = ""
    llm_provider: LLMProvider = LLMProvider.OPENAI
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    openai_base_url: str = ""       # OpenAI 兼容端点（MiMo 等第三方服务）
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    max_iterations: int = 10
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: float = 300.0
    max_tokens_budget: int = 100000  # token预算


class AgentResponse(BaseModel):
    """Agent响应"""
    agent_id: str
    content: str
    iterations: int
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0
    token_usage: dict[str, int] = Field(default_factory=dict)


class AgentMiddleware(ABC):
    """Agent中间件基类"""

    @abstractmethod
    async def before_run(self, agent: BaseAgent, task: str) -> str | None:
        """执行前钩子，返回None继续，返回字符串则短路"""
        ...

    @abstractmethod
    async def after_run(self, agent: BaseAgent, response: AgentResponse) -> AgentResponse:
        """执行后钩子"""
        ...

    @abstractmethod
    async def on_error(self, agent: BaseAgent, error: Exception) -> bool:
        """错误钩子，返回True表示已处理"""
        ...


class ContentFilterMiddleware(AgentMiddleware):
    """内容过滤中间件"""

    BLOCKED_PATTERNS = ["rm -rf", "format c:", "DROP TABLE", "DELETE FROM"]

    async def before_run(self, agent: BaseAgent, task: str) -> str | None:
        task_lower = task.lower()
        for pattern in self.BLOCKED_PATTERNS:
            if pattern.lower() in task_lower:
                return f"安全拒绝: 任务包含禁止的操作 '{pattern}'"
        return None

    async def after_run(self, agent: BaseAgent, response: AgentResponse) -> AgentResponse:
        return response

    async def on_error(self, agent: BaseAgent, error: Exception) -> bool:
        return False


class CostTrackerMiddleware(AgentMiddleware):
    """成本追踪中间件"""

    def __init__(self) -> None:
        self.total_tokens: dict[str, int] = {}

    async def before_run(self, agent: BaseAgent, task: str) -> str | None:
        return None

    async def after_run(self, agent: BaseAgent, response: AgentResponse) -> AgentResponse:
        agent_id = response.agent_id
        usage = response.token_usage
        if agent_id not in self.total_tokens:
            self.total_tokens[agent_id] = 0
        self.total_tokens[agent_id] += usage.get("total_tokens", 0)
        response.metadata["cumulative_tokens"] = self.total_tokens[agent_id]
        return response

    async def on_error(self, agent: BaseAgent, error: Exception) -> bool:
        return False

    def get_usage(self, agent_id: str | None = None) -> dict[str, int]:
        if agent_id:
            return {agent_id: self.total_tokens.get(agent_id, 0)}
        return dict(self.total_tokens)


class BaseAgent(ABC):
    """Agent基类"""

    def __init__(
        self,
        config: AgentConfig | None = None,
        llm_client: LLMClient | None = None,
        tools: ToolRegistry | None = None,
        memory: MemoryManager | None = None,
        middlewares: list[AgentMiddleware] | None = None,
    ):
        self.config = config or AgentConfig()
        self.id = self.config.agent_id
        self.name = self.config.agent_name or self.__class__.__name__

        # LLM客户端
        if llm_client:
            self.llm = llm_client
        elif self.config.llm_api_key:
            llm_config = LLMConfig(
                provider=self.config.llm_provider,
                model=self.config.llm_model,
                api_key=self.config.llm_api_key,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                openai_base_url=self.config.openai_base_url,
                anthropic_api_key=self.config.anthropic_api_key,
                anthropic_base_url=self.config.anthropic_base_url,
            )
            self.llm = LLMFactory.create(llm_config)
        else:
            self.llm = MockLLMClient()

        # 工具注册表
        self.tools = tools or create_default_registry()

        # 记忆系统（H2: 接入Agent）
        self.memory = memory or MemoryManager()

        # 状态
        self.state = AgentState(
            agent_id=self.id,
            agent_name=self.name,
            max_iterations=self.config.max_iterations,
        )

        # 对话历史
        self.conversation = ConversationHistory()

        # 日志器
        self.logger = AgentLogger(self.id, self.name)

        # 中间件
        self._middlewares: list[AgentMiddleware] = middlewares or []

        # Token追踪
        self._total_tokens: int = 0

        # 记忆懒初始化标记
        self._memory_ready: bool = False

        # 系统提示
        if self.config.system_prompt:
            self.conversation.add_system(self.config.system_prompt)

    def add_middleware(self, middleware: AgentMiddleware) -> None:
        """添加中间件"""
        self._middlewares.append(middleware)

    @property
    def system_prompt(self) -> str:
        return self.config.system_prompt

    async def run(self, task: str, context: str | None = None) -> AgentResponse:
        """主执行循环 - 原生 tool-calling 单循环

        每轮迭代只做 **一次** LLM 调用：模型要么返回工具调用（执行后继续循环），
        要么返回最终答案（结束）。相比旧版 think→should_answer→decide→answer
        的 3-4 次调用，速度与成本降低约 3-4 倍，且决策更连贯。
        """
        start_time = time.perf_counter()
        self.state.set_status(AgentStatus.THINKING)
        self.logger.log_agent_start(task)

        # 创建追踪
        trace_id = tracing_manager.start_trace()
        self.logger.set_trace_id(trace_id)

        # 中间件：执行前
        for mw in self._middlewares:
            short_circuit = await mw.before_run(self, task)
            if short_circuit:
                return AgentResponse(
                    agent_id=self.id,
                    content=short_circuit,
                    iterations=0,
                    metadata={"middleware_short_circuit": True},
                )

        # 构建用户消息
        user_content = task
        if context:
            user_content = f"上下文:\n{context}\n\n任务: {task}"

        # 注入相关的长期记忆（语义召回，而非重复短期上下文）
        memory_context = await self._recall_memory(task)
        if memory_context:
            user_content = f"[相关记忆]\n{memory_context}\n\n[当前任务]\n{user_content}"

        self.conversation.add_user(user_content)

        token_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        try:
            answer = ""
            for _ in range(self.state.max_iterations):
                self.state.increment_iteration()

                # 单次 LLM 调用：要么给出工具调用，要么给出答案
                response = await self._step()
                self._accumulate_usage(token_usage, response)
                self._total_tokens += response.total_tokens

                tool_calls = [self._parse_tool_call(tc) for tc in response.tool_calls]
                tool_calls = [tc for tc in tool_calls if tc is not None]

                if tool_calls:
                    # 记录模型的思考/工具决策
                    if response.content:
                        self.logger.log_agent_thinking(response.content)
                        self.conversation.add_assistant(response.content)
                    # 执行所有工具调用，结果回灌到对话
                    for tool_call in tool_calls:
                        result = await self._execute_tool(tool_call)
                        self.logger.log_agent_action(tool_call.name, result.content)
                        # 用 user 角色回灌观测，保证跨 provider 兼容（避免严格的
                        # tool_call_id 配对要求导致部分模型报错）
                        self.conversation.add_user(
                            f"[工具 {tool_call.name} 的结果]\n{result.content}"
                        )
                    continue

                # 没有工具调用 → 这是最终答案
                answer = response.content
                if not answer:
                    answer = await self._generate_answer()
                else:
                    self.conversation.add_assistant(answer)
                break
            else:
                # 达到最大迭代仍未收敛 → 强制总结
                answer = await self._generate_answer()

            duration = (time.perf_counter() - start_time) * 1000
            self.state.set_status(AgentStatus.COMPLETED)
            self.logger.log_agent_complete(answer, duration)

            # 将结果写入长期记忆，供后续任务语义召回
            await self._store_memory(task, answer)

            response_obj = AgentResponse(
                agent_id=self.id,
                content=answer,
                iterations=self.state.iteration,
                duration_ms=duration,
                token_usage=token_usage,
                metadata={"trace_id": trace_id},
            )

            # 中间件：执行后
            for mw in self._middlewares:
                response_obj = await mw.after_run(self, response_obj)

            tracing_manager.end_trace(trace_id)
            return response_obj

        except Exception as e:
            self.state.set_error(str(e))
            self.logger.log_agent_error(e)
            tracing_manager.end_trace(trace_id)

            # 中间件：错误处理
            for mw in self._middlewares:
                if await mw.on_error(self, e):
                    break
            raise
        finally:
            self.state.set_status(AgentStatus.IDLE)

    async def _step(self) -> LLMResponse:
        """单步推理：有工具则用原生 function-calling，否则普通对话。"""
        messages = list(self.conversation.get_messages())
        tool_schemas = self.tools.to_function_schemas()
        if tool_schemas:
            return await self.llm.function_call(messages, tool_schemas)
        return await self.llm.chat(messages)

    def _parse_tool_call(self, tc: dict[str, Any]) -> ToolCall | None:
        """解析不同 provider 的工具调用结构为统一的 ToolCall。

        OpenAI 形态: {"id":.., "function": {"name":.., "arguments": "json串"}}
        Anthropic 形态: {"id":.., "name":.., "arguments": {..}}
        """
        try:
            if "function" in tc:  # OpenAI 兼容
                fn = tc["function"]
                name = fn.get("name", "")
                raw_args = fn.get("arguments", {})
            else:  # Anthropic / 通用
                name = tc.get("name", "")
                raw_args = tc.get("arguments", {})
            if not name:
                return None
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            return ToolCall(id=tc.get("id") or str(uuid4()), name=name, arguments=args)
        except Exception:
            return None

    @staticmethod
    def _accumulate_usage(acc: dict[str, int], response: LLMResponse) -> None:
        """累加 token 使用量。"""
        usage = getattr(response, "usage", {}) or {}
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            acc[key] = acc.get(key, 0) + int(usage.get(key, 0))

    async def _ensure_memory(self) -> None:
        """懒初始化记忆系统（首次使用时接通长期向量存储）。"""
        if self._memory_ready:
            return
        try:
            await self.memory.initialize()
        except Exception:
            pass
        self._memory_ready = True

    async def _recall_memory(self, task: str, top_k: int = 3) -> str:
        """从长期记忆中语义召回与当前任务相关的内容。"""
        await self._ensure_memory()
        try:
            memories = await self.memory.recall(task, memory_type="long", top_k=top_k)
        except Exception:
            return ""
        snippets = [m.content for m in memories if m.content]
        return "\n".join(f"- {s}" for s in snippets)

    async def _store_memory(self, task: str, answer: str) -> None:
        """把任务结果写入长期记忆。"""
        await self._ensure_memory()
        try:
            await self.memory.remember(
                f"任务: {task}\n结果: {answer[:500]}",
                memory_type="long",
                metadata={"agent": self.name},
            )
        except Exception:
            pass

    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """执行工具调用"""
        tool = self.tools.get(tool_call.name)
        if not tool:
            return ToolResult(
                call_id=tool_call.id,
                content=f"工具不存在: {tool_call.name}",
                is_error=True,
            )

        self.logger.log_tool_call(tool_call.name, tool_call.arguments)

        try:
            result = await asyncio.wait_for(
                tool.execute(**tool_call.arguments),
                timeout=60.0,
            )
            self.logger.log_tool_result(tool_call.name, result)
            return ToolResult(call_id=tool_call.id, content=result, is_error=False)
        except TimeoutError:
            return ToolResult(
                call_id=tool_call.id,
                content=f"工具执行超时: {tool_call.name}",
                is_error=True,
            )
        except Exception as e:
            self.logger.log_tool_result(tool_call.name, str(e), is_error=True)
            return ToolResult(
                call_id=tool_call.id,
                content=f"工具执行错误: {e}",
                is_error=True,
            )

    async def _generate_answer(self) -> str:
        """生成最终答案（在无内容/达到最大迭代时兜底）"""
        messages = list(self.conversation.get_messages())
        messages.append(Message.user("请基于以上对话和工具结果，生成最终回答。"))

        response = await self.llm.chat(messages)
        self._total_tokens += response.total_tokens
        self.conversation.add_assistant(response.content)
        return response.content

    async def chat(self, message: str) -> str:
        response = await self.run(message)
        return response.content

    async def stream_chat(self, message: str):
        self.conversation.add_user(message)
        messages = self.conversation.get_messages()
        full_response = ""
        async for chunk in self.llm.stream_chat(messages):
            full_response += chunk
            yield chunk
        # 保存完整回复到对话历史
        if full_response:
            self.conversation.add_assistant(full_response)

    def reset(self) -> None:
        self.state.reset()
        self.conversation.clear()
        if self.config.system_prompt:
            self.conversation.add_system(self.config.system_prompt)

    def get_state(self) -> dict[str, Any]:
        return self.state.to_dict()

    def get_token_usage(self) -> int:
        return self._total_tokens


class ReActAgent(BaseAgent):
    """标准ReAct Agent

    使用 BaseAgent 的原生 tool-calling 单循环。模型每轮自主决定调用工具或给出答案，
    无需多次额外的 think/decide 调用。
    """

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)


class PlannerAgent(BaseAgent):
    """规划Agent"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig(
            agent_name="Planner",
            system_prompt="你是一个任务规划专家。分析复杂任务，分解为可执行的子任务，确定依赖关系。输出结构化JSON计划。",
        ))
        super().__init__(**kwargs)

    async def plan(self, task: str) -> list[dict[str, Any]]:
        response = await self.run(
            f"请将以下任务分解为子任务，输出JSON格式:\n{task}\n\n"
            "输出格式:\n"
            '[{"id": "1", "task": "子任务描述", "dependencies": [], "priority": "high/medium/low"}]'
        )
        try:
            content = response.content
            start = content.find("[")
            end = content.rfind("]") + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
        except Exception:
            pass
        return [{"id": "1", "task": task, "dependencies": [], "priority": "high"}]


class ResearcherAgent(BaseAgent):
    """研究Agent - 自带搜索工具"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig(
            agent_name="Researcher",
            system_prompt="你是一个信息研究专家。使用搜索工具收集信息，验证可靠性，整理总结发现。每次搜索后分析结果质量，必要时换关键词重搜。",
        ))
        super().__init__(**kwargs)


class CoderAgent(BaseAgent):
    """编码Agent - 自带代码执行工具"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig(
            agent_name="Coder",
            system_prompt=(
                "你是一个编程专家。编写高质量代码，注意：\n"
                "1. 先理解需求再编码\n"
                "2. 编写后用代码执行工具验证\n"
                "3. 处理边界情况和错误\n"
                "4. 代码要简洁可读"
            ),
        ))
        super().__init__(**kwargs)


class ReviewerAgent(BaseAgent):
    """审查Agent"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig(
            agent_name="Reviewer",
            system_prompt=(
                "你是一个质量审查专家。审查标准：\n"
                "1. 安全性：注入、泄露、权限\n"
                "2. 性能：复杂度、资源使用\n"
                "3. 可维护性：命名、结构、注释\n"
                "4. 正确性：逻辑、边界、异常\n"
                "输出评分(1-10)和具体改进建议。"
            ),
        ))
        super().__init__(**kwargs)


class SummarizerAgent(BaseAgent):
    """总结Agent"""

    def __init__(self, **kwargs: Any):
        kwargs.setdefault("config", AgentConfig(
            agent_name="Summarizer",
            system_prompt="你是信息整合专家。从多个输入源提取关键要点，生成清晰简洁的总结。结构化输出：要点、结论、建议。",
        ))
        super().__init__(**kwargs)

