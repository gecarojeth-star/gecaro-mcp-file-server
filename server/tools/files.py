"""File tools: list, read, write, str_replace, delete. All paths go through the sandbox."""
import os

from .. import config
from ..audit import audited
from ..errors import ToolInputError
from ..sandbox import HANDOFF_FILES, rel_posix, resolve_path

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}


# ---------- helpers ----------
def _looks_binary(path) -> bool:
    with open(path, "rb") as f:
        return b"\x00" in f.read(8192)


def _read_text(path, *, strict: bool = False) -> str:
    rel = rel_posix(path)
    if not path.exists():
        raise ToolInputError(f"File not found: {rel}. Use list_files to see what exists.")
    if path.is_dir():
        raise ToolInputError(f"{rel} is a directory. Use list_files to see its contents.")
    if _looks_binary(path):
        raise ToolInputError(f"{rel} looks like a binary file and cannot be read as text.")
    try:
        with open(path, "r", encoding="utf-8", errors="strict" if strict else "replace", newline="") as f:
            return f.read()
    except UnicodeDecodeError:
        raise ToolInputError(f"{rel} is not valid UTF-8 text.") from None


def _atomic_write(path, content: str) -> None:
    """Write to a temp file then swap it in, so a failed write never leaves a half file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except (FileExistsError, NotADirectoryError):
        raise ToolInputError("A parent of this path is an existing file, not a folder.") from None
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    os.replace(tmp, path)


# ---------- tools ----------
@audited
def list_files(path: str = ".", recursive: bool = False) -> str:
    """List files and folders inside a workspace folder.

    Use this first to see what exists before reading or writing. Folders end with '/'.
    Results are capped, so for big trees list one subfolder at a time.

    Args:
        path: Folder relative to the workspace root. Default is the root.
        recursive: If true, also list everything below the folder.
    """
    base = resolve_path(path)
    if not base.exists():
        raise ToolInputError(f"Folder not found: {rel_posix(base)}")
    if not base.is_dir():
        raise ToolInputError(f"{rel_posix(base)} is a file. Use read_file to read it.")

    entries: list[str] = []
    truncated = False
    if recursive:
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for d in dirnames:
                entries.append(rel_posix(base.__class__(dirpath) / d) + "/")
            for name in sorted(filenames):
                full = base.__class__(dirpath) / name
                entries.append(f"{rel_posix(full)} ({full.stat().st_size} bytes)")
            if len(entries) >= config.MAX_LIST_ENTRIES:
                truncated = True
                break
    else:
        for child in sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.name in SKIP_DIRS:
                continue
            if child.is_dir():
                entries.append(child.name + "/")
            else:
                entries.append(f"{child.name} ({child.stat().st_size} bytes)")

    if len(entries) > config.MAX_LIST_ENTRIES:
        entries, truncated = entries[: config.MAX_LIST_ENTRIES], True
    if not entries:
        return f"{rel_posix(base)} is empty."
    out = "\n".join(entries)
    if truncated:
        out += f"\n[listing truncated at {config.MAX_LIST_ENTRIES} entries; list a subfolder]"
    return out


@audited
def read_file(path: str, start_line: int = 1, end_line: int | None = None) -> str:
    """Read a text file, optionally only a range of lines.

    Always read a file before editing it. For large files read a range, or use
    search_code to find the right lines first. Output is capped at 20,000 characters.

    Args:
        path: File relative to the workspace root.
        start_line: First line to return (1-based).
        end_line: Last line to return (inclusive). Omit to read to the end.
    """
    target = resolve_path(path)
    text = _read_text(target)
    lines = text.splitlines(keepends=True)
    total = len(lines)
    if total == 0:
        return "[empty file]"
    if start_line < 1:
        raise ToolInputError("start_line must be 1 or greater.")
    if end_line is not None and end_line < start_line:
        raise ToolInputError("end_line must be greater than or equal to start_line.")
    if start_line > total:
        raise ToolInputError(f"start_line {start_line} is past the end; the file has {total} lines.")

    out = "".join(lines[start_line - 1 : end_line])
    if len(out) > config.MAX_READ_CHARS:
        return (
            out[: config.MAX_READ_CHARS]
            + f"\n[truncated at {config.MAX_READ_CHARS} characters; file has {total} lines. "
            "Read a narrower range with start_line/end_line.]"
        )
    if start_line != 1 or end_line is not None:
        shown_end = min(end_line, total) if end_line else total
        out += f"\n[showing lines {start_line}-{shown_end} of {total}]"
    return out


@audited
def write_file(path: str, content: str) -> str:
    """Create a file, or fully overwrite an existing one. Parent folders are created.

    Use str_replace for small edits to an existing file, so you do not resend the
    whole file. Content is limited to 200,000 bytes.

    Args:
        path: File relative to the workspace root.
        content: The complete new text of the file.
    """
    target = resolve_path(path)
    if target == config.WORKSPACE_ROOT or target.is_dir():
        raise ToolInputError(f"{rel_posix(target)} is a folder, not a file.")
    size = len(content.encode("utf-8"))
    if size > config.MAX_WRITE_BYTES:
        raise ToolInputError(
            f"Content is {size} bytes; the limit is {config.MAX_WRITE_BYTES}. Split it into several files."
        )
    existed = target.exists()
    _atomic_write(target, content)
    return f"{'Overwrote' if existed else 'Created'} {rel_posix(target)} ({size} bytes)."


@audited
def str_replace(path: str, old_str: str, new_str: str) -> str:
    """Replace exactly one occurrence of old_str with new_str in a file.

    Fails if old_str is missing or appears more than once, so widen old_str with
    surrounding text until it is unique. Read the file first.

    Args:
        path: File relative to the workspace root.
        old_str: Exact text to replace. Must appear exactly once.
        new_str: Replacement text. May be empty to delete old_str.
    """
    target = resolve_path(path)
    if not old_str:
        raise ToolInputError("old_str must not be empty.")
    text = _read_text(target, strict=True)
    count = text.count(old_str)
    if count == 0:
        raise ToolInputError("old_str was not found. Read the file again and copy the text exactly.")
    if count > 1:
        raise ToolInputError(
            f"old_str appears {count} times. Add surrounding text so it matches exactly once."
        )
    line = text[: text.index(old_str)].count("\n") + 1
    _atomic_write(target, text.replace(old_str, new_str, 1))
    return f"Replaced 1 occurrence in {rel_posix(target)} (line {line})."


@audited
def delete_file(path: str, confirm: bool = False) -> str:
    """Delete one file. Destructive, so it needs confirm=true.

    Only files can be deleted, not folders. The handoff files (PROJECT_STATE.md,
    PLAN_LOG.md, CHECKPOINTS.md, DECISIONS.md) cannot be deleted.

    Args:
        path: File relative to the workspace root.
        confirm: Must be true. The first call without it returns a reminder.
    """
    target = resolve_path(path)
    rel = rel_posix(target)
    if not target.exists():
        raise ToolInputError(f"File not found: {rel}.")
    if target.is_dir():
        raise ToolInputError(f"{rel} is a folder. Only single files can be deleted.")
    if target.parent == config.WORKSPACE_ROOT and target.name in HANDOFF_FILES:
        raise ToolInputError(f"{target.name} is a handoff file and cannot be deleted.")
    if confirm is not True:
        raise ToolInputError(f"Not deleted. Call delete_file again with confirm=true to delete {rel}.")
    target.unlink()
    return f"Deleted {rel}."
