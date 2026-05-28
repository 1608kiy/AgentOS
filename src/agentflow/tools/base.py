"""工具系统 - 可扩展的工具注册与调用"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: list[str] | None = None


class ToolDefinition(BaseModel):
    """工具定义"""
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    def to_function_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class Tool(ABC):
    """工具抽象基类"""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, 'name') or not cls.name:
            cls.name = cls.__name__.lower().replace('tool', '')

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        ...

    def to_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    def to_function_schema(self) -> dict[str, Any]:
        return self.to_definition().to_function_schema()


class ToolRegistry:
    """工具注册中心"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def register_many(self, tools: list[Tool]) -> None:
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return [tool.to_definition() for tool in self._tools.values()]

    def to_function_schemas(self) -> list[dict[str, Any]]:
        return [tool.to_function_schema() for tool in self._tools.values()]

    def has(self, name: str) -> bool:
        return name in self._tools

    def remove(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def clear(self) -> None:
        self._tools.clear()

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# ============ 内置工具 ============


class CalculatorTool(Tool):
    """计算器工具 - 安全版"""
    name = "calculator"
    description = "执行数学计算。支持基本运算和数学函数。"
    parameters = {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "数学表达式，如 '2 + 3 * 4' 或 'sqrt(16)'",
            }
        },
        "required": ["expression"],
    }

    # 白名单：只允许这些名称出现在表达式中
    _SAFE_NAMES: dict[str, Any] = {}

    def __init__(self) -> None:
        import math
        self._SAFE_NAMES = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow,
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
            "tan": math.tan, "log": math.log, "log10": math.log10,
            "exp": math.exp, "pi": math.pi, "e": math.e,
            "ceil": math.ceil, "floor": math.floor,
        }

    async def execute(self, expression: str = "", **kwargs: Any) -> str:
        try:
            # 预检查：拒绝包含危险模式的表达式
            dangerous = ["import", "exec", "eval", "__", "open", "os.", "sys.", "subprocess"]
            for pattern in dangerous:
                if pattern in expression.lower():
                    return f"安全拒绝: 表达式包含禁止的模式 '{pattern}'"

            result = eval(expression, {"__builtins__": {}}, self._SAFE_NAMES)
            return str(result)
        except Exception as e:
            return f"计算错误: {e}"


class WebSearchTool(Tool):
    """网络搜索工具 - 真实API版"""
    name = "web_search"
    description = "搜索网络获取信息。支持Tavily/SerpAPI/DuckDuckGo。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词",
            },
            "num_results": {
                "type": "integer",
                "description": "返回结果数量",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def __init__(self) -> None:
        self._tavily_key = os.getenv("TAVILY_API_KEY", "")
        self._serpapi_key = os.getenv("SERPAPI_API_KEY", "")

    async def execute(self, query: str = "", num_results: int = 5, **kwargs: Any) -> str:
        # 优先使用Tavily
        if self._tavily_key:
            return await self._search_tavily(query, num_results)
        # 其次使用SerpAPI
        if self._serpapi_key:
            return await self._search_serpapi(query, num_results)
        # 兜底：使用DuckDuckGo（无需API key）
        return await self._search_duckduckgo(query, num_results)

    async def _search_tavily(self, query: str, num_results: int) -> str:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self._tavily_key,
                        "query": query,
                        "max_results": num_results,
                    },
                    timeout=15.0,
                )
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    return f"未找到 '{query}' 的相关结果"

                lines = [f"搜索结果 (查询: '{query}'):"]
                for i, r in enumerate(results[:num_results], 1):
                    title = r.get("title", "")
                    snippet = r.get("content", "")[:200]
                    url = r.get("url", "")
                    lines.append(f"{i}. {title}\n   {snippet}\n   来源: {url}")
                return "\n".join(lines)
        except Exception as e:
            return f"Tavily搜索错误: {e}"

    async def _search_serpapi(self, query: str, num_results: int) -> str:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://serpapi.com/search",
                    params={
                        "q": query,
                        "api_key": self._serpapi_key,
                        "num": num_results,
                        "engine": "google",
                    },
                    timeout=15.0,
                )
                data = resp.json()
                organic = data.get("organic_results", [])
                if not organic:
                    return f"未找到 '{query}' 的相关结果"

                lines = [f"搜索结果 (查询: '{query}'):"]
                for i, r in enumerate(organic[:num_results], 1):
                    title = r.get("title", "")
                    snippet = r.get("snippet", "")[:200]
                    link = r.get("link", "")
                    lines.append(f"{i}. {title}\n   {snippet}\n   来源: {link}")
                return "\n".join(lines)
        except Exception as e:
            return f"SerpAPI搜索错误: {e}"

    async def _search_duckduckgo(self, query: str, num_results: int) -> str:
        """DuckDuckGo搜索（无需API key）"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_redirect": "1"},
                    headers={"User-Agent": "AgentFlow/0.1"},
                    timeout=15.0,
                )
                data = resp.json()
                results = data.get("RelatedTopics", [])
                if not results:
                    return f"未找到 '{query}' 的相关结果（DuckDuckGo）"

                lines = [f"搜索结果 (查询: '{query}'):"]
                count = 0
                for r in results:
                    if count >= num_results:
                        break
                    text = r.get("Text", "")
                    url = r.get("FirstURL", "")
                    if text:
                        count += 1
                        lines.append(f"{count}. {text[:200]}\n   来源: {url}")
                return "\n".join(lines) if count > 0 else f"未找到 '{query}' 的相关结果"
        except Exception as e:
            return f"DuckDuckGo搜索错误: {e}"


class FileReaderTool(Tool):
    """文件读取工具"""
    name = "file_reader"
    description = "读取文件内容。"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "文件路径"},
            "max_size": {"type": "integer", "description": "最大读取字节数", "default": 100000},
        },
        "required": ["file_path"],
    }

    async def execute(self, file_path: str = "", max_size: int = 100000, **kwargs: Any) -> str:
        try:
            path = Path(file_path)
            if not path.exists():
                return f"文件不存在: {file_path}"
            if not path.is_file():
                return f"不是文件: {file_path}"
            if path.stat().st_size > max_size:
                return f"文件过大 ({path.stat().st_size} bytes)，超过限制 ({max_size} bytes)"
            return path.read_text(encoding="utf-8")
        except Exception as e:
            return f"读取文件错误: {e}"


class FileWriterTool(Tool):
    """文件写入工具"""
    name = "file_writer"
    description = "写入文件内容。"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "文件内容"},
        },
        "required": ["file_path", "content"],
    }

    async def execute(self, file_path: str = "", content: str = "", **kwargs: Any) -> str:
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return f"文件已写入: {file_path} ({len(content)} 字符)"
        except Exception as e:
            return f"写入文件错误: {e}"


class CodeExecutorTool(Tool):
    """代码执行工具 - 沙箱版（subprocess隔离 + 超时 + 受限builtins）"""
    name = "code_executor"
    description = "在沙箱中执行Python代码并返回结果。有超时和安全限制。"
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python代码"},
            "timeout": {"type": "integer", "description": "超时秒数", "default": 10},
        },
        "required": ["code"],
    }

    # 禁止的模块/函数
    _BLOCKED = frozenset([
        "os.system", "os.popen", "subprocess", "shutil.rmtree",
        "socket", "ctypes", "importlib", "__import__",
        "eval", "exec", "compile", "globals", "locals",
        "open",  # 限制文件操作
    ])

    async def execute(self, code: str = "", timeout: int = 10, **kwargs: Any) -> str:
        # 预检查
        code_lower = code.lower()
        for blocked in self._BLOCKED:
            if blocked in code_lower:
                return f"安全拒绝: 代码包含禁止的操作 '{blocked}'"

        # 使用subprocess在隔离环境中执行
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._run_in_subprocess, code, timeout
            )
            return result
        except Exception as e:
            return f"代码执行错误: {e}"

    def _run_in_subprocess(self, code: str, timeout: int) -> str:
        """在子进程中执行代码"""
        try:
            proc = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=None,
                env={},
            )
            output = ""
            if proc.stdout:
                output += proc.stdout
            if proc.stderr:
                output += f"\nSTDERR:\n{proc.stderr}"
            if proc.returncode != 0:
                output += f"\n退出码: {proc.returncode}"
            return output or "代码执行成功（无输出）"
        except subprocess.TimeoutExpired:
            return f"代码执行超时（{timeout}秒）"
        except Exception as e:
            return f"子进程错误: {e}"


class APICallTool(Tool):
    """API调用工具"""
    name = "api_call"
    description = "发送HTTP请求调用API。"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "API URL"},
            "method": {"type": "string", "description": "HTTP方法", "enum": ["GET", "POST", "PUT", "DELETE"], "default": "GET"},
            "headers": {"type": "object", "description": "请求头"},
            "body": {"type": "object", "description": "请求体"},
            "timeout": {"type": "integer", "description": "超时秒数", "default": 30},
        },
        "required": ["url"],
    }

    async def execute(
        self,
        url: str = "",
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        timeout: int = 30,
        **kwargs: Any,
    ) -> str:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body,
                    timeout=float(timeout),
                )
                return f"状态码: {response.status_code}\n响应: {response.text[:2000]}"
        except Exception as e:
            return f"API调用错误: {e}"


def create_default_registry() -> ToolRegistry:
    """创建默认工具注册表"""
    registry = ToolRegistry()
    registry.register_many([
        CalculatorTool(),
        WebSearchTool(),
        FileReaderTool(),
        FileWriterTool(),
        CodeExecutorTool(),
        APICallTool(),
    ])
    return registry
