# LLM API Playground

GitHub: https://github.com/nanlins/API-Playground

交互式 LLM API 体验平台，支持 DeepSeek 和通义千问（Dashscope）两个供应商。
---

## 核心概念

| 概念 | 说明 |
|------|------|
| **message（消息）** | 对话的基本单位，包含 role（角色）和 content（内容） |
| **role（角色）** | 标识消息发送者：system（系统指令）、user（用户输入）、assistant（模型回复）、tool（工具执行结果） |
| **tool call（工具调用）** | 模型生成的工具调用意图（工具名+参数）。模型只决定调用哪个工具，执行由业务系统负责 |
| **tool result（工具结果）** | 工具执行后的返回结果，回传给模型用于生成最终回复 |
| **stream（流式）** | 服务端通过 SSE 逐 token 推送，实现打字机效果 |
| **usage（用量）** | Token 消耗统计：prompt_tokens（输入）、completion_tokens（输出）、total_tokens（总计） |

---

## 功能列表

| # | 功能 | 说明 |
|---|------|------|
| 1 | 普通对话调用 | POST /v1/chat/completions |
| 2 | 流式响应 | POST /v1/chat/completions + stream=true |
| 3 | 结构化输出 | POST /v1/chat/completions + response_format |
| 4 | 工具调用链路 | POST /v1/tool-chain |
| 5 | 嵌入生成与相似度计算 | POST /v1/embeddings/compare |
| 6 | 调用历史 | GET /v1/history |
| 7 | 双供应商对比 | GET /v1/models |
| 8 | 供应商和模型列表 | 页面顶部下拉框切换 |
| 9 | 网页供应商管理 | 添加/编辑/删除自定义 OpenAI 兼容供应商并测试连接 |

---

## 工具调用链路演示

完整的工具调用分为三步：

1. **模型生成工具调用意图** — 模型分析用户输入，决定调用哪个工具并填充参数
2. **系统执行工具** — 后端执行对应的工具函数（天气查询、计算器、网页搜索、时间查询），返回结果
3. **模型生成最终回复** — 工具执行结果回传给模型，模型据此生成自然语言回复

核心原则：**模型只生成工具调用意图，系统负责执行工具。**

可用工具：
- get_weather - 查询指定地点的天气
- calculator - 算术运算（加、减、乘、除、幂）
- web_search - 搜索实时信息
- get_current_time - 获取指定时区的当前时间

注意：`get_weather` 和 `web_search` 返回的是教学演示数据，并不请求真实天气或搜索服务。

验证方式：在页面「工具调用」标签页中输入问题，点击「调用工具链路」按钮，即可看到完整的步骤展示。

---

## 结构化输出失败处理

演示结构化输出在 Schema 约束过严时的失败场景：

1. 在「结构化输出」标签页中点击「测试 Schema 失败案例」按钮
2. 系统会加载一个包含严格约束（如 pattern 正则匹配）的 JSON Schema
3. 输入缺少必要字段的数据，发送请求
4. 模型输出无法匹配 Schema，返回错误
5. 页面会显示：
   - 原始模型输出
   - JSON 解析错误详情
   - 修复策略建议（放宽约束、简化 Schema、使用更强模型）

修复策略示例：
- 移除或放宽 pattern 约束
- 减少 required 字段
- 简化嵌套结构

---

## 供应商对比

| 功能 | DeepSeek | 通义千问（Dashscope） |
|------|----------|---------------------|
| 对话模型 | deepseek-v4-flash / deepseek-v4-pro | qwen-plus / qwen-max / qwen-turbo |
| 流式响应 | 支持 | 支持 |
| 结构化输出 | 通过 System Prompt 指令实现 | 通过原生 response_format 参数 |
| 工具调用 | 支持 | 支持 |
| 嵌入向量 | 不支持 | text-embedding-v2 |

---

## Prompt 工程

详细记录见 [docs/prompt_records.md](docs/prompt_records.md)，包含：

- 使用的 Prompt 结构（角色设定、任务描述、输出格式控制、约束条件）
- System Prompt 设计思路
- 是否使用 Few-shot 示例（本项目未使用，原因在文档中说明）
- 输出格式控制方式
- 模型不确定或越界回答的处理策略
- 3 组 Prompt 修改前后的效果对比

## 网页供应商配置

页面「供应商管理」标签页可添加任意 OpenAI 兼容供应商（如 Kimi、智谱、自定义网关），无需修改 `.env` 或重启服务。

### 添加供应商

1. 打开「供应商管理」，点击「+ 新增供应商」。
2. 填写名称、显示名、Base URL、API Key、聊天模型和 Embedding 模型。
3. 点击「保存」，供应商会立即出现在顶部聊天下拉框和 Embedding 供应商下拉框。

内置供应商继续从 `.env` 读取；自定义供应商只保存在当前浏览器：
- 非敏感配置（名称、Base URL、模型列表）保存到 `localStorage`
- API Key 单独保存到 `sessionStorage`，关闭页面后清除
- 自定义供应商不会写入 `backend/config.py`，也不会进入 Git

### 测试连接

保存前可点击「测试聊天」或「测试 Embedding」，后端会调用一次 `POST /v1/providers/test` 并显示模型、耗时与向量维度。

### 安全说明

API Key 仅用于当前请求，不会出现在日志、历史记录和接口响应中。

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
copy .env.example .env
```

编辑 `.env`，填入 DeepSeek 和 Dashscope 密钥。也可以在页面顶部直接输入 Key，无需修改 `.env`；嵌入功能默认使用 Dashscope，也可在「供应商管理」中添加支持 Embedding 的自定义供应商。

### 3. 启动后端

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

浏览器访问 `http://localhost:8000`。

### 4. Docker 启动

```bash
docker compose up -d
```

浏览器访问 `http://localhost:8000`，`logs.db` 会在运行时自动创建。

## 依赖清单

- 根目录 `requirements.txt`：本地开发与测试依赖，包含 pytest、ruff 等工具
- `backend/requirements.txt`：Docker 运行时依赖，只包含后端运行所需包

---

---

## 运行测试

```bash
python -m pytest tests/ -v
```

预期 33 个测试全部通过，涵盖 API 路由、流式 usage、工具调用增量聚合与错误处理。

## 项目结构

```text
llm-playground/
  backend/          FastAPI 后端（路由、供应商抽象、数据库日志、工具定义）
  frontend/         单页 Web UI（HTML/CSS/JS）
  tests/            pytest 测试套件
  examples/         使用示例脚本
  docs/             文档（Prompt 记录、问题日志、决策记录、错误解决方案）
  README.md         本文件
  .gitignore        Git 忽略规则
```
