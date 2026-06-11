"""MCP Server — 将 AgentFlow 的 ToolRegistry 暴露为 MCP 工具服务器。

外部 MCP 客户端（Claude Code、Cursor 等）可以直接调用 AgentFlow 的工具。

用法::

    # Python API
    from agentflow.mcp.server import create_mcp_server
    from agentflow.tools.base import create_default_registry

    registry = create_default_registry()
    server = create_mcp_server(registry, name="agentflow-tools")
    server.run()  # 默认 stdio 传输

    # CLI
    agentflow mcp-server          # stdio 模式（Claude Code 集成）
    agentflow mcp-server --http   # SSE/HTTP 模式（远程访问）
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from agentflow.tools.base import Tool, ToolRegistry


def _convert_parameters(tool: Tool) -> dict[str, Any]:
    """将 AgentFlow 工具参数定义转为 MCP JSON Schema 格式。"""
    params = tool.parameters or {}
    # MCP 要求 properties 和 type 字段存在
    if not params:
        return {
            "type": "object",
            "properties": {},
        }
    return params


def create_mcp_server(
    registry: ToolRegistry,
    name: str = "agentflow-tools",
    instructions: str | None = None,
) -> FastMCP:
    """从 ToolRegistry 创建 MCP Server。

    Args:
        registry: AgentFlow 工具注册表
        name: MCP 服务器名称
        instructions: 服务器说明（MCP 客户端可见）

    Returns:
        FastMCP 实例，可直接调用 server.run()
    """
    mcp = FastMCP(
        name=name,
        instructions=instructions or "AgentFlow 工具集合 — 包含计算、搜索、文件操作、代码执行等工具。",
    )

    for tool_def in registry.list_tools():
        tool_instance = registry.get(tool_def.name)
        if tool_instance is None:
            continue

        # 用闭包捕获 tool_instance，避免循环变量引用问题
        def _make_handler(t: Tool):
            async def handler(**kwargs: Any) -> str:
                try:
                    result = await t.execute(**kwargs)
                    return result if isinstance(result, str) else str(result)
                except Exception as e:
                    return f"工具执行错误: {e}"
            return handler

        handler = _make_handler(tool_instance)
        # 设置函数名和文档，MCP 会用这些作为工具描述
        handler.__name__ = tool_def.name
        handler.__doc__ = tool_def.description

        mcp.tool(name=tool_def.name, description=tool_def.description)(handler)

    return mcp


def run_server_stdio(registry: ToolRegistry, name: str = "agentflow-tools") -> None:
    """以 stdio 模式运行 MCP Server（适用于 Claude Code 等本地 CLI 工具）。"""
    server = create_mcp_server(registry, name=name)
    server.run(transport="stdio")


def run_server_sse(
    registry: ToolRegistry,
    name: str = "agentflow-tools",
    host: str = "0.0.0.0",
    port: int = 8766,
) -> None:
    """以 SSE/HTTP 模式运行 MCP Server（适用于远程访问）。"""
    server = create_mcp_server(registry, name=name)
    server.run(transport="sse", host=host, port=port)
