import httpx

BASE_URL = "http://localhost:8000"


def main() -> None:
    payload = {
        "model": "text-embedding-3-small",
        "text1": "AI is great",
        "text2": "ML is AI subset",
    }
    response = httpx.post(BASE_URL + "/v1/embeddings/compare", json=payload)
    print(response.json()["data"]["cosine_similarity"])


main()
