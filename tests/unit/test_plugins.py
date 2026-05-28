"""插件系统测试"""

import pytest
from agentflow.core.plugins import (
    Plugin,
    PluginMeta,
    PluginManager,
    CalculatorPlugin,
    WebSearchPlugin,
    auto_load_plugins,
)


def test_plugin_meta():
    """测试插件元数据"""
    meta = PluginMeta(
        name="test_plugin",
        version="1.0.0",
        description="测试插件",
        plugin_type="tool",
    )
    assert meta.name == "test_plugin"
    assert meta.enabled is True


def test_calculator_plugin():
    """测试计算器插件"""
    plugin = CalculatorPlugin()
    meta = plugin.meta()

    assert meta.name == "builtin_calculator"
    assert meta.plugin_type == "tool"


def test_web_search_plugin():
    """测试搜索插件"""
    plugin = WebSearchPlugin()
    meta = plugin.meta()

    assert meta.name == "builtin_web_search"


def test_plugin_manager():
    """测试插件管理器"""
    manager = PluginManager()

    manager.register(CalculatorPlugin())
    manager.register(WebSearchPlugin())

    plugins = manager.list_plugins()
    assert len(plugins) == 2


def test_plugin_manager_by_type():
    """测试按类型筛选"""
    manager = PluginManager()
    manager.register(CalculatorPlugin())

    tools = manager.list_by_type("tool")
    assert len(tools) == 1
    assert tools[0].plugin_type == "tool"


def test_plugin_enable_disable():
    """测试启用/禁用"""
    manager = PluginManager()
    manager.register(CalculatorPlugin())

    assert manager.disable("builtin_calculator") is True
    meta = manager.list_plugins()[0]
    assert meta.enabled is False

    assert manager.enable("builtin_calculator") is True
    meta = manager.list_plugins()[0]
    assert meta.enabled is True


def test_plugin_unload():
    """测试卸载插件"""
    manager = PluginManager()
    manager.register(CalculatorPlugin())

    assert manager.unload("builtin_calculator") is True
    assert len(manager.list_plugins()) == 0
    assert manager.unload("nonexistent") is False


def test_auto_load_plugins():
    """测试自动加载"""
    manager = PluginManager()
    # 直接测试内置插件注册
    manager.register(CalculatorPlugin())
    manager.register(WebSearchPlugin())

    assert len(manager.list_plugins()) == 2
