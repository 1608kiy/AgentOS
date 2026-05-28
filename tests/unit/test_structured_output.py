"""结构化输出解析测试"""

import pytest
from pydantic import BaseModel
from agentflow.utils.structured_output import (
    extract_json_from_text,
    parse_structured_output,
    parse_list_output,
)


class UserModel(BaseModel):
    name: str
    age: int
    email: str = ""


def test_extract_json_from_text():
    """测试从文本提取JSON"""
    # 直接JSON
    assert extract_json_from_text('{"name": "test"}') == {"name": "test"}

    # 代码块中的JSON
    text = '这是结果:\n```json\n{"name": "test"}\n```\n结束'
    assert extract_json_from_text(text) == {"name": "test"}

    # 数组
    text = '结果: [{"name": "a"}, {"name": "b"}]'
    result = extract_json_from_text(text)
    assert isinstance(result, list)
    assert len(result) == 2


def test_extract_json_no_json():
    """测试无JSON的情况"""
    assert extract_json_from_text("没有JSON的文本") is None
    assert extract_json_from_text("") is None


def test_parse_structured_output():
    """测试结构化输出解析"""
    text = '{"name": "张三", "age": 25, "email": "test@example.com"}'
    result = parse_structured_output(text, UserModel)
    assert result is not None
    assert result.name == "张三"
    assert result.age == 25


def test_parse_structured_output_from_code_block():
    """测试从代码块解析"""
    text = '分析结果:\n```json\n{"name": "李四", "age": 30}\n```'
    result = parse_structured_output(text, UserModel)
    assert result is not None
    assert result.name == "李四"


def test_parse_list_output():
    """测试列表解析"""
    text = '[{"name": "A", "age": 1}, {"name": "B", "age": 2}]'
    results = parse_list_output(text, UserModel)
    assert len(results) == 2
    assert results[0].name == "A"


def test_parse_list_output_single():
    """测试单个对象列表解析"""
    text = '{"name": "A", "age": 1}'
    results = parse_list_output(text, UserModel)
    assert len(results) == 1


def test_parse_invalid():
    """测试无效输入"""
    assert parse_structured_output("not json", UserModel) is None
    assert parse_list_output("not json", UserModel) == []
