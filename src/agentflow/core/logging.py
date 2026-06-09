"""日志与可观测性系统"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator
from uuid import uuid4

import structlog

from agentflow.core.config import LogFormat, LogLevel


def setup_logging(level: LogLevel = LogLevel.INFO, format: LogFormat = LogFormat.JSON) -> None:
    """配置日志系统"""
    # 配置structlog
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if format == LogFormat.CONSOLE:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.value)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(
            file=open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1) if sys.platform == "win32" else sys.stdout,
        ),
        cache_logger_on_first_use=True,
    )

    # 文件日志
    log_dir = Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "agentflow.log"
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(getattr(logging, level.value))
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logging.root.addHandler(file_handler)


def get_logger(name: str) -> structlog.BoundLogger:
    """获取日志器"""
    return structlog.get_logger(name)


class AgentLogger:
    """Agent专用日志器"""

    def __init__(self, agent_id: str, agent_name: str = ""):
        self.agent_id = agent_id
        self.agent_name = agent_name or agent_id
        self.logger = structlog.get_logger("agent").bind(
            agent_id=agent_id,
            agent_name=agent_name,
        )
        self._trace_id: str | None = None

    def set_trace_id(self, trace_id: str) -> None:
        """设置追踪ID"""
        self._trace_id = trace_id

    def log_agent_start(self, task: str) -> None:
        """记录Agent开始执行"""
        self.logger.info(
            "agent_started",
            task=task,
            trace_id=self._trace_id,
        )

    def log_agent_thinking(self, thought: str) -> None:
        """记录Agent思考过程"""
        self.logger.debug(
            "agent_thinking",
            thought=thought[:500],  # 截断长思考
            trace_id=self._trace_id,
        )

    def log_agent_action(self, action: str, result: str) -> None:
        """记录Agent执行动作"""
        self.logger.info(
            "agent_action",
            action=action,
            result_preview=result[:200],
            trace_id=self._trace_id,
        )

    def log_agent_error(self, error: Exception) -> None:
        """记录Agent错误"""
        self.logger.error(
            "agent_error",
            error_type=type(error).__name__,
            error_message=str(error),
            trace_id=self._trace_id,
        )

    def log_agent_complete(self, result: str, duration_ms: float) -> None:
        """记录Agent完成"""
        self.logger.info(
            "agent_completed",
            result_preview=result[:200],
            duration_ms=duration_ms,
            trace_id=self._trace_id,
        )

    def log_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """记录工具调用"""
        self.logger.info(
            "tool_call",
            tool_name=tool_name,
            arguments=arguments,
            trace_id=self._trace_id,
        )

    def log_tool_result(self, tool_name: str, result: str, is_error: bool = False) -> None:
        """记录工具结果"""
        self.logger.info(
            "tool_result",
            tool_name=tool_name,
            result_preview=result[:200],
            is_error=is_error,
            trace_id=self._trace_id,
        )


class TracingManager:
    """链路追踪管理器"""

    def __init__(self):
        self._traces: dict[str, TraceContext] = {}

    def start_trace(self, trace_id: str | None = None) -> str:
        """开始新的追踪"""
        trace_id = trace_id or str(uuid4())
        self._traces[trace_id] = TraceContext(trace_id=trace_id)
        return trace_id

    def end_trace(self, trace_id: str) -> TraceContext | None:
        """结束追踪"""
        trace = self._traces.pop(trace_id, None)
        if trace:
            trace.end_time = datetime.now()
        return trace

    def get_trace(self, trace_id: str) -> TraceContext | None:
        """获取追踪上下文"""
        return self._traces.get(trace_id)


class TraceContext:
    """追踪上下文"""

    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.spans: list[Span] = []
        self.start_time = datetime.now()
        self.end_time: datetime | None = None
        self.metadata: dict[str, Any] = {}

    @contextmanager
    def span(self, name: str, metadata: dict[str, Any] | None = None) -> Generator[Span, None, None]:
        """创建一个新的Span"""
        span = Span(
            name=name,
            trace_id=self.trace_id,
            metadata=metadata or {},
        )
        self.spans.append(span)
        try:
            yield span
        except Exception as e:
            span.set_error(e)
            raise
        finally:
            span.end()

    def add_event(self, name: str, data: dict[str, Any] | None = None) -> None:
        """添加事件"""
        event = Event(name=name, data=data or {})
        if self.spans:
            self.spans[-1].events.append(event)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "spans": [s.to_dict() for s in self.spans],
            "metadata": self.metadata,
        }


class Span:
    """追踪Span"""

    def __init__(self, name: str, trace_id: str, metadata: dict[str, Any] | None = None):
        self.name = name
        self.trace_id = trace_id
        self.metadata = metadata or {}
        self.start_time = datetime.now()
        self.end_time: datetime | None = None
        self.events: list[Event] = []
        self.error: Exception | None = None
        self._start_perf: float = time.perf_counter()

    def end(self) -> None:
        """结束Span"""
        self.end_time = datetime.now()

    def set_error(self, error: Exception) -> None:
        """设置错误"""
        self.error = error

    def add_event(self, name: str, data: dict[str, Any] | None = None) -> None:
        """添加事件"""
        self.events.append(Event(name=name, data=data or {}))

    @property
    def duration_ms(self) -> float:
        """计算持续时间（毫秒）"""
        return (time.perf_counter() - self._start_perf) * 1000

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": round(self.duration_ms, 2),
            "events": [e.to_dict() for e in self.events],
            "error": str(self.error) if self.error else None,
            "metadata": self.metadata,
        }


class Event:
    """追踪事件"""

    def __init__(self, name: str, data: dict[str, Any] | None = None):
        self.name = name
        self.data = data or {}
        self.timestamp = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


# 全局追踪管理器
tracing_manager = TracingManager()
