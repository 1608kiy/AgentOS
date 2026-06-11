"""MCP 工具协议测试 - Server + Client"""

import pytest
from agentflow.tools.base import ToolRegistry, CalculatorTool, Tool


# ============ MCP Server 测试 ============

def test_create_mcp_server():
    """测试从 ToolRegistry 创建 MCP Server"""
    from agentflow.mcp.server import create_mcp_server

    registry = ToolRegistry()
    registry.register(CalculatorTool())
    server = create_mcp_server(registry, name="test-server")
    assert server is not None


def test_create_mcp_server_empty_registry():
    """测试空注册表也能创建 MCP Server"""
    from agentflow.mcp.server import create_mcp_server

    server = create_mcp_server(ToolRegistry())
    assert server is not None


def test_convert_parameters():
    """测试参数格式转换"""
    from agentflow.mcp.server import _convert_parameters

    tool = CalculatorTool()
    params = _convert_parameters(tool)
    assert params["type"] == "object"
    assert "expression" in params["properties"]


# ============ MCP Client 测试 ============

def test_mcp_tool_creation():
    """测试 MCPTool 对象创建"""
    from agentflow.mcp.client import MCPTool

    tool = MCPTool(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {"input": {"type": "string"}}},
        session=None,
    )
    assert tool.name == "test_tool"
    assert tool.description == "A test tool"
    assert tool.to_definition().name == "test_tool"


@pytest.mark.asyncio
async def test_mcp_tool_execute_with_no_session():
    """测试 MCPTool 在 session 为 None 时优雅报错"""
    from agentflow.mcp.client import MCPTool

    tool = MCPTool(name="test", description="test", parameters={}, session=None)
    result = await tool.execute()
    assert "错误" in result


def test_mcp_tool_client_requires_args():
    """测试 MCPToolClient 必须指定 command 或 url"""
    from agentflow.mcp.client import MCPToolClient

    with pytest.raises(ValueError, match="必须指定"):
        MCPToolClient()


def test_mcp_tool_client_stdio_params():
    """测试 MCPToolClient stdio 参数配置"""
    from agentflow.mcp.client import MCPToolClient

    client = MCPToolClient(command="echo", args=["hello"])
    assert client._command == "echo"
    assert client._args == ["hello"]
    assert client._url is None


def test_mcp_tool_client_sse_params():
    """测试 MCPToolClient SSE 参数配置"""
    from agentflow.mcp.client import MCPToolClient

    client = MCPToolClient(url="http://localhost:8766/sse")
    assert client._url == "http://localhost:8766/sse"
    assert client._command is None


def test_mcp_tool_client_get_tools_empty():
    """测试未连接时 get_tools 返回空列表"""
    from agentflow.mcp.client import MCPToolClient

    client = MCPToolClient(command="echo")
    assert client.get_tools() == []
    assert client.list_tools() == []
