import json

import httpx

BASE_URL = "http://localhost:8000"


def main() -> None:
    payload = {
        "model": "deepseek/deepseek-v4-flash",
        "messages": [{"role": "user", "content": "Weather in Beijing?"}],
    }
    response = httpx.post(BASE_URL + "/v1/tool-chain", json=payload)
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))


main()
