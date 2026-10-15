"""search_code: find text across the workspace without reading whole files."""
import os
from pathlib import Path

from .. import config
from ..audit import audited
from ..errors import ToolInputError
from ..sandbox import rel_posix, resolve_path

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
MAX_FILE_BYTES = 1_000_000


def _iter_files(base: Path):
    """Yield the file itself, or every file below a folder (skipping noise folders)."""
    if base.is_file():
        yield base
        return
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            yield Path(dirpath) / name


@audited
def search_code(query: str, path: str = ".", case_sensitive: bool = False, max_results: int = 30) -> str:
    """Search for a text snippet in a folder or a single file and return matching lines.

    Use this to find the right file and line before read_file, instead of reading
    whole files. Matches plain text (not regex). Skips binary and very large files.

    Args:
        query: Text to look for.
        path: Folder OR single file to search, relative to the workspace root. Default is the root.
        case_sensitive: Default false.
        max_results: Maximum matching lines to return (1-50).
    """
    if not query:
        raise ToolInputError("query must not be empty.")
    if not 1 <= max_results <= config.MAX_SEARCH_RESULTS:
        raise ToolInputError(f"max_results must be between 1 and {config.MAX_SEARCH_RESULTS}.")
    base = resolve_path(path)
    if not base.exists():
        raise ToolInputError(f"Path not found: {rel_posix(base)}. Use list_files to see what exists.")

    needle = query if case_sensitive else query.lower()
    hits: list[str] = []
    for full in _iter_files(base):
        try:
            if full.stat().st_size > MAX_FILE_BYTES:
                continue
            with open(full, "rb") as fb:
                if b"\x00" in fb.read(8192):
                    continue
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                for lineno, line in enumerate(f, 1):
                    hay = line if case_sensitive else line.lower()
                    if needle in hay:
                        hits.append(f"{rel_posix(full)}:{lineno}: {line.strip()[:200]}")
                        if len(hits) >= max_results:
                            return "\n".join(hits) + f"\n[stopped at {max_results} results; narrow the query or path]"
        except OSError:
            continue
    return "\n".join(hits) if hits else f"No matches for '{query}'."
