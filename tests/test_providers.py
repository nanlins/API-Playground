from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from backend import providers
from backend.database import redact_secrets
from backend.models import ProviderConfig
from backend.providers import DeepSeekProvider, OpenAIProvider, get_provider


class AsyncIter:
    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        async def gen():
            for item in self.items:
                yield item

        return gen()


def chunk(index=0, content=None, tool_calls=None, usage=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content, tool_calls=tool_calls))],
        usage=usage,
    )


def tool_delta(index, id=None, name=None, arguments=None):
    return SimpleNamespace(
        index=index,
        id=id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


async def test_stream_tool_call_fragments_are_aggregated():
    provider = OpenAIProvider.__new__(OpenAIProvider)
    client = MagicMock()
    create = AsyncMock(
        return_value=AsyncIter(
            [
                chunk(0, tool_calls=[tool_delta(0, "call_1", "calculator", '{"operation":"add",')]),
                chunk(0, tool_calls=[tool_delta(0, None, None, '"a":1,"b":2}')]),
                SimpleNamespace(
                    choices=[],
                    usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                ),
            ]
        )
    )
    client.chat.completions.create = create
    provider.client = client

    events = []
    async for event in provider.chat_stream("m", [{"role": "user", "content": "hi"}]):
        events.append(event)

    tool_event = next(event for event in events if event["type"] == "tool_call")
    assert tool_event["tool_calls"][0]["id"] == "call_1"
    assert tool_event["tool_calls"][0]["function"]["name"] == "calculator"
    assert tool_event["tool_calls"][0]["function"]["arguments"] == '{"operation":"add","a":1,"b":2}'
    done = next(event for event in events if event["type"] == "done")
    assert done["usage"]["available"] is True
    assert done["usage"]["total_tokens"] == 15


async def test_stream_usage_is_marked_unavailable_when_missing():
    provider = OpenAIProvider.__new__(OpenAIProvider)
    client = MagicMock()
    create = AsyncMock(
        return_value=AsyncIter(
            [
                chunk(0, content="ok"),
                SimpleNamespace(choices=[], usage=None),
            ]
        )
    )
    client.chat.completions.create = create
    provider.client = client

    events = []
    async for event in provider.chat_stream("m", [{"role": "user", "content": "hi"}]):
        events.append(event)

    done = next(event for event in events if event["type"] == "done")
    assert done["usage"]["available"] is False
    assert done["usage"]["total_tokens"] == 0


async def test_deepseek_stream_converts_response_format_to_prompt():
    provider = DeepSeekProvider(api_key="sk-test")
    client = MagicMock()
    create = AsyncMock(
        return_value=AsyncIter(
            [
                chunk(0, content="{}"),
                SimpleNamespace(
                    choices=[],
                    usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
                ),
            ]
        )
    )
    client.chat.completions.create = create
    provider.client = client

    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    events = []
    async for event in provider.chat_stream(
        "deepseek-v4-flash",
        [{"role": "user", "content": "x"}],
        response_format={"type": "json_schema", "json_schema": {"name": "x", "schema": schema}},
    ):
        events.append(event)

    kwargs = create.call_args.kwargs
    assert "response_format" not in kwargs
    assert kwargs["stream_options"] == {"include_usage": True}
    assert "Output valid JSON following schema" in kwargs["messages"][0]["content"]
    assert any(event["type"] == "done" for event in events)


def test_get_provider_uses_provider_config(monkeypatch):
    captured = {}

    def fake_init(self, api_key=None, base_url=None, **kwargs):
        captured["api_key"] = api_key
        captured["base_url"] = base_url

    monkeypatch.setattr("backend.providers.AsyncOpenAI.__init__", fake_init)
    config = ProviderConfig(
        name="kimi",
        base_url="https://api.moonshot.cn/v1",
        api_key="sk-xyz",
        chat_model="kimi-latest",
    )
    provider = get_provider("kimi", None, config)
    assert provider is not None
    assert captured["api_key"] == "sk-xyz"
    assert captured["base_url"] == "https://api.moonshot.cn/v1"


def test_redact_secrets_recursively():
    data = {
        "messages": [{"content": "hi", "_api_key": "sk-1"}],
        "provider_config": {"api_key": "sk-2", "base_url": "https://x"},
    }
    cleaned = redact_secrets(data)
    assert cleaned["messages"][0]["_api_key"] == "***"
    assert cleaned["provider_config"]["api_key"] == "***"
    assert cleaned["provider_config"]["base_url"] == "https://x"


async def test_test_provider_chat_uses_config():
    config = ProviderConfig(
        name="kimi",
        base_url="https://api.moonshot.cn/v1",
        api_key="sk-xyz",
        chat_model="kimi-latest",
    )
    provider = MagicMock()
    provider.chat = AsyncMock(return_value=({"role": "assistant", "content": "pong"}, {}))
    with patch("backend.providers.get_provider", return_value=provider) as gp:
        data = await providers.test_provider(config, test_type="chat", sample_message="ping")
    assert data["ok"] is True
    assert data["model"] == "kimi-latest"
    gp.assert_called_once_with("kimi", api_key="sk-xyz", provider_config=config)


async def test_test_provider_embedding_returns_dimensions():
    config = ProviderConfig(
        name="zhipu",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        api_key="sk-xyz",
        embedding_model="embedding-2",
        supports_embedding=True,
    )
    provider = MagicMock()
    provider.embeddings = AsyncMock(return_value=([0.1, 0.2, 0.3], {"prompt_tokens": 2, "total_tokens": 2}))
    with patch("backend.providers.get_provider", return_value=provider):
        data = await providers.test_provider(config, test_type="embedding", sample_message="ping")
    assert data["ok"] is True
    assert data["dimensions"] == 3
