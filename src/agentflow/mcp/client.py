"""MCP Client — 连接外部 MCP Server，将其工具导入 AgentFlow。

用法::

    from agentflow.mcp.client import MCPToolClient

    # 连接本地 MCP Server（stdio 模式）
    async with MCPToolClient(command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]) as client:
        tools = client.get_tools()          # 获取 AgentFlow Tool 对象
        registry.register_many(tools)       # 注册到工具注册表
        result = await tools[0].execute(path="/tmp/test.txt")  # 直接调用

    # 连接远程 MCP Server（SSE 模式）
    async with MCPToolClient(url="http://localhost:8766/sse") as client:
        tools = client.get_tools()
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from agentflow.tools.base import Tool, ToolRegistry


class MCPTool(Tool):
    """包装外部 MCP 工具为 AgentFlow Tool。"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        session: Any,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self._session = session

    async def execute(self, **kwargs: Any) -> str:
        try:
            result = await self._session.call_tool(self.name, kwargs)
            # MCP 结果是 TextContent 列表
            parts = []
            for item in (result.content or []):
                if hasattr(item, "text"):
                    parts.append(item.text)
                else:
                    parts.append(str(item))
            return "\n".join(parts) if parts else "（无输出）"
        except Exception as e:
            return f"MCP 工具调用错误: {e}"


class MCPToolClient:
    """MCP 工具客户端 — 连接外部 MCP Server 并导入工具。

    支持 stdio 和 SSE 两种传输模式。用作 async context manager。
    """

    def __init__(
        self,
        command: str | None = None,
        args: list[str] | None = None,
        url: str | None = None,
        env: dict[str, str] | None = None,
    ):
        """
        Args:
            command: stdio 模式的可执行文件路径（如 "npx"、"python"）
            args: stdio 模式的命令参数
            url: SSE 模式的服务器 URL（如 "http://localhost:8766/sse"）
            env: 传递给子进程的环境变量
        """
        if not command and not url:
            raise ValueError("必须指定 command（stdio 模式）或 url（SSE 模式）")
        self._command = command
        self._args = args or []
        self._url = url
        self._env = env
        self._session = None
        self._read_stream = None
        self._write_stream = None
        self._cleanup = None
        self._tools: list[MCPTool] = []
        self._tool_defs: list[dict[str, Any]] = []

    async def __aenter__(self) -> MCPToolClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def connect(self) -> None:
        """建立连接并发现工具。"""
        from mcp import ClientSession

        if self._command:
            # stdio 模式
            from mcp.client.stdio import stdio_client
            from mcp import StdioServerParameters

            params = StdioServerParameters(
                command=self._command,
                args=self._args,
                env=self._env,
            )
            self._read_stream, self._write_stream = await stdio_client(params).__aenter__()
        elif self._url:
            # SSE 模式
            from mcp.client.sse import sse_client

            self._read_stream, self._write_stream = await sse_client(self._url).__aenter__()

        self._session = ClientSession(self._read_stream, self._write_stream)
        await self._session.__aenter__()
        await self._session.initialize()

        # 发现工具
        tools_result = await self._session.list_tools()
        self._tools = []
        self._tool_defs = []
        for t in tools_result.tools:
            params = t.inputSchema if t.inputSchema else {"type": "object", "properties": {}}
            tool = MCPTool(
                name=t.name,
                description=t.description or "",
                parameters=params,
                session=self._session,
            )
            self._tools.append(tool)
            self._tool_defs.append({
                "name": t.name,
                "description": t.description or "",
                "parameters": params,
            })

    async def close(self) -> None:
        """关闭连接。"""
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
        # stdio/sse client cleanup is handled by the context managers

    def get_tools(self) -> list[MCPTool]:
        """获取已发现的 MCP 工具（AgentFlow Tool 格式）。"""
        return list(self._tools)

    def get_tool_registry(self) -> ToolRegistry:
        """创建包含所有 MCP 工具的 ToolRegistry。"""
        registry = ToolRegistry()
        registry.register_many(self._tools)
        return registry

    def list_tools(self) -> list[dict[str, Any]]:
        """列出所有工具的 schema 描述。"""
        return list(self._tool_defs)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """直接调用指定工具。"""
        tool = next((t for t in self._tools if t.name == name), None)
        if tool is None:
            return f"工具不存在: {name}"
        return await tool.execute(**arguments)
