"""S6 回归用例：模型输出的脏格式，抽取器必须扛得住。

这些 case 全部来自真实踩坑（围栏、前后缀、嵌套花括号），
以后有人"优化"extract_json 时必须先过这里。
"""

import json

import pytest
from pydantic import BaseModel

from agent_lab.app.services.structured import extract_json


class _Demo(BaseModel):
    name: str
    count: int


def test_plain_json():
    assert extract_json('{"name": "a", "count": 1}') == {"name": "a", "count": 1}


def test_markdown_fence():
    text = '```json\n{"name": "a", "count": 2}\n```'
    assert extract_json(text)["count"] == 2


def test_fence_without_language():
    assert extract_json('```\n{"name": "b", "count": 3}\n```')["name"] == "b"


def test_prefix_suffix_noise():
    text = '好的，结果如下：\n{"name": "c", "count": 4}\n还需要我做什么吗？'
    assert extract_json(text)["count"] == 4


def test_nested_braces_in_string():
    text = '{"name": "带 } 的值", "count": 5}'
    assert extract_json(text)["name"] == "带 } 的值"


def test_array_root():
    assert extract_json("[1, 2, 3]") == [1, 2, 3]


def test_invalid_raises():
    with pytest.raises(json.JSONDecodeError):
        extract_json("模型这次完全没给 JSON")


def test_schema_validation_catches_wrong_type():
    """抽取成功不代表合格 —— 类型错了必须被 Pydantic 拦住。"""
    from pydantic import ValidationError

    data = extract_json('{"name": "a", "count": "不是数字"}')
    with pytest.raises(ValidationError):
        _Demo.model_validate(data)
