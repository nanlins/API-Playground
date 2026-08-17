# 重要决策记录

| ID | 决策 | 原因 |
|----|----------|-----------|
| D1 | 采用 OpenAI 兼容格式 | 行业标准，DeepSeek/Dashscope 均支持 |
| D2 | Provider 抽象层 | 方便扩展供应商，统一错误与流式处理 |
| D3 | SQLite 记录调用历史 | 零配置、适合教学项目 |
| D4 | 纯 HTML/CSS/JS | 无构建步骤，单页即可演示 |
| D5 | SSE 流式响应 | 浏览器原生支持，适合打字机效果 |
| D6 | 路径保持英文 | 避免 Windows 编码问题 |
| D7 | JSON Schema 控制结构化输出 | 精确控制输出格式 |
| D8 | 模型生成意图，系统执行工具 | 避免模型直接执行代码，提高安全性 |
| D9 | 只保留 DeepSeek + 通义千问 | 满足双供应商对比，减少维护面 |
| D10 | API Key 用独立请求字段 | 不写入模型消息，避免密钥泄露给供应商 |
| D11 | 嵌入固定 Dashscope | DeepSeek 无嵌入接口；确定嵌入模型为 `text-embedding-v2` |
| D12 | Provider 超时设为 60 秒 + 1 次重试 | 工具链路多次请求，短超时会误报失败 |
| D13 | 流式 tool call 聚合后传输 | 按供应商原生增量转发无法执行工具 |
| D14 | 流式请求 `include_usage` | 保证 Token 用量可录入历史；不支持时不伪造 0 |
| D15 | 错误映射 HTTP 状态码 | 认证失败 401、业务错误 4xx、内部错误 500 |
| D16 | 测试全部 Mock LLM | 不依赖外网，CI 稳定并覆盖请求参数与错误路径 |
| D17 | Pydantic 响应模型约束端点 | 返回结构明确，OpenAPI 文档与实现一致 |
| D18 | 密钥默认值清零并迁移到 .env | 防止真实凭据进入代码库，同时保留本地运行能力 |
| D19 | 畸形 JSON 返回 400 | 区分请求格式错误与内部故障 |
| D20 | 前端动态文案统一转义 | 避免角色标签等固定拼接成为注入面 |
| D21 | README 测试数量以实际为准 | 文档与 CI 口径保持一致 |
| D22 | 真实密钥不落本地工作区 | 部署环境通过私密环境变量注入，本地使用 .env.example 占位符 |
| D23 | 前端消息渲染不使用动态 innerHTML | 消除固定/动态拼接注入面 |
| D24 | Docker 镜像只包含运行时文件 | 缩小镜像并避免测试/文档进入生产 |
| D25 | README 提供单一运行入口说明 | 面试交付需按文档即可启动 | 快速开始覆盖依赖、.env、uvicorn、Docker、访问地址 |
| D26 | 依赖清单保留双入口并说明用途 | 保持 Docker 镜像只安装运行时依赖 | README 说明根 requirements 含测试依赖，backend 仅运行时 |
| D27 | 交付前清理陈旧模板与运行数据 | 保证仓库干净，避免误配或混入数据 | 删除 backend/.env.example 与 logs.db |
| D28 | 远端新增提交采用合并而非强推 | 避免覆盖远端历史 | fetch + merge origin/main，解决冲突后 push |
| D29 | 网页自定义供应商（ProviderConfig） | 用户无需改 .env/重启即可接入 Kimi、智谱、自定义网关 | API Key 只在单次请求内存中使用；非敏感配置存 localStorage，Key 存 sessionStorage |
| D30 | Embedding 供应商化 | DeepSeek 不支持嵌入，不同供应商需要不同模型 | 内置默认 Dashscope；自定义供应商按 supports_embedding 过滤并动态创建客户端 |
