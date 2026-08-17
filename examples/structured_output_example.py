import json

import httpx

BASE_URL = "http://localhost:8000"
SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
    },
    "required": ["name", "age"],
}


def main() -> None:
    payload = {
        "model": "deepseek/deepseek-v4-flash",
        "messages": [{"role": "user", "content": "John, 25"}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "p", "schema": SCHEMA},
        },
    }
    response = httpx.post(BASE_URL + "/v1/chat/completions", json=payload)
    print(json.dumps(response.json(), indent=2))


main()
