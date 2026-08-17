import httpx

BASE_URL = "http://localhost:8000"


def main() -> None:
    payload = {
        "model": "deepseek/deepseek-v4-flash",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
    }
    response = httpx.post(BASE_URL + "/v1/chat/completions", json=payload)
    print(response.json())


main()
