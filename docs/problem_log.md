# 问题记录

| 编号 | 问题 | 原因 | 解决 |
|---|---|---|---|
| P1 | PowerShell 编码问题 | cp932/cp950 会损坏中文路径与文本 | 使用 apply_patch/Python 跑笔记写入，路径保持英文 |
| P2 | apply_patch 前导空格 | 每行多一个前导空格 | 写修复脚本去除空格 |
| P3 | SSE 流式 | 浏览器需要逐 token 展示 | 使用 SSE + ReadableStream |
| P4 | Anthropic 消息格式差异 | 不同供应商消息格式不一致 | Provider 层转换消息格式 |
| P5 | 没有 API Key | 请求未携带密钥 | 提供友好的错误提示与后端默认密钥 |
| P6 | 嵌入功能 401/400 | 嵌入指向 OpenAI/错误 Provider | 嵌入固定 Dashscope + `text-embedding-v2` |
| P7 | 结构化输出 400 | DeepSeek 不支持 `response_format` | 转为 System Prompt 指令 |
| P8 | 工具链路超时 | 10 秒超时过短 | 供应商设为 60 秒 + 1 次重试 |
| P9 | 流式 tool call 碎片 | OpenAI 流式按 index 增量返回 | Provider 层聚合后统一发出 |
| P10 | 流式 usage 为 0 | 没有请求 `include_usage` | 添加 `stream_options`，不可用时标记 `available=False` |
| P11 | 密钥写入 system 消息 | 老版本用 `_api_key` 消息字段传递 | 请求独立 `api_key` 字段，转发前从消息中剥离 |
| P12 | 前端添加系统提示词重置历史 | 直接重置 chatHistory | 只替换存在的 system 消息，保留用户/助手消息 |
| P13 | config.py 默认值写死真实 API Key | 代码泄露真实凭据，空 Key 请求未统一返回 401 | 默认值改为空字符串；真实 Key 仅写入被 gitignore 的 .env；聊天/工具链路缺 Key 返回 401 |
| P14 | /v1/tools/execute 畸形 JSON 返回 500 | 未捕获 JSONDecodeError | 捕获后返回 400，并补充测试 |
| P15 | 前端角色标签直接拼接 innerHTML | role 文案未转义 | 统一调用 escapeHtml |
| P16 | README 测试数量与实际不符 | 文档写 18，实际 22 | README 改为 22 个，后续以 pytest 实际结果为准 |
| P17 | 本地 .env 保存真实 API Key | 凭据落盘即存在泄露面 | 删除本地 .env，真实 Key 改为部署机环境变量或用户本地配置 |
| P18 | 前端 addMessage 仍对 extra 直接 innerHTML | 动态 HTML 拼接存在低风险注入面 | 移除 extra 参数，角色与消息统一使用 DOM/textContent 构建 |
| P19 | Docker 镜像包含 tests/docs/examples/.github | 生产镜像体积增大且含开发文件 | Dockerfile 仅 COPY backend/frontend，.dockerignore 补充开发目录 |
| P20 | README 缺少运行说明与仓库链接 | 交付验收要求仓库可直接启动并展示 GitHub 地址 | 增加快速开始与 GitHub 链接 |
| P21 | backend/.env.example 残留旧供应商配置 | 与根目录 .env.example 重复且内容过时 | 删除 backend 副本，只保留根目录一份 |
| P22 | 工作区残留 logs.db 运行数据 | 直接打包交付时会混入运行时数据 | 删除 logs.db，README 说明运行时自动创建 |
| P23 | 根目录与 backend 存在两份依赖清单 | 后续容易单边更新 | README 明确开发/测试依赖与 Docker 运行时依赖差异 |
| P24 | 推送被远端拒绝（非快进） | GitHub 上存在未同步的 README 提交 ecbf7ca | fetch 后 merge origin/main，解决 README 冲突并保留远端删除内容后推送 |
| P25 | 供应商管理前端白屏 | JS 引用了未定义的 loadCustomProviders/currentProviderConfig 等函数 | 补全供应商管理函数，页面加载时合并内置与自定义供应商 |
| P26 | 自定义供应商无法接入 | 后端固定 deepseek/dashscope | 新增 ProviderConfig 与 /v1/providers/test，请求级动态创建 OpenAI 兼容客户端 |
| P27 | 自定义供应商 API Key 可能进历史 | 历史 input_data 若保存完整配置会带 Key | 保存历史前脱敏 api_key，前端 Key 存 sessionStorage |
