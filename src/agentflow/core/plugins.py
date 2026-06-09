"""插件系统 - Agent/Tool/Memory可插拔扩展"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class PluginMeta(BaseModel):
    """插件元数据"""
    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    plugin_type: str = "tool"  # tool / agent / memory / middleware
    entry_point: str = ""
    dependencies: list[str] = Field(default_factory=list)
    enabled: bool = True


class Plugin(ABC):
    """插件基类"""

    @abstractmethod
    def meta(self) -> PluginMeta:
        """返回插件元数据"""
        ...

    @abstractmethod
    def register(self, registry: Any) -> None:
        """注册到系统"""
        ...

    def on_load(self) -> None:
        """加载时钩子"""
        pass

    def on_unload(self) -> None:
        """卸载时钩子"""
        pass


class PluginManager:
    """插件管理器"""

    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._meta: dict[str, PluginMeta] = {}

    def register(self, plugin: Plugin) -> None:
        """注册插件"""
        meta = plugin.meta()
        self._plugins[meta.name] = plugin
        self._meta[meta.name] = meta

    def load_from_directory(self, directory: str | Path) -> int:
        """从目录加载插件"""
        plugin_dir = Path(directory)
        if not plugin_dir.exists():
            return 0

        loaded = 0
        for py_file in plugin_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            try:
                self._load_module(py_file)
                loaded += 1
            except Exception as e:
                print(f"加载插件失败 {py_file.name}: {e}")

        return loaded

    def _load_module(self, file_path: Path) -> None:
        """加载单个模块"""
        module_name = f"agentflow_plugin_{file_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # 查找Plugin子类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and issubclass(attr, Plugin) and attr is not Plugin):
                    plugin = attr()
                    self.register(plugin)
                    plugin.on_load()

    def load_from_entry_points(self) -> int:
        """从entry_points加载插件"""
        try:
            from importlib.metadata import entry_points
            agentflow_eps = entry_points(group="agentflow.plugins")
            loaded = 0
            for ep in agentflow_eps:
                try:
                    plugin_class = ep.load()
                    if issubclass(plugin_class, Plugin):
                        plugin = plugin_class()
                        self.register(plugin)
                        plugin.on_load()
                        loaded += 1
                except Exception as e:
                    print(f"加载entry_point插件失败 {ep.name}: {e}")
            return loaded
        except ImportError:
            return 0

    def get(self, name: str) -> Plugin | None:
        """获取插件"""
        return self._plugins.get(name)

    def list_plugins(self) -> list[PluginMeta]:
        """列出所有插件"""
        return list(self._meta.values())

    def list_by_type(self, plugin_type: str) -> list[PluginMeta]:
        """按类型列出插件"""
        return [m for m in self._meta.values() if m.plugin_type == plugin_type]

    def enable(self, name: str) -> bool:
        """启用插件"""
        if name in self._meta:
            self._meta[name].enabled = True
            return True
        return False

    def disable(self, name: str) -> bool:
        """禁用插件"""
        if name in self._meta:
            self._meta[name].enabled = False
            return True
        return False

    def unload(self, name: str) -> bool:
        """卸载插件"""
        plugin = self._plugins.pop(name, None)
        self._meta.pop(name, None)
        if plugin:
            plugin.on_unload()
            return True
        return False

    def register_all(self, registry: Any) -> None:
        """将所有已启用的插件注册到系统"""
        for name, plugin in self._plugins.items():
            meta = self._meta.get(name)
            if meta and meta.enabled:
                try:
                    plugin.register(registry)
                except Exception as e:
                    print(f"注册插件失败 {name}: {e}")


# ============ 内置插件示例 ============

class CalculatorPlugin(Plugin):
    """计算器插件示例"""

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="builtin_calculator",
            version="1.0.0",
            description="内置计算器工具插件",
            plugin_type="tool",
        )

    def register(self, registry: Any) -> None:
        from agentflow.tools.base import CalculatorTool
        if hasattr(registry, 'register'):
            registry.register(CalculatorTool())


class WebSearchPlugin(Plugin):
    """搜索插件示例"""

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="builtin_web_search",
            version="1.0.0",
            description="内置网络搜索工具插件",
            plugin_type="tool",
        )

    def register(self, registry: Any) -> None:
        from agentflow.tools.base import WebSearchTool
        if hasattr(registry, 'register'):
            registry.register(WebSearchTool())


# 全局插件管理器
plugin_manager = PluginManager()


def auto_load_plugins() -> int:
    """自动加载插件"""
    loaded = 0

    # 1. 加载内置插件
    plugin_manager.register(CalculatorPlugin())
    plugin_manager.register(WebSearchPlugin())
    loaded += 2

    # 2. 从插件目录加载
    plugin_dirs = [
        Path.home() / ".agentflow" / "plugins",
        Path("./plugins"),
    ]
    for d in plugin_dirs:
        if d.exists():
            loaded += plugin_manager.load_from_directory(d)

    # 3. 从entry_points加载
    loaded += plugin_manager.load_from_entry_points()

    return loaded
