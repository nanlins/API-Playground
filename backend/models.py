# Pydantic 请求/响应模型定义
from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    """对话消息"""

    role: str = Field(description="角色: system / user / assistant / tool")
    content: str | None = Field(None, description="消息内容")
    tool_calls: list[dict[str, Any]] | None = Field(None, description="工具调用列表")
    tool_call_id: str | None = Field(None, description="工具调用 ID")
    name: str | None = Field(None, description="工具名称")


class ProviderConfig(BaseModel):
    """网页端自定义 OpenAI 兼容供应商配置"""

    name: str = Field(description="唯一标识，如 kimi、zhipu、my-gateway")
    display_name: str = Field("", description="前端显示名")
    base_url: str = Field(description="OpenAI 兼容 Base URL")
    api_key: str = Field("", description="请求级 Key，日志必须脱敏")
    chat_model: str = Field("", description="聊天模型")
    embedding_model: str = Field("", description="Embedding 模型，留空表示不支持")
    embedding_dimensions: int | None = Field(None, description="可选，用于维度校验")
    supports_chat: bool = Field(True, description="是否支持聊天")
    supports_embedding: bool = Field(False, description="是否支持 Embedding")
    anthropic_style: bool = Field(False, description="是否走 Anthropic 原生协议")
    native_json_mode: bool = Field(True, description="是否原生支持 response_format")


class ChatCompletionRequest(BaseModel):
    """聊天补全请求"""

    model: str = Field(description="模型名称")
    messages: list[dict[str, Any]] = Field(description="消息列表")
    api_key: str | None = Field(None, description="API Key（可选，优先于环境变量）")
    system_prompt: str | None = Field(None, description="系统提示词")
    stream: bool = Field(False, description="是否流式响应")
    temperature: float | None = Field(None, description="采样温度", ge=0, le=2)
    max_tokens: int | None = Field(None, description="最大输出 Token 数")
    response_format: dict[str, Any] | None = Field(None, description="结构化输出格式")
    tools: list[dict[str, Any]] | None = Field(None, description="可用工具列表")
    tool_choice: str | None = Field(None, description="工具选择策略")
    provider_config: ProviderConfig | None = Field(None, description="网页自定义供应商配置")


class EmbeddingRequest(BaseModel):
    """嵌入生成请求"""

    model: str = Field("", description="嵌入模型名称，留空使用默认模型")
    input: str = Field(description="输入文本")
    api_key: str | None = Field(None, description="API Key（可选）")
    provider_config: ProviderConfig | None = Field(None, description="网页自定义供应商配置")


class EmbeddingCompareRequest(BaseModel):
    """嵌入相似度比较请求"""

    model: str = Field("", description="嵌入模型名称，留空使用默认模型")
    text1: str = Field(description="文本 A")
    text2: str = Field(description="文本 B")
    api_key: str | None = Field(None, description="API Key（可选）")
    provider_config: ProviderConfig | None = Field(None, description="网页自定义供应商配置")


class ProviderTestRequest(BaseModel):
    """供应商连接测试请求"""

    provider_config: ProviderConfig = Field(description="待测试的供应商配置")
    test_type: str = Field("chat", description="chat / embedding")
    sample_message: str = Field("ping", description="chat 测试消息")


class TokenUsage(BaseModel):
    """Token 用量"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    available: bool = True


class APIResponse(BaseModel):
    """统一 API 响应"""

    success: bool = True
    data: Any = None
    error: str | None = None
    usage: TokenUsage | None = None
    elapsed_ms: float = 0.0


class ToolChainResponse(BaseModel):
    """工具调用链路响应"""

    success: bool = True
    steps: list[Any] = Field(default_factory=list)
    final_response: str | None = None
    usage: TokenUsage | None = None
    elapsed_ms: float = 0.0
    error: str | None = None


class HistoryListResponse(BaseModel):
    """历史记录列表响应"""

    success: bool = True
    data: list[Any] = Field(default_factory=list)
    count: int = 0
    error: str | None = None


class HistoryResponse(BaseModel):
    """历史记录详情响应"""

    success: bool = True
    data: Any | None = None
    error: str | None = None
