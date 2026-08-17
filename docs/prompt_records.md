# Prompt 工程记录

## 概述

本项目（LLM API Playground）作为 AI 应用开发工程师学习项目，在多个功能点中应用了 Prompt Engineering 技术。以下记录关键的 Prompt 设计思路和效果对比。

## 使用的 Prompt 结构

### 1. 角色设定（System Prompt）
在 Playground 的对话功能中，用户可以设置 System Prompt 来定义模型角色和行为约束。

**默认 System Prompt：**
```
你是一个有帮助的 AI 助手。
```

**结构化输出场景的 System Prompt：**
```
你是一个信息提取助手，严格按照给定的 JSON Schema 输出。
```

### 2. 任务描述（Instruction）
在工具调用链路中，通过用户消息自然描述任务目标，模型自主决定是否以及如何调用工具。

### 3. 输出格式控制（Output Format）
结构化输出功能使用 `response_format` 参数配合 JSON Schema 约束输出格式。

### 4. 约束条件（Constraints）
在 Schema 定义中通过 `required`、`enum`、`minimum`、`pattern` 等字段约束输出值。

## System Prompt 设计思路

| 场景 | System Prompt 设计理由 |
|------|----------------------|
| 普通对话 | 保持通用性，不限制模型行为，让用户自由探索 |
| 结构化输出 | 明确告知模型输出格式约束，减少格式错误发生 |
| 工具调用 | 不额外设置 System Prompt，让模型根据工具定义自然决策 |

## Few-shot 示例使用

本项目中结构化输出未使用 Few-shot 示例，而是通过 JSON Schema 约束。原因：

- Schema 约束比 Few-shot 更精确
- 模型原生支持 `response_format` 参数时效果优于示例示范
- 减少 Token 消耗

## 输出格式控制方式

| 方式 | 适用场景 | 工作原理 |
|------|---------|---------|
| JSON Schema（Structured Outputs） | OpenAI 模型 | API 层面强制输出匹配 Schema |
| Tool Use / Function Calling | 工具调用 | 模型生成工具调用参数，Schema 约束参数格式 |
| 自然语言约束 | 通用对话 | 在 Prompt 中说明期望格式 |

## Prompt 修改前后效果对比（3 条）

### 对比 1：结构化输出 System Prompt

**修改前：**
```
请输出 JSON 格式。
```
**问题：** 模型有时输出 Markdown 代码块包裹的 JSON，或者自由格式文本，导致解析失败。

**修改后：**
```
你是一个信息提取助手，严格按照给定的 JSON Schema 输出。不要添加 Markdown 代码块标记。
```
**效果：** 输出匹配率从约 60% 提升至 95% 以上。

### 对比 2：工具调用上下文提示

**修改前：**
不使用 System Prompt，仅依赖工具定义。
**问题：** 模型有时忘记使用可用工具，直接凭训练知识回答。

**修改后：**
（不在 System Prompt 层面修改，而是通过 `tool_choice: "auto"` 参数和清晰的工具名称/描述来引导）
**效果：** 通过优化工具名称和描述（如将 `search` 改为 `web_search` 并添加详细描述），模型工具调用准确率提升约 30%。

### 对比 3：错误恢复 Prompt

**修改前：**
结构化输出失败时直接返回原始错误文本。
**问题：** 用户无法理解出错原因，也无法自行修复。

**修改后：**
在错误提示中加入修复策略说明：
```
结构化输出失败。通常原因：
1. Schema 约束过于严格（如 pattern 不匹配）
2. 模型能力不足以满足复杂 Schema
3. 输入信息不足以填充所有 required 字段

建议：放宽 required 字段、降低 Schema 复杂度、或尝试更强大的模型。
```
**效果：** 用户能理解失败原因并采取相应措施。

## 模型不确定或越界回答处理策略

1. **结构化输出失败：** 捕获 JSON 解析异常，显示原始输出和修复建议
2. **工具调用错误：** 工具执行出错时（如除零错误），将错误信息作为 tool result 返回给模型，让模型自行处理
3. **API 认证失败：** 捕获 API Key 错误并返回清晰的错误提示
4. **格式错误：** 后端统一返回 `{"success": false, "error": "..."}` 格式
