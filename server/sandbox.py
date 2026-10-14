"""Path sandbox. Every file tool must call resolve_path() before touching disk."""
from pathlib import PureWindowsPath

from . import config
from .errors import ToolInputError

# Top-level folders agents may never touch (git hooks could run code).
PROTECTED_TOP_DIRS = {".git"}
# The handoff files that carry context between sessions. They cannot be deleted.
HANDOFF_FILES = {"PROJECT_STATE.md", "PLAN_LOG.md", "CHECKPOINTS.md", "DECISIONS.md"}


class SandboxError(ToolInputError):
    """The requested path is outside what the agent is allowed to use."""


def resolve_path(user_path, *, allow_protected: bool = False):
    """Turn an agent-supplied relative path into an absolute path inside the workspace.

    Rejects: non-strings, null bytes, absolute paths, drive letters, '..' escapes,
    symlinks that point outside the root, and the protected .git folder.
    """
    if not isinstance(user_path, str):
        raise SandboxError("path must be a string")
    if "\x00" in user_path:
        raise SandboxError("path contains a null byte")

    cleaned = user_path.strip().replace("\\", "/")
    win = PureWindowsPath(cleaned)
    if cleaned.startswith("/") or win.drive or win.anchor:
        raise SandboxError(
            "absolute paths are not allowed; use a path relative to the workspace root"
        )

    root = config.WORKSPACE_ROOT
    target = root if cleaned in ("", ".") else (root / cleaned).resolve()

    try:
        rel = target.relative_to(root)
    except ValueError:
        raise SandboxError("path escapes the workspace root") from None

    if not allow_protected and rel.parts and rel.parts[0].lower() in PROTECTED_TOP_DIRS:
        raise SandboxError(f"'{rel.parts[0]}' is protected and cannot be accessed")
    return target


def rel_posix(target) -> str:
    """Path relative to the workspace root, always with forward slashes."""
    root = config.WORKSPACE_ROOT
    return "." if target == root else target.relative_to(root).as_posix()
