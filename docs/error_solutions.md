# 错误记录与解决方案

## 关键词索引

| 关键词 | 问题编号 |
|---|---|
| embedding, api key, 401, authentication | E001 |
| structured output, response_format, DeepSeek, 400 | E002 |
| embedding not supported, provider limit | E003 |
| default provider, model prefix, wrong provider | E004 |
| embedding, 400, bad request, dashscope | E005 |
| timeout, APITimeoutError, tool chain | E006 |
| stream, tool call, fragment, aggregation | E007 |

## E001: 嵌入用户提交的 API Key 无效（401）

- 错误信息：`AuthenticationError: Error code: 401 - You didn't provide an API key`
- 原因：嵌入功能固定使用 Dashscope，但前端未把 Dashscope Key 传给后端；后端只能用环境变量中的默认值。
- 解决：后端确认 `provider_name = "dashscope"`；嵌入请求支持 `api_key` 字段；前端将页面顶部的 Dashscope Key 传入嵌入接口。

## E002: DeepSeek 不支持 `response_format`（400）

- 错误信息：`BadRequestError: Error code: 400 - This response_format type is unavailable now`
- 原因：DeepSeek API 不支持 OpenAI 的 `response_format` 参数。
- 解决：`DeepSeekProvider` 覆盖 `chat/chat_stream`，将 JSON Schema 转为 System Prompt 指令，提交给模型时不再包含 `response_format`。

## E003: 供应商不支持嵌入

- 原因：DeepSeek 没有嵌入接口；项目只保留 DeepSeek 和通义千问两种供应商。
- 解决：嵌入固定使用 Dashscope `text-embedding-v2`，避免供应商选择不支持嵌入时出错。

## E004: 默认供应商不匹配

- 错误表现：结构化输出或嵌入返回 401/400，因为前端默认指向不支持的供应商。
- 解决：前端默认 DeepSeek；嵌入端点固定 Dashscope；`/v1/models` 与后端供应商实现保持一致。

## E005: 计算相似度时返回 400 Bad Request

- 错误表现：嵌入模块计算相似度时提示 400。
- 原因：以前代码仍指向已删除的 OpenAI 供应商，或传递了错误的嵌入模型。
- 解决：嵌入端点固定 `provider_name = "dashscope"`，默认模型为 `text-embedding-v2`，后端优先使用请求中的 Dashscope Key。

## E006: 调用工具链路时超时

- 错误信息：`APITimeoutError: Request timed out`
- 原因：初始设置 10 秒超时过短，工具调用链路需要多次模型请求。
- 解决：所有 Provider 设为 `timeout=60.0, max_retries=1`；前端对流式请求不设端点超时，依赖后端输出。

## E007: 流式工具调用按增量碎片传输

- 表现：流式过程中收到的 tool_call 只有部分 id/name/arguments，无法执行工具。
- 解决：Provider 层按 index 聚合 tool_calls 增量，流式结束时统一发出完整 tool_call；同时请求 `stream_options.include_usage` 以获取真实 Token 用量。
