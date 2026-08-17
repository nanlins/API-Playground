# 工具定义与执行 - 用于 Function Calling / Tool Use 演示
import json
import math
from datetime import UTC, datetime, timedelta

# 工具 1：天气查询（返回演示数据，不请求真实天气服务）
WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询指定地点的当前天气（演示数据）",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "城市名称，如北京、上海、东京",
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "温度单位",
                },
            },
            "required": ["location"],
        },
    },
}

# 工具 2：计算器
CALCULATOR_TOOL = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "对两个数字进行算术运算",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide", "power"],
                    "description": "算术运算类型",
                },
                "a": {"type": "number", "description": "第一个操作数"},
                "b": {"type": "number", "description": "第二个操作数"},
            },
            "required": ["operation", "a", "b"],
        },
    },
}

# 工具 3：网页搜索（返回演示结果，不访问真实搜索引擎）
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "搜索实时信息（返回演示结果）",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词",
                },
            },
            "required": ["query"],
        },
    },
}

# 工具 4：时间查询
TIME_TOOL = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "获取指定时区的当前日期和时间",
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "时区名称，如 Asia/Shanghai、America/New_York",
                },
            },
        },
    },
}

# 可用工具列表
AVAILABLE_TOOLS = [WEATHER_TOOL, CALCULATOR_TOOL, SEARCH_TOOL, TIME_TOOL]


def execute_tool(tool_name, arguments):
    """执行工具并返回结果字符串"""
    if tool_name == "get_weather":
        location = arguments.get("location", "未知")
        unit = arguments.get("unit", "celsius")
        temp = 22 if unit == "celsius" else 72
        return json.dumps(
            {
                "location": location,
                "temperature": temp,
                "unit": unit,
                "condition": "多云",
                "humidity": "65%",
                "demo": True,
            },
            ensure_ascii=False,
        )

    if tool_name == "calculator":
        op = arguments.get("operation")
        a = arguments.get("a", 0)
        b = arguments.get("b", 0)
        if op == "add":
            result = a + b
        elif op == "subtract":
            result = a - b
        elif op == "multiply":
            result = a * b
        elif op == "divide":
            result = "错误：除数不能为零" if b == 0 else a / b
        elif op == "power":
            result = math.pow(a, b)
        else:
            result = f"未知运算: {op}"
        return json.dumps({"operation": op, "a": a, "b": b, "result": result})

    if tool_name == "web_search":
        query = arguments.get("query", "")
        return json.dumps(
            {
                "query": query,
                "results": [
                    {"title": f"{query} 相关结果", "url": f"https://example.com/search?q={query}"},
                ],
                "demo": True,
            },
            ensure_ascii=False,
        )

    if tool_name == "get_current_time":
        tz_name = arguments.get("timezone", "Asia/Shanghai")
        tz_map = {
            "Asia/Shanghai": 8,
            "Asia/Tokyo": 9,
            "America/New_York": -5,
            "America/Los_Angeles": -8,
            "Europe/London": 0,
            "UTC": 0,
        }
        offset = tz_map.get(tz_name, 8)
        now = datetime.now(UTC) + timedelta(hours=offset)
        return json.dumps(
            {
                "timezone": tz_name,
                "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                "utc_offset": f"UTC{'+' if offset >= 0 else ''}{offset}",
            },
            ensure_ascii=False,
        )

    return json.dumps({"error": f"未知工具: {tool_name}"})
