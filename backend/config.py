# Application Configuration
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "logs.db"

# Load .env file
load_dotenv(BASE_DIR / ".env")

# DeepSeek Configuration
DEEPSEEK_API_KEY = os.getenv(
    "DEEPSEEK_API_KEY",
    "",
)
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://opencode.ai/zen/go/v1")
DEEPSEEK_MODELS = os.getenv(
    "DEEPSEEK_MODELS",
    "deepseek-v4-flash,deepseek-v4-pro",
).split(",")

# Dashscope (Qwen) Configuration
DASHSCOPE_API_KEY = os.getenv(
    "DASHSCOPE_API_KEY",
    "",
)
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)
DASHSCOPE_MODELS = os.getenv(
    "DASHSCOPE_MODELS",
    "qwen-plus,qwen-max,qwen-turbo",
).split(",")
DASHSCOPE_EMBEDDING_MODEL = os.getenv(
    "DASHSCOPE_EMBEDDING_MODEL",
    "text-embedding-v2",
)

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
