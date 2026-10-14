"""The tool registry. main.py registers everything in ALL_TOOLS with the MCP server."""
from .files import delete_file, list_files, read_file, str_replace, write_file
from .gitlite import git_commit, git_log, git_status
from .search import search_code

ALL_TOOLS = [
    list_files, read_file, write_file, str_replace, delete_file,
    search_code, git_status, git_commit, git_log,
]
