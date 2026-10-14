"""Entry point. Run with:  python -m server.main"""
from mcp.server.fastmcp import FastMCP

from . import config
from .bootstrap import bootstrap
from .tools import ALL_TOOLS

INSTRUCTIONS = (
    "Shared workspace for multiple agent sessions. At the start of every session, "
    "read PROJECT_STATE.md, then the end of PLAN_LOG.md. Read a file before editing it. "
    "Prefer search_code and line ranges over reading whole files. Before you stop, "
    "update PROJECT_STATE.md, append to PLAN_LOG.md and CHECKPOINTS.md, and git_commit."
)


def build_server() -> FastMCP:
    bootstrap()
    mcp = FastMCP("file-server", instructions=INSTRUCTIONS, host=config.HOST, port=config.PORT)
    for tool in ALL_TOOLS:
        mcp.tool()(tool)
    return mcp


def main() -> None:
    build_server().run(transport=config.TRANSPORT)


if __name__ == "__main__":
    main()
