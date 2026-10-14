"""git-lite: status, commit, log for the workspace repo. No push, reset or checkout."""
import os
import subprocess

from .. import config
from ..audit import audited
from ..errors import ToolInputError


def _git(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    cmd = ["git", "-c", "user.name=mcp-agent", "-c", "user.email=agent@localhost", *args]
    try:
        return subprocess.run(
            cmd, cwd=config.WORKSPACE_ROOT, capture_output=True, text=True,
            timeout=config.GIT_TIMEOUT, env=env,
        )
    except FileNotFoundError:
        raise ToolInputError("git is not installed on the server.") from None
    except subprocess.TimeoutExpired:
        raise ToolInputError("git took too long and was stopped.") from None


def ensure_repo() -> None:
    """Called at startup: make the workspace a git repo if it is not one yet."""
    if not (config.WORKSPACE_ROOT / ".git").exists():
        _git("init")


@audited
def git_status() -> str:
    """Show which workspace files are new, changed or deleted since the last commit.

    Run this before git_commit to check what will be saved.
    """
    proc = _git("status", "--short", "--branch")
    if proc.returncode != 0:
        raise ToolInputError("The workspace is not a git repository.")
    return proc.stdout.strip() or "Working tree clean."


@audited
def git_commit(message: str) -> str:
    """Commit ALL current workspace changes with a message. Use after finishing a step.

    Write a message that says what changed and why. There is no undo tool, so check
    git_status first.

    Args:
        message: Commit message, 1-300 characters.
    """
    message = (message or "").strip()
    if not 1 <= len(message) <= 300:
        raise ToolInputError("message must be 1-300 characters.")
    if not _git("status", "--porcelain").stdout.strip():
        return "Nothing to commit."
    if _git("add", "-A").returncode != 0:
        raise ToolInputError("git add failed.")
    proc = _git("commit", "-m", message)
    if proc.returncode != 0:
        raise ToolInputError("git commit failed: " + (proc.stderr.strip() or proc.stdout.strip())[:200])
    short = _git("rev-parse", "--short", "HEAD").stdout.strip()
    return f"Committed {short}: {message.splitlines()[0]}"


@audited
def git_log(max_count: int = 10) -> str:
    """Show recent commits, newest first, one line each.

    Args:
        max_count: How many commits to show (1-50).
    """
    if not 1 <= max_count <= 50:
        raise ToolInputError("max_count must be between 1 and 50.")
    proc = _git("log", f"-n{max_count}", "--date=short", "--pretty=format:%h %ad %s")
    if proc.returncode != 0:
        return "No commits yet."
    return proc.stdout.strip() or "No commits yet."
