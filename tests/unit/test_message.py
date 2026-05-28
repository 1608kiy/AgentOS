"""消息系统测试"""

import pytest
from agentflow.core.message import Message, ConversationHistory, ToolCall, ToolResult, MessageRole


def test_message_creation():
    msg = Message.user("Hello")
    assert msg.role.value == "user"
    assert msg.content == "Hello"
    assert msg.id is not None


def test_message_types():
    system_msg = Message.system("System prompt")
    user_msg = Message.user("User message")
    assistant_msg = Message.assistant("Assistant message")
    tool_msg = Message.tool("Tool result", name="test_tool")

    assert system_msg.role.value == "system"
    assert user_msg.role.value == "user"
    assert assistant_msg.role.value == "assistant"
    assert tool_msg.role.value == "tool"
    assert tool_msg.name == "test_tool"


def test_message_to_dict():
    msg = Message.user("Hello")
    d = msg.to_dict()
    assert d["role"] == "user"
    assert d["content"] == "Hello"


def test_conversation_history():
    history = ConversationHistory()
    history.add_user("Hello")
    history.add_assistant("Hi there!")
    history.add_system("System message")

    assert len(history) == 3
    assert len(history.get_messages()) == 3
    assert len(history.get_messages(MessageRole.USER)) == 1
    assert len(history.get_messages(MessageRole.ASSISTANT)) == 1


def test_conversation_to_dicts():
    history = ConversationHistory()
    history.add_user("Hello")
    history.add_assistant("Hi!")

    dicts = history.to_dicts()
    assert len(dicts) == 2
    assert dicts[0]["role"] == "user"


def test_conversation_clear():
    history = ConversationHistory()
    history.add_user("Hello")
    history.clear()
    assert len(history) == 0


def test_tool_call():
    tc = ToolCall(name="calculator", arguments={"expression": "2+2"})
    assert tc.name == "calculator"
    assert tc.arguments["expression"] == "2+2"
    assert tc.id is not None


def test_tool_result():
    result = ToolResult(call_id="123", content="4", is_error=False)
    assert result.content == "4"
    assert result.is_error is False
    assert result.call_id == "123"


def test_tool_result_error():
    result = ToolResult(call_id="123", content="Error occurred", is_error=True)
    assert result.is_error is True
