# LLM 供应商抽象层 - OpenAI 兼容 (DeepSeek / Dashscope / 自定义网关)
import json
import time
from abc import ABC, abstractmethod
from typing import Any

from openai import AsyncOpenAI

from backend.config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
)


def schema_to_prompt(schema):
    """PromptAdapter：将 JSON Schema 转为自然语言输出约束"""
    return "Output valid JSON following schema: " + json.dumps(schema, ensure_ascii=False)


class BaseProvider(ABC):
    """供应商基类"""

    @abstractmethod
    async def chat(
        self,
        model,
        messages,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        response_format=None,
        tools=None,
        tool_choice=None,
    ):
        """普通对话调用"""

    @abstractmethod
    async def chat_stream(
        self,
        model,
        messages,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        response_format=None,
        tools=None,
        tool_choice=None,
    ):
        """流式对话调用"""

    @abstractmethod
    async def embeddings(self, model, text):
        """生成嵌入向量"""


class OpenAIProvider(BaseProvider):
    """OpenAI 兼容供应商基类"""

    def __init__(self, api_key=None, base_url=None):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=60.0, max_retries=1)

    @staticmethod
    def _build_messages(system_prompt, messages):
        if system_prompt:
            return [{"role": "system", "content": system_prompt}] + list(messages)
        return list(messages)

    @staticmethod
    def _normalize_usage(usage):
        if usage is None:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "available": False}
        return {
            "prompt_tokens": usage.prompt_tokens or 0,
            "completion_tokens": usage.completion_tokens or 0,
            "total_tokens": usage.total_tokens or 0,
            "available": True,
        }

    async def chat(
        self,
        model,
        messages,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        response_format=None,
        tools=None,
        tool_choice=None,
    ):
        """普通对话调用"""
        kwargs = {"model": model, "messages": self._build_messages(system_prompt, messages)}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if response_format:
            kwargs["response_format"] = response_format
        if tools:
            kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        result = {"role": "assistant", "content": choice.message.content}
        if choice.message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in choice.message.tool_calls
            ]

        return result, self._normalize_usage(response.usage)

    async def chat_stream(
        self,
        model,
        messages,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        response_format=None,
        tools=None,
        tool_choice=None,
    ):
        """流式对话调用（聚合 tool_calls 增量，并请求 usage）"""
        kwargs = {
            "model": model,
            "messages": self._build_messages(system_prompt, messages),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if response_format:
            kwargs["response_format"] = response_format
        if tools:
            kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice

        stream = await self.client.chat.completions.create(**kwargs)
        full_content = ""
        tool_calls_agg: dict[int, dict[str, Any]] = {}
        usage = None

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                full_content += delta.content
                yield {"type": "content", "content": delta.content}
            if delta and delta.tool_calls:
                for tc in delta.tool_calls:
                    index = tc.index if tc.index is not None else len(tool_calls_agg)
                    entry = tool_calls_agg.setdefault(
                        index,
                        {"id": tc.id or "", "type": tc.type or "function", "function": {"name": "", "arguments": ""}},
                    )
                    if tc.id:
                        entry["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            entry["function"]["name"] = tc.function.name
                        if tc.function.arguments:
                            entry["function"]["arguments"] += tc.function.arguments
            if chunk.usage:
                usage = chunk.usage

        if tool_calls_agg:
            yield {
                "type": "tool_call",
                "tool_calls": [tool_calls_agg[index] for index in sorted(tool_calls_agg)],
            }
        yield {"type": "done", "usage": self._normalize_usage(usage)}

    async def embeddings(self, model, text):
        response = await self.client.embeddings.create(model=model, input=text)
        embedding = response.data[0].embedding
        usage = response.usage
        return embedding, {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
            "available": True,
        }


def _convert_response_format(response_format, system_prompt):
    """DeepSeek 风格：把 response_format 转为 system prompt"""
    schema = response_format.get("json_schema", {}).get("schema", {})
    if schema:
        instruction = schema_to_prompt(schema)
        system_prompt = (system_prompt + "\n\n" + instruction) if system_prompt else instruction
    return system_prompt


class OpenAICompatProvider(OpenAIProvider):
    """OpenAI 兼容供应商，支持按 native_json_mode 切换 JSON 输出方式"""

    def __init__(self, api_key=None, base_url=None, native_json_mode=True):
        super().__init__(api_key=api_key, base_url=base_url)
        self.native_json_mode = native_json_mode

    async def chat(
        self,
        model,
        messages,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        response_format=None,
        tools=None,
        tool_choice=None,
    ):
        if response_format and not getattr(self, "native_json_mode", True):
            system_prompt = _convert_response_format(response_format, system_prompt)
            response_format = None
        return await super().chat(
            model, messages, system_prompt, temperature, max_tokens, response_format, tools, tool_choice
        )

    async def chat_stream(
        self,
        model,
        messages,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        response_format=None,
        tools=None,
        tool_choice=None,
    ):
        if response_format and not getattr(self, "native_json_mode", True):
            system_prompt = _convert_response_format(response_format, system_prompt)
            response_format = None
        async for event in super().chat_stream(
            model, messages, system_prompt, temperature, max_tokens, response_format, tools, tool_choice
        ):
            yield event


class DashscopeProvider(OpenAIProvider):
    """Dashscope/Qwen provider (OpenAI-compatible)"""

    def __init__(self, api_key=None):
        super().__init__(api_key=api_key or DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)


class DeepSeekProvider(OpenAICompatProvider):
    """DeepSeek provider (OpenAI-compatible, 非原生 JSON 模式)"""

    def __init__(self, api_key=None, base_url=None):
        super().__init__(
            api_key=api_key or DEEPSEEK_API_KEY,
            base_url=base_url or DEEPSEEK_BASE_URL,
            native_json_mode=False,
        )


def get_provider(provider_name, api_key=None, provider_config=None):
    """工厂方法：有 provider_config 时创建动态 OpenAI 兼容客户端"""
    if provider_config:
        return OpenAICompatProvider(
            api_key=provider_config.api_key or api_key,
            base_url=provider_config.base_url,
            native_json_mode=provider_config.native_json_mode,
        )
    if provider_name == "deepseek":
        return DeepSeekProvider(api_key)
    if provider_name == "dashscope":
        return DashscopeProvider(api_key)
    raise ValueError(f"不支持的供应商: {provider_name}")


async def test_provider(config, test_type="chat", sample_message="ping"):
    """测试供应商连接：chat 或 embedding，返回耗时与模型信息"""
    provider = get_provider(config.name, api_key=config.api_key, provider_config=config)
    start = time.time()
    if test_type == "chat":
        if not config.chat_model:
            raise ValueError("该供应商未配置聊天模型")
        result, _usage = await provider.chat(
            config.chat_model,
            [{"role": "user", "content": sample_message}],
            max_tokens=16,
        )
        return {
            "ok": True,
            "provider": config.name,
            "model": config.chat_model,
            "reply": (result.get("content") or "")[:200],
            "elapsed_ms": round((time.time() - start) * 1000, 2),
        }
    if test_type == "embedding":
        if not config.embedding_model:
            raise ValueError("该供应商未配置 Embedding 模型")
        embedding, _usage = await provider.embeddings(config.embedding_model, sample_message)
        return {
            "ok": True,
            "provider": config.name,
            "model": config.embedding_model,
            "dimensions": len(embedding),
            "elapsed_ms": round((time.time() - start) * 1000, 2),
        }
    raise ValueError(f"不支持的测试类型: {test_type}")
