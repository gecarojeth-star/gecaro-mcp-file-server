"""Audit log + error hygiene for every tool call."""
import functools
import inspect
import json
import time
from datetime import datetime, timezone

from . import config
from .errors import ToolInputError


def _short(value, limit: int = 120):
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"...(+{len(value) - limit} chars)"
    return value


def _write_log(entry: dict) -> None:
    try:
        config.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(config.LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # logging must never break a tool call


def audited(fn):
    """Log every call (name, short args, ok/error, duration) and never leak stack traces.

    Expected problems (ToolInputError) pass through with their helpful message.
    Anything unexpected is logged in full but reported to the agent generically.
    """
    sig = inspect.signature(fn)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        started = time.perf_counter()
        try:
            bound = sig.bind(*args, **kwargs)
            shown = {k: _short(v) for k, v in bound.arguments.items()}
        except TypeError:
            shown = {}
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "tool": fn.__name__, "args": shown}
        try:
            result = fn(*args, **kwargs)
        except ToolInputError as exc:
            entry.update(ok=False, error=str(exc))
            raise
        except Exception as exc:  # noqa: BLE001
            entry.update(ok=False, error=f"{type(exc).__name__}: {exc}")
            raise ToolInputError(
                f"Internal error ({type(exc).__name__}). The server log has details."
            ) from None
        else:
            entry.update(ok=True)
            return result
        finally:
            entry["ms"] = round((time.perf_counter() - started) * 1000, 1)
            _write_log(entry)

    return wrapper
