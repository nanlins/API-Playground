# FastAPI 应用入口 - LLM API Playground
import json
import logging
import math
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from openai import APIConnectionError, APIStatusError, APITimeoutError

from backend.config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_EMBEDDING_MODEL,
    DASHSCOPE_MODELS,
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODELS,
    HOST,
    PORT,
)
from backend.database import (
    get_call_history_async,
    get_call_log_async,
    save_call_log_async,
)
from backend.models import (
    APIResponse,
    ChatCompletionRequest,
    EmbeddingCompareRequest,
    EmbeddingRequest,
    HistoryListResponse,
    HistoryResponse,
    ProviderTestRequest,
    ToolChainResponse,
)
from backend.providers import get_provider, test_provider
from backend.tools import AVAILABLE_TOOLS, execute_tool

FRONTEND_INDEX = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"LLM API Playground started. Access http://localhost:{PORT}")
    yield
    print("应用关闭")


app = FastAPI(title="LLM API Playground", version="1.1.0", lifespan=lifespan)

# CORS 配置：教学项目允许本地任意来源，但不使用 credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def error_status(exc: Exception) -> int:
    """将异常映射为 HTTP 状态码"""
    if isinstance(exc, HTTPException):
        return exc.status_code
    if isinstance(exc, ValueError):
        return 400
    if isinstance(exc, APIStatusError):
        return exc.status_code
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return 504
    return 500


def error_response(exc: Exception, elapsed_ms: float = 0.0) -> JSONResponse:
    """构造统一错误响应，保留 success/error/elapsed_ms 字段"""
    return JSONResponse(
        status_code=error_status(exc),
        content={
            "success": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_ms": elapsed_ms,
        },
    )


def extract_api_key(request) -> str | None:
    """从请求体或兼容的旧消息字段中提取 API Key"""
    if getattr(request, "api_key", None):
        return request.api_key
    for msg in request.messages:
        if isinstance(msg, dict) and msg.get("_api_key"):
            return msg["_api_key"]
    return None


def strip_secret_from_messages(messages):
    """移除消息中的 _api_key 字段，避免密钥转发给模型供应商"""
    cleaned = []
    for msg in messages:
        if isinstance(msg, dict):
            cleaned.append({key: value for key, value in msg.items() if key != "_api_key"})
        else:
            cleaned.append(msg)
    return cleaned



def missing_key_response(
    provider_name: str,
    api_key: str | None,
    provider_config=None,
) -> JSONResponse | None:
    """缺少 Key 时返回 401；未知供应商交给 get_provider 返回 400。"""
    defaults = {"deepseek": DEEPSEEK_API_KEY, "dashscope": DASHSCOPE_API_KEY}
    effective_key = api_key
    if provider_config is not None:
        effective_key = provider_config.api_key or api_key
    if provider_config is not None and not effective_key:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": "缺少 API Key，请在前端供应商配置中填写",
                "elapsed_ms": 0,
            },
        )
    if provider_name in defaults and not effective_key and not defaults[provider_name]:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "缺少 API Key，请在前端配置或在 .env 中设置", "elapsed_ms": 0},
        )
    return None


def parse_model(request_model: str):
    """解析 provider/model 前缀"""
    if "/" in request_model:
        provider_name, model = request_model.split("/", 1)
    else:
        provider_name, model = "dashscope", request_model
    return provider_name, model


# ===== 前端页面 =====


@app.get("/")
async def serve_frontend():
    """返回前端页面"""
    if FRONTEND_INDEX.exists():
        return HTMLResponse(FRONTEND_INDEX.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>LLM API Playground</h1><p>前端文件缺失</p>")


# ===== 健康检查 =====


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "LLM API Playground"}


# ===== 模型列表 =====


@app.get("/v1/models")
async def list_models():
    """返回支持的供应商和模型列表"""
    return {
        "dashscope": {
            "name": "通义千问 (Dashscope)",
            "models": DASHSCOPE_MODELS,
            "embedding_models": [DASHSCOPE_EMBEDDING_MODEL],
        },
        "deepseek": {
            "name": "DeepSeek",
            "models": DEEPSEEK_MODELS,
        },
    }


# ===== 聊天补全 =====


@app.post("/v1/chat/completions", response_model=APIResponse)
async def chat_completions(request: ChatCompletionRequest):
    """聊天补全（支持普通对话、流式、结构化输出、工具调用）"""
    provider_name, model = parse_model(request.model)
    api_key = extract_api_key(request)
    messages = strip_secret_from_messages(request.messages)
    provider_config = request.provider_config
    if provider_config is not None:
        provider_name = provider_config.name
        if provider_config.api_key:
            api_key = provider_config.api_key

    missing = missing_key_response(provider_name, api_key, provider_config)
    if missing:
        return missing

    try:
        provider = get_provider(provider_name, api_key, provider_config)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(exc), "elapsed_ms": 0},
        )

    # 流式响应
    if request.stream:
        return StreamingResponse(
            stream_chat(
                provider,
                model,
                messages,
                request.system_prompt,
                request.temperature,
                request.max_tokens,
                request.tools,
                request.tool_choice,
                request.response_format,
                provider_name,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 非流式响应
    start_time = time.time()
    try:
        result, usage = await provider.chat(
            model,
            messages,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            response_format=request.response_format,
            tools=request.tools,
            tool_choice=request.tool_choice,
        )
        elapsed = (time.time() - start_time) * 1000

        call_type = "tool_call" if result.get("tool_calls") else "structured" if request.response_format else "chat"
        await save_call_log_async(
            provider=provider_name,
            model=model,
            call_type=call_type,
            input_data={"messages": messages, "system_prompt": request.system_prompt},
            output_data=result,
            elapsed_ms=elapsed,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

        return {
            "success": True,
            "data": result,
            "usage": usage,
            "elapsed_ms": elapsed,
        }

    except Exception as exc:
        elapsed = (time.time() - start_time) * 1000
        await save_call_log_async(
            provider=provider_name,
            model=model,
            call_type="chat",
            input_data={"messages": messages},
            output_data=None,
            elapsed_ms=elapsed,
            error=f"{type(exc).__name__}: {exc}",
        )
        return error_response(exc, elapsed)


def sse_event(event: dict) -> str:
    """构造 SSE 数据帧"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def stream_chat(
    provider,
    model,
    messages,
    system_prompt,
    temperature,
    max_tokens,
    tools,
    tool_choice,
    response_format,
    provider_name,
):
    """流式聊天生成器"""
    start_time = time.time()
    full_content = ""
    tool_calls = []
    usage = {}
    try:
        async for event in provider.chat_stream(
            model,
            messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            tools=tools,
            tool_choice=tool_choice,
        ):
            if event["type"] == "content":
                full_content += event["content"]
                yield sse_event(event)
            elif event["type"] == "tool_call":
                tool_calls = event.get("tool_calls", [])
                yield sse_event(event)
            elif event["type"] == "done":
                usage = event.get("usage", {})
                yield sse_event(event)

        elapsed = (time.time() - start_time) * 1000
        await save_call_log_async(
            provider=provider_name,
            model=model,
            call_type="stream",
            input_data={"messages": messages},
            output_data={"content": full_content, "tool_calls": tool_calls},
            elapsed_ms=elapsed,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        await save_call_log_async(
            provider=provider_name,
            model=model,
            call_type="stream",
            input_data={"messages": messages},
            output_data=None,
            error=error_msg,
        )
        yield sse_event({"type": "error", "error": error_msg})
    yield "data: [DONE]\n\n"


# ===== 工具调用 =====


@app.post("/v1/tools/execute")
async def execute_tool_endpoint(request: Request):
    """执行单个工具（本地函数，无需模型）"""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "请求体不是合法 JSON", "elapsed_ms": 0},
        )
    tool_name = body.get("tool_name")
    arguments = body.get("arguments", {})
    tool_names = {tool["function"]["name"] for tool in AVAILABLE_TOOLS}
    if tool_name not in tool_names:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": f"未知工具: {tool_name}"},
        )
    result = execute_tool(tool_name, arguments)
    return {"success": True, "data": json.loads(result) if isinstance(result, str) else result}


@app.post("/v1/tool-chain", response_model=ToolChainResponse)
async def tool_chain(request: ChatCompletionRequest):
    """演示完整的工具调用链路：模型生成工具调用 → 执行 → 返回结果给模型生成最终回复"""
    provider_name, model = parse_model(request.model)
    api_key = extract_api_key(request)
    messages = strip_secret_from_messages(request.messages)
    provider_config = request.provider_config
    if provider_config is not None:
        provider_name = provider_config.name
        if provider_config.api_key:
            api_key = provider_config.api_key

    missing = missing_key_response(provider_name, api_key, provider_config)
    if missing:
        return missing

    try:
        provider = get_provider(provider_name, api_key, provider_config)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(exc), "steps": [], "elapsed_ms": 0},
        )

    # 如果没有指定 tools，使用默认工具
    tools = request.tools or AVAILABLE_TOOLS
    steps = []
    start_time = time.time()

    try:
        # 第1步：模型生成工具调用
        result, usage = await provider.chat(
            model,
            messages,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            tools=tools,
        )
        steps.append({"step": "model_tool_call", "response": result, "usage": usage})

        # 第2步：如果有工具调用，执行工具
        if result.get("tool_calls"):
            messages.append(
                {
                    "role": "assistant",
                    "content": result.get("content"),
                    "tool_calls": result["tool_calls"],
                }
            )
            for tc in result["tool_calls"]:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                try:
                    arguments = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    arguments = {}
                tool_result = execute_tool(tool_name, arguments)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": tool_result,
                    }
                )
                steps.append(
                    {
                        "step": "execute_tool",
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "result": json.loads(tool_result) if isinstance(tool_result, str) else tool_result,
                    }
                )

            # 第3步：模型根据工具结果生成最终回复
            final_result, final_usage = await provider.chat(
                model,
                messages,
                system_prompt=request.system_prompt,
                temperature=request.temperature,
            )
            steps.append({"step": "final_response", "response": final_result, "usage": final_usage})

            elapsed = (time.time() - start_time) * 1000
            total_prompt = usage.get("prompt_tokens", 0) + final_usage.get("prompt_tokens", 0)
            total_completion = usage.get("completion_tokens", 0) + final_usage.get("completion_tokens", 0)
            await save_call_log_async(
                provider=provider_name,
                model=model,
                call_type="tool_chain",
                input_data={"messages": messages, "steps": steps},
                output_data={"final_response": final_result, "steps": steps},
                elapsed_ms=elapsed,
                prompt_tokens=total_prompt,
                completion_tokens=total_completion,
                total_tokens=total_prompt + total_completion,
            )

            return {
                "success": True,
                "steps": steps,
                "final_response": final_result.get("content"),
                "usage": final_usage,
                "elapsed_ms": elapsed,
            }

        elapsed = (time.time() - start_time) * 1000
        await save_call_log_async(
            provider=provider_name,
            model=model,
            call_type="tool_chain",
            input_data={"messages": messages, "steps": steps},
            output_data={"final_response": result.get("content"), "steps": steps},
            elapsed_ms=elapsed,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )
        return {
            "success": True,
            "steps": steps,
            "final_response": result.get("content"),
            "usage": usage,
            "elapsed_ms": elapsed,
        }

    except Exception as exc:
        elapsed = (time.time() - start_time) * 1000
        await save_call_log_async(
            provider=provider_name,
            model=model,
            call_type="tool_chain",
            input_data={"messages": messages, "steps": steps},
            output_data=None,
            elapsed_ms=elapsed,
            error=f"{type(exc).__name__}: {exc}",
        )
        return error_response(exc, elapsed)


# ===== 嵌入生成 =====


@app.post("/v1/embeddings", response_model=APIResponse)
async def create_embeddings(request: EmbeddingRequest):
    """生成文本嵌入向量（固定使用 Dashscope）"""
    provider_config = request.provider_config
    if provider_config is not None:
        provider_name = provider_config.name
        model = request.model or provider_config.embedding_model
        api_key = request.api_key or provider_config.api_key
        missing_tip = "请在该供应商配置中填写 API Key"
    else:
        provider_name = "dashscope"
        model = request.model or DASHSCOPE_EMBEDDING_MODEL
        api_key = request.api_key or DASHSCOPE_API_KEY
        missing_tip = "Embedding 使用 Dashscope，请提供 Dashscope API Key"
    if not api_key:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": missing_tip,
                "elapsed_ms": 0,
            },
        )

    try:
        provider = get_provider(provider_name, api_key, provider_config)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(exc), "elapsed_ms": 0},
        )

    start_time = time.time()
    try:
        embedding, usage = await provider.embeddings(model, request.input)
        elapsed = (time.time() - start_time) * 1000
        await save_call_log_async(
            provider=provider_name,
            model=model,
            call_type="embedding",
            input_data={"input": request.input},
            output_data={"vector_preview": embedding[:5], "dimensions": len(embedding)},
            elapsed_ms=elapsed,
            prompt_tokens=usage.get("prompt_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )
        return {
            "success": True,
            "data": {"vector": embedding, "dimensions": len(embedding), "model": model},
            "usage": usage,
            "elapsed_ms": elapsed,
        }

    except Exception as exc:
        elapsed = (time.time() - start_time) * 1000
        logger.exception("Embedding 生成失败: %s", exc)
        await save_call_log_async(
            provider=provider_name,
            model=model,
            call_type="embedding",
            input_data={"input": request.input},
            output_data=None,
            elapsed_ms=elapsed,
            error=f"{type(exc).__name__}: {exc}",
        )
        return error_response(exc, elapsed)


@app.post("/v1/embeddings/compare", response_model=APIResponse)
async def compare_embeddings(request: EmbeddingCompareRequest):
    """比较两段文本的语义相似度（余弦相似度）"""
    provider_config = request.provider_config
    if provider_config is not None:
        provider_name = provider_config.name
        model = request.model or provider_config.embedding_model
        api_key = request.api_key or provider_config.api_key
        missing_tip = "请在该供应商配置中填写 API Key"
    else:
        provider_name = "dashscope"
        model = request.model or DASHSCOPE_EMBEDDING_MODEL
        api_key = request.api_key or DASHSCOPE_API_KEY
        missing_tip = "Embedding 使用 Dashscope，请提供 Dashscope API Key"
    if not api_key:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": missing_tip,
                "elapsed_ms": 0,
            },
        )

    try:
        provider = get_provider(provider_name, api_key, provider_config)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(exc), "elapsed_ms": 0},
        )

    start_time = time.time()
    try:
        emb1, usage1 = await provider.embeddings(model, request.text1)
        emb2, usage2 = await provider.embeddings(model, request.text2)
        elapsed = (time.time() - start_time) * 1000

        # 计算余弦相似度
        dot_product = sum(a * b for a, b in zip(emb1, emb2, strict=True))
        norm1 = math.sqrt(sum(a * a for a in emb1))
        norm2 = math.sqrt(sum(b * b for b in emb2))
        cosine_sim = dot_product / (norm1 * norm2) if norm1 and norm2 else 0

        combined_usage = {
            "prompt_tokens": usage1.get("prompt_tokens", 0) + usage2.get("prompt_tokens", 0),
            "completion_tokens": 0,
            "total_tokens": usage1.get("total_tokens", 0) + usage2.get("total_tokens", 0),
            "available": True,
        }
        await save_call_log_async(
            provider=provider_name,
            model=model,
            call_type="embedding_compare",
            input_data={"text1": request.text1, "text2": request.text2},
            output_data={"cosine_similarity": round(cosine_sim, 6)},
            elapsed_ms=elapsed,
            prompt_tokens=combined_usage["prompt_tokens"],
            total_tokens=combined_usage["total_tokens"],
        )
        return {
            "success": True,
            "data": {
                "text1": request.text1,
                "text2": request.text2,
                "cosine_similarity": round(cosine_sim, 6),
            },
            "usage": combined_usage,
            "elapsed_ms": elapsed,
        }

    except Exception as exc:
        elapsed = (time.time() - start_time) * 1000
        logger.exception("Embedding 相似度计算失败: %s", exc)
        await save_call_log_async(
            provider=provider_name,
            model=model,
            call_type="embedding_compare",
            input_data={"text1": request.text1, "text2": request.text2},
            output_data=None,
            elapsed_ms=elapsed,
            error=f"{type(exc).__name__}: {exc}",
        )
        return error_response(exc, elapsed)


# ===== 供应商连接测试 =====


@app.post("/v1/providers/test")
async def test_provider_connection(request: ProviderTestRequest):
    """测试自定义供应商的 chat / embedding 连通性"""
    start_time = time.time()
    try:
        data = await test_provider(
            request.provider_config,
            test_type=request.test_type,
            sample_message=request.sample_message,
        )
        elapsed = (time.time() - start_time) * 1000
        return {"success": True, "data": data, "elapsed_ms": round(elapsed, 2)}
    except Exception as exc:
        elapsed = (time.time() - start_time) * 1000
        return error_response(exc, elapsed)


# ===== 调用历史 =====


@app.get("/v1/history", response_model=HistoryListResponse)
async def get_history(limit: int = 50):
    """获取 API 调用历史"""
    try:
        history = await get_call_history_async(limit)
        return {"success": True, "data": history, "count": len(history)}
    except Exception as exc:
        return error_response(exc)


@app.get("/v1/history/{log_id}", response_model=HistoryResponse)
async def get_history_detail(log_id: int):
    """获取单条 API 调用历史"""
    try:
        item = await get_call_log_async(log_id)
        if item is None:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": f"记录不存在: {log_id}"},
            )
        return {"success": True, "data": item}
    except Exception as exc:
        return error_response(exc)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
