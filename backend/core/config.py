import os

from dotenv import load_dotenv


load_dotenv()


# ============================================================
# MINIO / STORAGE
# ============================================================

MINIO_ENDPOINT = os.getenv(
    "STORAGE_ENDPOINT",
    "localhost:9000"
)

MINIO_ACCESS_KEY = os.getenv(
    "STORAGE_ACCESS_KEY",
    "minioadmin"
)

MINIO_SECRET_KEY = os.getenv(
    "STORAGE_SECRET_KEY",
    "minioadmin123"
)

MINIO_BUCKET = os.getenv(
    "STORAGE_BUCKET",
    "invoice-ai"
)

MINIO_SECURE = (
    os.getenv(
        "STORAGE_SECURE",
        "false"
    ).lower()
    == "true"
)


# ============================================================
# HUGGING FACE / LLM
# ============================================================

HF_TOKEN = os.getenv(
    "HF_TOKEN",
    ""
)

HF_MODEL = os.getenv(
    "HF_MODEL",
    "Qwen/Qwen3.8-27B"
)

HF_PROVIDER = os.getenv(
    "HF_PROVIDER",
    "auto"
)


# ============================================================
# WEB SERVICE
# ============================================================

WEB_SERVICE_URL = os.getenv(
    "WEB_SERVICE_URL",
    ""
)

WEB_SERVICE_METHOD = os.getenv(
    "WEB_SERVICE_METHOD",
    "POST"
).upper()

WEB_SERVICE_TIMEOUT = int(
    os.getenv(
        "WEB_SERVICE_TIMEOUT",
        "30"
    )
)

WEB_SERVICE_TOKEN = os.getenv(
    "WEB_SERVICE_TOKEN",
    ""
)

WEB_SERVICE_USERNAME = os.getenv(
    "WEB_SERVICE_USERNAME",
    ""
)

WEB_SERVICE_PASSWORD = os.getenv(
    "WEB_SERVICE_PASSWORD",
    ""
)


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

CONFIG_DIR = os.path.join(
    BASE_DIR,
    "config"
)