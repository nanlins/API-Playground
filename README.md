# LLM API Playground

> 用途：交互式 LLM API 体验平台（DeepSeek / 通义千问双供应商）——聊天、流式、结构化输出、真实工具调用（天气/搜索/时间/计算器）、嵌入对比与调用历史，配套 Web 前端与 Docker 部署。

[![CI](https://github.com/nanlins/API-Playground/actions/workflows/ci.yml/badge.svg)](https://github.com/nanlins/API-Playground/actions/workflows/ci.yml)

GitHub: https://github.com/nanlins/API-Playground

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
| 1 | 普通对话调用 | `POST /v1/chat/completions` |
| 2 | 流式响应 | `POST /v1/chat/completions` + `stream=true` |
| 3 | 结构化输出 | `POST /v1/chat/completions` + `response_format`（json_object / json_schema） |
| 4 | 工具调用链路 | `POST /v1/tool-chain`（真实数据工具） |
| 5 | 嵌入生成与相似度计算 | `POST /v1/embeddings`、`/v1/embeddings/compare` |
| 6 | 调用历史 | `GET /v1/history`、`/v1/history/{id}` |
| 7 | 供应商与模型列表 | `GET /v1/models` |
| 8 | 网页供应商管理 | 添加/编辑/删除自定义 OpenAI 兼容供应商并测试连接（`POST /v1/providers/test`） |

---

## 工具调用链路演示

完整的工具调用分三步：

1. **模型生成工具调用意图** — 模型分析用户输入，决定调用哪个工具并填充参数
2. **系统执行工具** — 后端执行对应工具，返回结果
3. **模型生成最终回复** — 工具结果回传，模型据此生成自然语言回复

核心原则：**模型只生成工具调用意图，系统负责执行工具。**

### 可用工具（真实数据）

| 工具 | 数据源 | 说明 |
|------|--------|------|
| `get_weather` | Open-Meteo（免密钥） | 实时天气；定位链：离线坐标表 → Nominatim → Open-Meteo 地理编码 |
| `calculator` | 本地运算 | 加/减/乘/除/幂 |
| `web_search` | Bing → 百度 → DuckDuckGo-HTML 多后端链 | 实时搜索，按网络可达性自动降级 |
| `get_current_time` | zoneinfo（IANA 时区库） | 自动处理夏令时（DST） |

所有工具结果带 `demo:false` 与 `source` 字段标注数据来源；失败返回明确 `error`（网络/未找到城市），不返回占位数据。

> 天气定位：内置 `backend/city_coords.py` 离线坐标表（34 省级 + 全部地级市 + 常用县 + 常见外国城市中文音译），省级名映射省会代表坐标（如"河北省"→石家庄），县级与外国城市由 Nominatim（OpenStreetMap）兜底。

---

## 结构化输出与"失败案例"

演示结构化输出在 Schema 约束下的两类现象：

1. **格式失败**：Schema 过严（pattern 正则等）时，模型可能输出非法 JSON → 自动重试 2 次，仍失败则展示原始输出、解析错误与修复建议（放宽 required、简化嵌套、换更强模型）。
2. **语义失败（编造）**：输入缺少必填字段信息时，模型会为满足 Schema 而**编造**字段值（例如编造 `metadata.internal_id`）。页面通过**接地检查**把输入文本中无依据的叶子字段红字标注为"模型编造"，提示 **Schema 只保证格式、不保证真实**。

操作：结构化输出标签页点「加载 Schema 失败案例」→ 输入"李四今年 30 岁"→ 发送，观察红字标注。

---

## 供应商对比

| 功能 | DeepSeek | 通义千问（Dashscope） |
|------|----------|---------------------|
| 对话模型 | deepseek-flash / deepseek-v4-pro | qwen-plus / qwen-max / qwen-turbo |
| 流式响应 | 支持 | 支持 |
| 结构化输出 | 支持（json_object / json_schema） | 支持（原生 response_format） |
| 工具调用 | 支持 | 支持 |
| 嵌入向量 | 不支持 | text-embedding-v2 |

> 模型名需带供应商前缀：`deepseek/deepseek-flash`、`dashscope/qwen-plus`。裸写模型名默认按已知模型列表推断供应商，无法确定时返回明确 400。

---

## Prompt 工程

详细记录见 [docs/prompt_records.md](docs/prompt_records.md)，包含使用的 Prompt 结构、System Prompt 设计思路、Few-shot 取舍、输出格式控制、越界处理策略与修改前后对比。

## 网页供应商配置

页面「供应商管理」可添加任意 OpenAI 兼容供应商（Kimi、智谱、自定义网关等），无需改 `.env` 或重启。非敏感配置存 `localStorage`，API Key 存 `sessionStorage`（关页即清），不写入仓库、不进 Git、不进日志/历史/响应。

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate  /  macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env   # Windows: copy .env.example .env
```

编辑 `.env` 填入 `DEEPSEEK_API_KEY`（`DEEPSEEK_BASE_URL=https://api.deepseek.com/v1`、`DEEPSEEK_MODELS=deepseek-flash`）与可选的 `DASHSCOPE_API_KEY`（嵌入功能用）。也可在页面顶部直接输入 Key。

### 3. 启动后端

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

浏览器访问 `http://localhost:8000`。

### 4. Docker 启动

```bash
# 国内网络可加构建参数加速：
docker compose build --build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
docker compose up -d --force-recreate
```

- 数据库（调用历史）落在宿主机 `data/logs.db`，通过 `./data:/app/data` 目录挂载持久化。
- 构建期 pip 源可用 `PIP_INDEX_URL` 覆盖（默认官方源保证 CI 一致），并内置 `--retries/--timeout` 抗镜像限流。

## 依赖清单

- 根目录 `requirements.txt`：本地开发与测试依赖（含 pytest、ruff、tzdata）
- `backend/requirements.txt`：Docker 运行时依赖（仅后端运行所需）

## 运行测试

```bash
python -m pytest tests/ -v     # 33 个测试全部通过
ruff check backend/ tests/     # 代码风格
```

## 项目结构

```text
llm-playground/
  backend/
    main.py           FastAPI 入口（路由、SSE、工具链路、接地检查）
    tools.py          工具定义与执行（真实天气/搜索/时间/计算器）
    city_coords.py    离线省市县/外国城市坐标表 + 归一化
    providers.py      供应商抽象（OpenAI 兼容）
    database.py       调用历史 SQLite（保存失败不中断主链路）
    config.py         配置（.env 加载）
  frontend/           单页 Web UI（HTML/CSS/JS）
  tests/              pytest 测试套件
  examples/           使用示例脚本
  docs/               文档
  README.md           本文件
```

## 历史说明

本仓库早期历史存在机器化提交形态：2026-08-17 20:17 同一分钟 33 个 commit（逐文件提交规程产物）。该形态源于当时执行的"逐文件提交"自动化规程，不代表真实开发节奏；自 2026-09-29 起已改为功能分支 + 逻辑分组提交 + squash 合并，并以 CI 门禁（测试/lint/格式/构建）作为合并前提。

## 修改记录

- 2026-09-29：新增 docker job（hashFiles 守卫）与 CI badge、历史说明小节
- 2026-09-30：DeepSeek 真实接入工程缺陷修复（模型路由/默认 max_tokens/官方 base_url）
- 2026-10-01：修复 Docker 下 SQLITE_CANTOPEN（目录挂载 data/）与流式中断/结构化 500
- 2026-10-01：工具真实数据化（天气/搜索/时间）、结构化接地检查、冷启动韧性、docker pip 源 ARG
- 2026-10-01：天气定位链支持省级/县级/外国城市（离线坐标表 + Nominatim 兜底）
- 2026-10-01：重写 README，同步真实工具数据源、定位链、模型前缀、Docker 挂载等当前实现
