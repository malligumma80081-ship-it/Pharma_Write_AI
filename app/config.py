import os

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3.2",
)

APP_NAME = "PharmaWrite AI"
APP_VERSION = "0.1.0"