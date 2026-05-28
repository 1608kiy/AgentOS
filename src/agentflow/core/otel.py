"""OpenTelemetry集成 - 生产级可观测性"""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator

from agentflow.core.config import AgentFlowConfig


class OTelConfig:
    """OpenTelemetry配置"""

    def __init__(self, config: AgentFlowConfig | None = None):
        self.enabled = False
        self.service_name = "agentflow"
        self.endpoint = "http://localhost:4317"
        self.exporter = "otlp"  # otlp / jaeger / zipkin

    def configure(
        self,
        enabled: bool = True,
        service_name: str = "agentflow",
        endpoint: str = "http://localhost:4317",
        exporter: str = "otlp",
    ) -> None:
        self.enabled = enabled
        self.service_name = service_name
        self.endpoint = endpoint
        self.exporter = exporter


_otel_config = OTelConfig()


def get_otel_config() -> OTelConfig:
    return _otel_config


def setup_opentelemetry(
    service_name: str = "agentflow",
    endpoint: str = "http://localhost:4317",
    enabled: bool = True,
) -> None:
    """初始化OpenTelemetry"""
    _otel_config.configure(
        enabled=enabled,
        service_name=service_name,
        endpoint=endpoint,
    )

    if not enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        except ImportError:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            exporter = ConsoleSpanExporter()

        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        _otel_config.enabled = True
    except ImportError:
        _otel_config.enabled = False


class OTelTracer:
    """OpenTelemetry追踪器包装"""

    def __init__(self, name: str = "agentflow"):
        self._name = name
        self._tracer = None
        self._enabled = False

        if _otel_config.enabled:
            try:
                from opentelemetry import trace
                self._tracer = trace.get_tracer(name)
                self._enabled = True
            except ImportError:
                pass

    @contextmanager
    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Generator[OTelSpan, None, None]:
        """创建Span"""
        if self._enabled and self._tracer:
            with self._tracer.start_as_current_span(name) as span:
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, str(v))
                yield OTelSpan(span)
        else:
            yield OTelSpan(None)

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """添加事件"""
        if self._enabled and self._tracer:
            from opentelemetry import trace
            span = trace.get_current_span()
            if span.is_recording():
                span.add_event(name, attributes or {})


class OTelSpan:
    """Span包装"""

    def __init__(self, span: Any):
        self._span = span

    def set_attribute(self, key: str, value: Any) -> None:
        if self._span and self._span.is_recording():
            self._span.set_attribute(key, str(value))

    def set_status(self, status: str, description: str = "") -> None:
        if self._span and self._span.is_recording():
            try:
                from opentelemetry.trace import Status, StatusCode
                if status == "error":
                    self._span.set_status(Status(StatusCode.ERROR, description))
                else:
                    self._span.set_status(Status(StatusCode.OK))
            except ImportError:
                pass

    def record_exception(self, exception: Exception) -> None:
        if self._span and self._span.is_recording():
            self._span.record_exception(exception)

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        if self._span and self._span.is_recording():
            self._span.add_event(name, attributes or {})


class OTelMeter:
    """OpenTelemetry指标"""

    def __init__(self, name: str = "agentflow"):
        self._meter = None
        self._enabled = False

        if _otel_config.enabled:
            try:
                from opentelemetry import metrics
                self._meter = metrics.get_meter(name)
                self._enabled = True
            except ImportError:
                pass

    def create_counter(self, name: str, description: str = "", unit: str = "1") -> Any:
        if self._enabled and self._meter:
            return self._meter.create_counter(name, description=description, unit=unit)
        return None

    def create_histogram(self, name: str, description: str = "", unit: str = "ms") -> Any:
        if self._enabled and self._meter:
            return self._meter.create_histogram(name, description=description, unit=unit)
        return None

    def record_duration(self, histogram: Any, duration_ms: float, attributes: dict[str, Any] | None = None) -> None:
        if histogram:
            histogram.record(duration_ms, attributes or {})


# 全局实例
otel_tracer = OTelTracer()
otel_meter = OTelMeter()
