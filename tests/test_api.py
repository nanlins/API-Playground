from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import APIStatusError


class AsyncIter:
    """Wrap a list into an async iterator."""

    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        async def gen():
            for item in self.items:
                yield item

        return gen()


def make_provider():
    provider = MagicMock()
    provider.chat = AsyncMock(
        return_value=(
            {"role": "assistant", "content": "你好"},
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "available": True},
        )
    )
    provider.chat_stream = MagicMock(
        return_value=AsyncIter(
            [
                {"type": "content", "content": "你好"},
                {
                    "type": "done",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "available": True},
                },
            ]
        )
    )
    provider.embeddings = AsyncMock(
        return_value=([1.0, 0.0], {"prompt_tokens": 2, "total_tokens": 2, "available": True})
    )
    return provider


@pytest.fixture
def mock_llm():
    with (
        patch("backend.main.get_provider") as get_provider,
        patch("backend.main.save_call_log_async", new_callable=AsyncMock) as save_log,
    ):
        provider = make_provider()
        get_provider.return_value = provider
        yield get_provider, provider, save_log


class TestHealthAndModels:
    async def test_health_check(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_list_models(self, client):
        resp = await client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "deepseek" in data
        assert "dashscope" in data
        assert "text-embedding-v2" in data["dashscope"]["embedding_models"]


class TestChatEndpoint:
    async def test_chat_sends_api_key_to_provider(self, client, mock_llm):
        get_provider, provider, save_log = mock_llm
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek/deepseek-v4-flash",
                "messages": [{"role": "user", "content": "hi"}],
                "api_key": "sk-test",
                "stream": False,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        get_provider.assert_called_once_with("deepseek", "sk-test", None)
        save_log.assert_awaited_once()

    async def test_legacy_api_key_is_stripped_from_messages(self, client, mock_llm):
        get_provider, provider, _ = mock_llm
        captured = {}

        async def fake_chat(model, messages, **kwargs):
            captured["messages"] = messages
            return (
                {"role": "assistant", "content": "ok"},
                {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2, "available": True},
            )

        provider.chat = AsyncMock(side_effect=fake_chat)
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek/deepseek-v4-flash",
                "messages": [{"role": "user", "content": "hi", "_api_key": "sk-legacy"}],
                "stream": False,
            },
        )
        assert resp.status_code == 200
        get_provider.assert_called_once_with("deepseek", "sk-legacy", None)
        assert all("_api_key" not in msg for msg in captured["messages"])

    async def test_unsupported_provider_returns_400(self, client, mock_llm):
        get_provider, _, _ = mock_llm
        get_provider.side_effect = ValueError("不支持的供应商: xxx")
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "xxx/model",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    async def test_auth_error_returns_401(self, client, mock_llm):
        _, provider, _ = mock_llm
        provider.chat.side_effect = APIStatusError(
            "unauthorized",
            response=httpx.Response(401, request=httpx.Request("POST", "http://test")),
            body=None,
        )
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek/deepseek-v4-flash",
                "messages": [{"role": "user", "content": "hi"}],
                "api_key": "sk-test",
                "stream": False,
            },
        )
        assert resp.status_code == 401
        assert resp.json()["success"] is False

    async def test_internal_error_returns_500(self, client, mock_llm):
        _, provider, _ = mock_llm
        provider.chat.side_effect = RuntimeError("boom")
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek/deepseek-v4-flash",
                "messages": [{"role": "user", "content": "hi"}],
                "api_key": "sk-test",
                "stream": False,
            },
        )
        assert resp.status_code == 500
        assert "boom" in resp.json()["error"]

    async def test_chat_without_key_returns_401(self, client):
        with patch("backend.main.DEEPSEEK_API_KEY", ""):
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "deepseek/deepseek-v4-flash",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )
        assert resp.status_code == 401
        assert resp.json()["success"] is False

    async def test_dashscope_chat_without_key_returns_401(self, client):
        with patch("backend.main.DASHSCOPE_API_KEY", ""):
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "dashscope/qwen-plus",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )
        assert resp.status_code == 401
        assert resp.json()["success"] is False

    async def test_stream_passes_events_and_usage(self, client, mock_llm):
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek/deepseek-v4-flash",
                "messages": [{"role": "user", "content": "hi"}],
                "api_key": "sk-test",
                "stream": True,
            },
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        assert "你好" in resp.text
        assert "total_tokens" in resp.text


class TestToolChainEndpoint:
    async def test_tool_chain_executes_local_tool(self, client, mock_llm):
        get_provider, provider, _ = mock_llm
        provider.chat.side_effect = [
            (
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "calculator",
                                "arguments": '{"operation": "add", "a": 1, "b": 2}',
                            },
                        }
                    ],
                },
                {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "available": True},
            ),
            (
                {"role": "assistant", "content": "结果是 3"},
                {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25, "available": True},
            ),
        ]
        resp = await client.post(
            "/v1/tool-chain",
            json={
                "model": "deepseek/deepseek-v4-flash",
                "messages": [{"role": "user", "content": "帮我算 1 加 2"}],
                "api_key": "sk-test",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["final_response"] == "结果是 3"
        execute_steps = [step for step in data["steps"] if step["step"] == "execute_tool"]
        assert execute_steps[0]["tool_name"] == "calculator"
        get_provider.assert_called_once_with("deepseek", "sk-test", None)

    async def test_unknown_tool_returns_404(self, client):
        resp = await client.post(
            "/v1/tools/execute",
            json={"tool_name": "no_such_tool", "arguments": {}},
        )
        assert resp.status_code == 404


    async def test_malformed_json_returns_400(self, client):
        resp = await client.post(
            "/v1/tools/execute",
            content="{bad json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    async def test_tool_chain_without_key_returns_401(self, client):
        with patch("backend.main.DEEPSEEK_API_KEY", ""):
            resp = await client.post(
                "/v1/tool-chain",
                json={
                    "model": "deepseek/deepseek-v4-flash",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
        assert resp.status_code == 401
        assert resp.json()["success"] is False


class TestEmbeddingEndpoint:
    async def test_compare_embeddings_success(self, client, mock_llm):
        _, provider, _ = mock_llm
        provider.embeddings.side_effect = [
            ([1.0, 0.0], {"prompt_tokens": 1, "total_tokens": 1, "available": True}),
            ([1.0, 0.0], {"prompt_tokens": 1, "total_tokens": 1, "available": True}),
        ]
        resp = await client.post(
            "/v1/embeddings/compare",
            json={"model": "", "text1": "a", "text2": "a", "api_key": "sk-dash"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["cosine_similarity"] == 1.0

    async def test_compare_embeddings_requires_dashscope_key(self, client):
        with patch("backend.main.DASHSCOPE_API_KEY", None):
            resp = await client.post(
                "/v1/embeddings/compare",
                json={"model": "", "text1": "a", "text2": "b"},
            )
        assert resp.status_code == 401
        assert "Dashscope" in resp.json()["error"]


class TestHistoryEndpoint:
    async def test_history_list(self, client):
        with patch(
            "backend.main.get_call_history_async",
            new_callable=AsyncMock,
            return_value=[{"id": 1, "model": "deepseek-v4-flash", "call_type": "chat"}],
        ):
            resp = await client.get("/v1/history")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    async def test_history_detail(self, client):
        item = {"id": 42, "provider": "deepseek", "model": "deepseek-v4-flash", "call_type": "chat"}
        with patch("backend.main.get_call_log_async", new_callable=AsyncMock, return_value=item):
            resp = await client.get("/v1/history/42")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 42


class TestProviderConfig:
    async def test_custom_provider_config_used_for_chat(self, client, mock_llm):
        get_provider, _, _ = mock_llm
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "kimi/kimi-latest",
                "messages": [{"role": "user", "content": "hi"}],
                "provider_config": {
                    "name": "kimi",
                    "display_name": "Kimi",
                    "base_url": "https://api.moonshot.cn/v1",
                    "api_key": "sk-custom",
                    "chat_model": "kimi-latest",
                    "native_json_mode": False,
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        args = get_provider.call_args
        assert args.args[0] == "kimi"
        assert args.args[1] == "sk-custom"
        assert args.args[2].name == "kimi"
        assert args.args[2].base_url == "https://api.moonshot.cn/v1"
        assert args.args[2].native_json_mode is False

    async def test_custom_provider_missing_key_returns_401(self, client):
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "kimi/kimi-latest",
                "messages": [{"role": "user", "content": "hi"}],
                "provider_config": {
                    "name": "kimi",
                    "base_url": "https://api.moonshot.cn/v1",
                },
            },
        )
        assert resp.status_code == 401
        assert resp.json()["success"] is False

    async def test_embedding_uses_custom_provider_config(self, client, mock_llm):
        get_provider, _, _ = mock_llm
        resp = await client.post(
            "/v1/embeddings",
            json={
                "input": "hello",
                "provider_config": {
                    "name": "zhipu",
                    "base_url": "https://open.bigmodel.cn/api/paas/v4",
                    "api_key": "sk-zhipu",
                    "embedding_model": "embedding-2",
                    "supports_embedding": True,
                },
            },
        )
        assert resp.status_code == 200
        args = get_provider.call_args
        assert args.args[0] == "zhipu"
        assert args.args[1] == "sk-zhipu"
        assert args.args[2].embedding_model == "embedding-2"

    async def test_history_input_never_contains_api_key(self, client, mock_llm):
        _, _, save_log = mock_llm
        resp = await client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek/deepseek-v4-flash",
                "messages": [{"role": "user", "content": "hi"}],
                "provider_config": {
                    "name": "deepseek",
                    "base_url": "https://example.com/v1",
                    "api_key": "sk-topsecret",
                    "chat_model": "deepseek-v4-flash",
                },
            },
        )
        assert resp.status_code == 200
        input_data = save_log.await_args.kwargs.get("input_data") or {}
        assert "sk-topsecret" not in str(input_data)


class TestProviderTestEndpoint:
    async def test_provider_test_chat_success(self, client):
        with patch(
            "backend.main.test_provider",
            new_callable=AsyncMock,
            return_value={
                "ok": True,
                "provider": "kimi",
                "model": "kimi-latest",
                "reply": "pong",
                "elapsed_ms": 12.0,
            },
        ):
            resp = await client.post(
                "/v1/providers/test",
                json={
                    "test_type": "chat",
                    "provider_config": {
                        "name": "kimi",
                        "base_url": "https://api.moonshot.cn/v1",
                        "api_key": "sk-test",
                        "chat_model": "kimi-latest",
                    },
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["model"] == "kimi-latest"

    async def test_provider_test_embedding_success(self, client):
        with patch(
            "backend.main.test_provider",
            new_callable=AsyncMock,
            return_value={
                "ok": True,
                "provider": "zhipu",
                "model": "embedding-2",
                "dimensions": 1024,
                "elapsed_ms": 20.0,
            },
        ):
            resp = await client.post(
                "/v1/providers/test",
                json={
                    "test_type": "embedding",
                    "provider_config": {
                        "name": "zhipu",
                        "base_url": "https://open.bigmodel.cn/api/paas/v4",
                        "api_key": "sk-test",
                        "embedding_model": "embedding-2",
                        "supports_embedding": True,
                    },
                },
            )
        assert resp.status_code == 200
        assert resp.json()["data"]["dimensions"] == 1024

    async def test_provider_test_bad_key_returns_401(self, client):
        exc = APIStatusError(
            "bad key",
            response=httpx.Response(401, request=httpx.Request("POST", "http://test")),
            body=None,
        )
        with patch("backend.main.test_provider", new_callable=AsyncMock, side_effect=exc):
            resp = await client.post(
                "/v1/providers/test",
                json={
                    "test_type": "chat",
                    "provider_config": {
                        "name": "kimi",
                        "base_url": "https://api.moonshot.cn/v1",
                        "api_key": "bad",
                        "chat_model": "kimi-latest",
                    },
                },
            )
        assert resp.status_code == 401
        assert resp.json()["success"] is False


class TestFrontendEndpoint:
    async def test_frontend_served(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "dashscopeKeyInput" in resp.text
