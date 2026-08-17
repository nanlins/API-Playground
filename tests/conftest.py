import os
import sys

import pytest

# 把项目根目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def app():
    """提供 FastAPI 测试实例"""
    from backend.main import app
    return app


@pytest.fixture
def client(app):
    """提供测试客户端"""
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def sample_messages():
    return [{"role": "user", "content": "你好，请简单介绍一下自己。"}]


@pytest.fixture
def sample_tool_messages():
    return [{"role": "user", "content": "北京现在的天气怎么样？"}]


@pytest.fixture
def sample_structured_schema():
    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],
    }


@pytest.fixture
def sample_embedding_text():
    return "机器学习是人工智能的重要分支。"
