# Application Configuration
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# 数据库路径：默认 data/ 子目录（目录挂载友好，Docker bind mount 单文件会在宿主缺失时被创建为目录导致 SQLITE_CANTOPEN）
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "logs.db")))

# Load .env file
load_dotenv(BASE_DIR / ".env")

# DeepSeek Configuration
DEEPSEEK_API_KEY = os.getenv(
    "DEEPSEEK_API_KEY",
    "",
)
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
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

# 修改记录：
#   2026-09-30 DEEPSEEK_BASE_URL 默认改为官方 https://api.deepseek.com/v1
#   2026-10-01 DATABASE_PATH 迁移到 data/logs.db（支持 DATABASE_PATH 环境变量覆盖），
#              配合 compose 目录挂载修复 SQLITE_CANTOPEN
