"""工具系统测试"""

import pytest
from agentflow.tools.base import (
    Tool,
    ToolRegistry,
    CalculatorTool,
    WebSearchTool,
    FileReaderTool,
    FileWriterTool,
    CodeExecutorTool,
    create_default_registry,
)


@pytest.mark.asyncio
async def test_calculator_basic():
    """测试基本计算"""
    tool = CalculatorTool()
    assert await tool.execute(expression="2 + 3") == "5"
    assert await tool.execute(expression="10 * 5") == "50"
    assert await tool.execute(expression="100 / 4") == "25.0"


@pytest.mark.asyncio
async def test_calculator_math_functions():
    """测试数学函数"""
    tool = CalculatorTool()
    assert await tool.execute(expression="sqrt(16)") == "4.0"
    assert await tool.execute(expression="abs(-5)") == "5"
    assert await tool.execute(expression="max(1, 2, 3)") == "3"


@pytest.mark.asyncio
async def test_calculator_security_reject():
    """测试计算器安全拒绝"""
    tool = CalculatorTool()
    result = await tool.execute(expression="__import__('os').system('ls')")
    assert "安全拒绝" in result


@pytest.mark.asyncio
async def test_calculator_error():
    """测试计算错误处理"""
    tool = CalculatorTool()
    result = await tool.execute(expression="1/0")
    assert "错误" in result


@pytest.mark.asyncio
async def test_web_search_duckduckgo():
    """测试DuckDuckGo搜索（无需API key）"""
    tool = WebSearchTool()
    result = await tool.execute(query="Python programming", num_results=3)
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_file_reader_not_found():
    """测试文件读取 - 文件不存在"""
    tool = FileReaderTool()
    result = await tool.execute(file_path="/nonexistent/file.txt")
    assert "不存在" in result


@pytest.mark.asyncio
async def test_file_writer_and_reader(tmp_path):
    """测试文件写入和读取"""
    writer = FileWriterTool()
    reader = FileReaderTool()

    test_file = str(tmp_path / "test.txt")
    test_content = "Hello, AgentFlow!"

    # 写入
    write_result = await writer.execute(file_path=test_file, content=test_content)
    assert "已写入" in write_result

    # 读取
    read_result = await reader.execute(file_path=test_file)
    assert read_result == test_content


@pytest.mark.asyncio
async def test_file_reader_size_limit(tmp_path):
    """测试文件大小限制"""
    writer = FileWriterTool()
    reader = FileReaderTool()

    test_file = str(tmp_path / "large.txt")
    await writer.execute(file_path=test_file, content="x" * 1000)

    result = await reader.execute(file_path=test_file, max_size=100)
    assert "过大" in result


@pytest.mark.asyncio
async def test_code_executor_safe():
    """测试代码执行 - 安全代码"""
    tool = CodeExecutorTool()
    result = await tool.execute(code="print(2 + 3)", timeout=5)
    assert "5" in result


@pytest.mark.asyncio
async def test_code_executor_blocked():
    """测试代码执行 - 被阻止的代码"""
    tool = CodeExecutorTool()
    result = await tool.execute(code="import os; os.system('ls')")
    assert "安全拒绝" in result


@pytest.mark.asyncio
async def test_code_executor_timeout():
    """测试代码执行 - 超时"""
    tool = CodeExecutorTool()
    result = await tool.execute(code="import time; time.sleep(10)", timeout=1)
    assert "超时" in result


def test_tool_registry():
    """测试工具注册表"""
    registry = ToolRegistry()
    tool = CalculatorTool()
    registry.register(tool)

    assert registry.has("calculator")
    assert len(registry) == 1
    assert registry.get("calculator") is tool


def test_tool_registry_remove():
    """测试工具移除"""
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    assert registry.remove("calculator") is True
    assert registry.has("calculator") is False
    assert registry.remove("nonexistent") is False


def test_tool_schemas():
    """测试工具Schema"""
    registry = create_default_registry()
    schemas = registry.to_function_schemas()

    assert len(schemas) >= 5
    names = [s["name"] for s in schemas]
    assert "calculator" in names
    assert "web_search" in names
    assert "code_executor" in names


def test_tool_definition():
    """测试工具定义"""
    tool = CalculatorTool()
    defn = tool.to_definition()

    assert defn.name == "calculator"
    assert "expression" in str(defn.parameters)
