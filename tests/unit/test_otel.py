"""OpenTelemetry集成测试"""

import pytest
from agentflow.core.otel import (
    OTelConfig,
    OTelTracer,
    OTelSpan,
    OTelMeter,
    get_otel_config,
    setup_opentelemetry,
)


def test_otel_config():
    """测试OTel配置"""
    config = OTelConfig()
    assert config.enabled is False
    assert config.service_name == "agentflow"


def test_otel_config_configure():
    """测试配置更新"""
    config = OTelConfig()
    config.configure(enabled=True, service_name="test-service", endpoint="http://localhost:4317")
    assert config.enabled is True
    assert config.service_name == "test-service"


def test_otel_tracer_disabled():
    """测试禁用状态的Tracer"""
    tracer = OTelTracer()
    with tracer.start_span("test") as span:
        span.set_attribute("key", "value")
        assert isinstance(span, OTelSpan)


def test_otel_span_noop():
    """测试空操作Span"""
    span = OTelSpan(None)
    span.set_attribute("key", "value")
    span.set_status("ok")
    span.add_event("test")
    # 不应抛出异常


def test_otel_meter_disabled():
    """测试禁用状态的Meter"""
    meter = OTelMeter()
    counter = meter.create_counter("test.counter")
    assert counter is None


def test_setup_opentelemetry_disabled():
    """测试禁用OTel"""
    setup_opentelemetry(enabled=False)
    config = get_otel_config()
    assert config.enabled is False
