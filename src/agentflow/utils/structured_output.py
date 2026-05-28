"""结构化输出解析工具"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def extract_json_from_text(text: str) -> Any:
    """从LLM输出中提取JSON"""
    # 1. 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. 提取```json代码块
    json_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if json_block:
        try:
            return json.loads(json_block.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. 提取[...]或{...}
    for pattern in [r"\[.*\]", r"\{.*\}"]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue

    return None


def parse_structured_output(text: str, model_class: type[T]) -> T | None:
    """从LLM输出解析Pydantic模型"""
    data = extract_json_from_text(text)
    if data is None:
        return None

    try:
        if isinstance(data, list) and len(data) > 0:
            return model_class.model_validate(data[0])
        return model_class.model_validate(data)
    except ValidationError:
        return None


def parse_list_output(text: str, model_class: type[T]) -> list[T]:
    """从LLM输出解析Pydantic模型列表"""
    data = extract_json_from_text(text)
    if data is None:
        return []

    if not isinstance(data, list):
        data = [data]

    results = []
    for item in data:
        try:
            results.append(model_class.model_validate(item))
        except ValidationError:
            continue
    return results


async def parse_with_retry(
    llm_client: Any,
    messages: list[Any],
    model_class: type[T],
    max_retries: int = 3,
    **kwargs: Any,
) -> T | None:
    """带重试的结构化解析"""
    for attempt in range(max_retries):
        response = await llm_client.chat(messages, **kwargs)
        result = parse_structured_output(response.content, model_class)
        if result:
            return result

        # 重试时告诉LLM格式错误
        messages.append(type(messages[0]).assistant(response.content))
        messages.append(type(messages[0]).user(
            f"输出格式错误，请严格按照JSON格式输出。错误详情: 无法解析为 {model_class.__name__}。\n"
            f"期望的JSON结构: {model_class.model_json_schema()}"
        ))

    return None
