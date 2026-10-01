# 工具定义与执行 - 用于 Function Calling / Tool Use 演示
# 关键导出：AVAILABLE_TOOLS, execute_tool
# 承重不变量：execute_tool 为同步阻塞函数（内部做真实网络请求），
#             调用方必须经 asyncio.to_thread 执行，避免阻塞事件循环。
import json
import math
from datetime import datetime

import httpx

# 工具 1：天气查询（Open-Meteo 实时数据，免 API Key）
WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询指定地点的当前实时天气（Open-Meteo，免密钥）",
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

# 工具 3：网页搜索（DuckDuckGo 实时结果）
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "搜索实时信息（DuckDuckGo 实时结果）",
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

# 工具 4：时间查询（IANA 时区，DST 感知）
TIME_TOOL = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "获取指定时区的当前日期和时间（IANA 时区库，自动处理夏令时）",
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

# WMO 天气代码 → 中文描述（Open-Meteo weather_code）
WMO_CODES = {
    0: "晴",
    1: "大致晴朗",
    2: "局部多云",
    3: "阴",
    45: "雾",
    48: "凇雾",
    51: "小毛毛雨",
    53: "中毛毛雨",
    55: "大毛毛雨",
    56: "冻毛毛雨",
    57: "强冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    80: "小阵雨",
    81: "中阵雨",
    82: "强阵雨",
    85: "小阵雪",
    86: "大阵雪",
    95: "雷阵雨",
    96: "雷阵雨伴小冰雹",
    99: "雷阵雨伴强冰雹",
}


def _weather(location, unit):
    last_err = None
    for _attempt in range(2):
        try:
            geo = httpx.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": location, "count": 1, "language": "zh", "format": "json"},
                timeout=15,
            ).json()
            results = geo.get("results") or []
            if not results:
                return json.dumps({"error": f"未找到城市: {location}"}, ensure_ascii=False)
            place = results[0]
            params = {
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
            }
            if unit == "fahrenheit":
                params["temperature_unit"] = "fahrenheit"
            wx = httpx.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=15).json()
            cur = wx.get("current", {})
            place_name = place.get("name", location)
            region = "".join(filter(None, [place.get("admin1", ""), place.get("country", "")]))
            return json.dumps(
                {
                    "location": f"{place_name}（{region}）" if region else place_name,
                    "temperature": cur.get("temperature_2m"),
                    "unit": unit,
                    "condition": WMO_CODES.get(cur.get("weather_code"), f"代码{cur.get('weather_code')}"),
                    "humidity": f"{cur.get('relative_humidity_2m')}%",
                    "wind_speed_kmh": cur.get("wind_speed_10m"),
                    "observed_at": cur.get("time"),
                    "demo": False,
                    "source": "open-meteo",
                },
                ensure_ascii=False,
            )
        except Exception as exc:
            last_err = exc
    return json.dumps(
        {"error": f"天气查询失败: {type(last_err).__name__}: {last_err}"}, ensure_ascii=False
    )


_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _search_bing(query):
    import re

    resp = httpx.get(
        "https://www.bing.com/search",
        params={"q": query, "setlang": "zh-hans"},
        headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"},
        timeout=8,
        follow_redirects=True,
    )
    resp.raise_for_status()
    rows = []
    blocks = re.findall(r'<li class="b_algo".*?</li>', resp.text, re.S)
    for blk in blocks[:5]:
        m = re.search(r"<h2[^>]*><a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", blk, re.S)
        if not m:
            continue
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        sm = re.search(r"<p[^>]*>(.*?)</p>", blk, re.S)
        snippet = re.sub(r"<[^>]+>", "", sm.group(1)).strip()[:200] if sm else ""
        rows.append({"title": title, "url": m.group(1), "snippet": snippet})
    return rows


def _search_baidu(query):
    import re

    resp = httpx.get(
        "https://www.baidu.com/s",
        params={"wd": query},
        headers={"User-Agent": _UA},
        timeout=8,
        follow_redirects=True,
    )
    resp.raise_for_status()
    rows = []
    for m in re.finditer(r"<h3[^>]*>\s*<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", resp.text, re.S):
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if title:
            rows.append({"title": title, "url": m.group(1), "snippet": ""})
        if len(rows) >= 5:
            break
    return rows


def _search_ddg_html(query):
    import re
    from urllib.parse import parse_qs, unquote, urlparse

    resp = httpx.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers={"User-Agent": _UA},
        timeout=8,
        follow_redirects=True,
    )
    resp.raise_for_status()
    rows = []
    anchors = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', resp.text, re.S)
    snippets = re.findall(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.S)
    for i, (href, title_html) in enumerate(anchors[:5]):
        title = re.sub(r"<[^>]+>", "", title_html).strip()
        url = href if not href.startswith("//") else "https:" + href
        if "uddg=" in url:
            url = unquote(parse_qs(urlparse(url).query).get("uddg", [url])[0])
        snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()[:200] if i < len(snippets) else ""
        rows.append({"title": title, "url": url, "snippet": snippet})
    return rows


def _web_search(query):
    """多后端实时搜索链：Bing → Baidu → DuckDuckGo HTML（仅依赖 httpx，按网络可达性自动降级）"""
    errors = []
    for backend, fn in (("bing", _search_bing), ("baidu", _search_baidu), ("duckduckgo-html", _search_ddg_html)):
        try:
            rows = fn(query)
            payload = {"query": query, "results": rows, "demo": False, "source": backend}
            if not rows:
                payload["note"] = "无结果"
            return json.dumps(payload, ensure_ascii=False)
        except Exception as exc:
            errors.append(f"{backend}: {type(exc).__name__}")
    return json.dumps(
        {"query": query, "error": "搜索失败（所有后端不可达）: " + "; ".join(errors), "demo": False},
        ensure_ascii=False,
    )


def _get_current_time(tz_name):
    from zoneinfo import ZoneInfo

    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        return json.dumps({"error": f"未知时区: {tz_name}"}, ensure_ascii=False)
    now = datetime.now(tz)
    offset = now.strftime("%z")
    return json.dumps(
        {
            "timezone": tz_name,
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "tz_abbr": now.tzname(),
            "utc_offset": f"UTC{offset[:3]}:{offset[3:]}",
            "dst": bool(now.dst()),
            "demo": False,
            "source": "zoneinfo",
        },
        ensure_ascii=False,
    )


def execute_tool(tool_name, arguments):
    """执行工具并返回结果字符串（同步阻塞；调用方须经 asyncio.to_thread）"""
    if tool_name == "get_weather":
        return _weather(arguments.get("location", "未知"), arguments.get("unit", "celsius"))

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
        return _web_search(arguments.get("query", ""))

    if tool_name == "get_current_time":
        return _get_current_time(arguments.get("timezone", "Asia/Shanghai"))

    return json.dumps({"error": f"未知工具: {tool_name}"})

# 修改记录：
#   2026-10-01 天气/搜索由演示桩改为真实数据源（Open-Meteo / 多后端搜索链），时间改 zoneinfo 修复 DST 错误；
#              所有工具结果带 demo:false 与 source 标注；失败返回 error 而非占位数据；
#              搜索不引入 ddgs 重依赖（镜像构建网络受限），多后端链 Bing→Baidu→DDG-HTML 按可达性降级；
#              天气请求超时 15s 且失败自动重试 1 次（抗容器冷启动 DNS 慢）；
#              启动预热经实测与首次调用并发触发限流，已按方案A移除
