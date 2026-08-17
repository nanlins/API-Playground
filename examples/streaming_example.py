import httpx

BASE_URL = "http://localhost:8000"


def main() -> None:
    payload = {
        "model": "deepseek/deepseek-v4-flash",
        "messages": [{"role": "user", "content": "count 1-3"}],
        "stream": True,
    }
    with httpx.stream(
        "POST", BASE_URL + "/v1/chat/completions", json=payload, timeout=30
    ) as response:
        for line in response.iter_lines():
            if line is None or not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                break
            print(data)


main()
