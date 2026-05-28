"""Agent基类 - ReAct模式实现（企业级增强版）"""

from __future__ import annotations

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
        """主执行循环 - ReAct模式"""
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

        # H2: 注入记忆上下文
        memory_context = self.memory.get_context_string()
        if memory_context:
            user_content = f"[记忆上下文]\n{memory_context}\n\n[当前任务]\n{user_content}"

        self.conversation.add_user(user_content)

        token_usage: dict[str, int] = {}

        try:
            for iteration in range(self.state.max_iterations):
                self.state.increment_iteration()

                # 1. Think
                thought = await self._think()
                self.logger.log_agent_thinking(thought)

                # 2. Decide - H5: LLM决策
                if await self._should_answer(thought):
                    answer = await self._generate_answer()
                    duration = (time.perf_counter() - start_time) * 1000
                    self.state.set_status(AgentStatus.COMPLETED)
                    self.logger.log_agent_complete(answer, duration)

                    # H2: 将结果存入记忆
                    await self.memory.remember(
                        f"任务: {task}\n结果: {answer[:500]}",
                        memory_type="short",
                    )

                    response = AgentResponse(
                        agent_id=self.id,
                        content=answer,
                        iterations=self.state.iteration,
                        duration_ms=duration,
                        token_usage=token_usage,
                        metadata={"trace_id": trace_id},
                    )

                    # 中间件：执行后
                    for mw in self._middlewares:
                        response = await mw.after_run(self, response)

                    tracing_manager.end_trace(trace_id)
                    return response

                # 3. Act
                tool_call = await self._decide_action(thought)
                if tool_call:
                    result = await self._execute_tool(tool_call)
                    self.logger.log_agent_action(tool_call.name, result.content)

                    self.conversation.add_tool(
                        f"工具 {tool_call.name} 的结果:\n{result.content}",
                        name=tool_call.name,
                    )
                else:
                    answer = await self._generate_answer()
                    duration = (time.perf_counter() - start_time) * 1000
                    self.state.set_status(AgentStatus.COMPLETED)

                    response = AgentResponse(
                        agent_id=self.id,
                        content=answer,
                        iterations=self.state.iteration,
                        duration_ms=duration,
                        token_usage=token_usage,
                    )
                    for mw in self._middlewares:
                        response = await mw.after_run(self, response)
                    tracing_manager.end_trace(trace_id)
                    return response

            # 达到最大迭代
            answer = await self._generate_answer()
            duration = (time.perf_counter() - start_time) * 1000
            self.state.set_status(AgentStatus.COMPLETED)

            response = AgentResponse(
                agent_id=self.id,
                content=answer,
                iterations=self.state.iteration,
                duration_ms=duration,
                token_usage=token_usage,
            )
            for mw in self._middlewares:
                response = await mw.after_run(self, response)
            tracing_manager.end_trace(trace_id)
            return response

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

    async def _think(self) -> str:
        """思考过程"""
        messages = self.conversation.get_messages()
        think_prompt = Message.user(
            "请分析当前情况，决定下一步行动。"
            "如果需要使用工具，说明需要使用哪个工具以及原因。"
            "如果已经有足够信息回答，请直接给出答案。"
        )
        messages.append(think_prompt)

        response = await self.llm.chat(messages)
        self._total_tokens += response.total_tokens
        return response.content

    async def _should_answer(self, thought: str) -> bool:
        """H5: 使用LLM决策是否应该直接回答"""
        messages = [
            Message.system(
                "你是一个决策助手。根据给定的思考内容，判断是否已经有足够信息来回答用户的问题。\n"
                "如果已经有足够信息，回复 'YES'。\n"
                "如果还需要使用工具获取更多信息，回复 'NO'。\n"
                "只回复 YES 或 NO，不要输出其他内容。"
            ),
            Message.user(f"思考内容:\n{thought}\n\n是否有足够信息回答？"),
        ]

        try:
            response = await self.llm.chat(messages)
            decision = response.content.strip().upper()
            return "YES" in decision
        except Exception:
            # 降级到关键词匹配
            answer_keywords = ["答案", "结论", "总结", "回答", "answer", "conclusion", "summary"]
            return any(kw in thought.lower() for kw in answer_keywords)

    async def _decide_action(self, thought: str) -> ToolCall | None:
        """决定执行的动作"""
        tool_schemas = self.tools.to_function_schemas()
        if not tool_schemas:
            return None

        messages = self.conversation.get_messages()
        messages.append(Message.assistant(thought))
        messages.append(Message.user(
            "基于以上分析，请决定要调用的工具。"
            "如果没有合适的工具可以使用，返回空。"
        ))

        try:
            response = await self.llm.function_call(messages, tool_schemas)
            self._total_tokens += response.total_tokens
            if response.tool_calls:
                tc = response.tool_calls[0]
                args = tc["function"]["arguments"]
                return ToolCall(
                    id=tc.get("id", str(uuid4())),
                    name=tc["function"]["name"],
                    arguments=json.loads(args) if isinstance(args, str) else args,
                )
        except Exception:
            pass

        return None

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
        """生成最终答案"""
        messages = self.conversation.get_messages()
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
        async for chunk in self.llm.stream_chat(messages):
            yield chunk

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
    """标准ReAct Agent"""

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    async def _think(self) -> str:
        messages = self.conversation.get_messages()
        tool_list = ", ".join(t.name for t in self.tools.list_tools())
        think_prompt = Message.user(
            f"当前可用工具: [{tool_list}]\n\n"
            "请按以下步骤思考:\n"
            "1. 分析当前任务和已有信息\n"
            "2. 判断是否需要使用工具\n"
            "3. 如果需要工具，说明使用哪个工具及原因\n"
            "4. 如果已有足够信息，直接给出答案\n\n"
            "请开始思考:"
        )
        messages.append(think_prompt)
        response = await self.llm.chat(messages)
        self._total_tokens += response.total_tokens
        return response.content


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


# 需要在顶部导入asyncio
import asyncio
