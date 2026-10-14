"""All settings live here. Values come from environment variables or a .env file."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file() -> None:
    """Tiny .env loader so we need no extra dependency. Real env vars win."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

# The sandbox root. Every tool path is resolved against this folder.
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", BASE_DIR / "workspace")).resolve()
TEMPLATES_DIR = BASE_DIR / "templates"
LOG_PATH = Path(os.environ.get("LOG_PATH", BASE_DIR / "logs" / "calls.jsonl"))

HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "8000"))
TRANSPORT = os.environ.get("MCP_TRANSPORT", "streamable-http")
AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")  # used for endpoint auth (Day 2)

# Limits that keep agent calls small and safe.
MAX_READ_CHARS = 20_000
MAX_WRITE_BYTES = 200_000
MAX_SEARCH_RESULTS = 50
MAX_LIST_ENTRIES = 200
GIT_TIMEOUT = 15
