# Decisions

Key choices for this project, and why. Newest at the bottom.

Each entry: **Decision** · **Why** · **Tradeoff**

---

## 1. Python + official MCP SDK (FastMCP), pinned to `mcp>=1.8,<2`

- **Decision:** Build the server with FastMCP from the official Python SDK, and pin the version below 2.
- **Why:** FastMCP turns plain Python functions into MCP tools, using their type hints for the schema and their docstrings for the description. Version 2 of the SDK renamed `FastMCP` and broke the code, so the pin keeps installs reproducible.
- **Tradeoff:** I won't get new 2.x features until I migrate on purpose.

## 2. Streamable HTTP transport

- **Decision:** Serve MCP over Streamable HTTP instead of stdio.
- **Why:** Claude's custom connectors need a remote HTTPS URL. stdio only works for a local app on the same computer.
- **Tradeoff:** The server must be online and needs authentication, while stdio needs neither.

## 3. Secret token in the URL path (plus Bearer header)

- **Decision:** Accept the token as `https://<domain>/<token>/mcp`, or as `Authorization: Bearer <token>`.
- **Why:** The Claude Free plan connector dialog has no custom-header field, and its auth can't be edited after adding. The path secret is the only option that works there. The Bearer header is kept for Inspector and scripts.
- **Safeguards:** constant-time comparison, a minimum of 24 characters, the server refuses to start with no token on a public host, and the web access log is off so the URL never reaches logs.
- **Tradeoff:** A secret in a URL is weaker than a header, because it can leak through screenshots, browser history or copied links. OAuth would be better on a paid plan.

## 4. ngrok with a free static domain

- **Decision:** Expose the server through ngrok, using the free static dev domain.
- **Why:** It gives free HTTPS without router setup, and the static domain means the connector URL never changes after a restart.
- **Tradeoff:** It depends on ngrok's free plan limits, and my laptop must stay on.

## 5. Docker Compose as the process manager (NSSM as fallback)

- **Decision:** Run the server and the tunnel as two containers with `restart: unless-stopped`, and turn on Docker Desktop's "Start when you sign in."
- **Why:** One command starts everything, crashes restart on their own, and it survived `docker compose restart` and a full Windows reboot (see `evidence/docker_*_check.txt`). Only the tunnel container gets the ngrok token, the server runs as a non-root user, and port 8000 is published only to `127.0.0.1`.
- **Fallback:** If Docker had failed, I would have used NSSM (a Windows service wrapper). It wasn't needed.
- **Tradeoff:** Docker Desktop is heavy, and containers read `.env` only when created, so changes need `--force-recreate`.

## 6. No code-execution tool

- **Decision:** No tool runs shell commands or Python.
- **Why:** Over a public URL, a run-code tool would turn any token leak into full control of my laptop. A file-only server keeps the damage inside `workspace/`.
- **Tradeoff:** Agents can't run tests. In the demo, both agents wrote tests but couldn't run them (noted honestly in `PROJECT_STATE.md`).

## 7. Gate destructive tools

- **Decision:** `delete_file` needs `confirm=true`, deletes only single files (not folders), and can't delete the 4 handoff files. `.git` is blocked by the sandbox. Every call is logged to `logs/calls.jsonl`.
- **Why:** An agent mistake shouldn't wipe the project state or the workspace history.
- **Tradeoff:** One extra call when a delete is really wanted.

## 8. Sandbox: one workspace root

- **Decision:** Every path is resolved inside `workspace/`. `..`, absolute paths, drive letters, null bytes and symlinks that point outside are rejected.
- **Why:** This is the main security boundary of a file server.
- **Tradeoff:** Agents can't see any other folder, by design.

## 9. Small, single-purpose tools

- **Decision:** 9 tools, each doing one job, with limits: reads capped at 20,000 characters, writes at 200 KB, `str_replace` must match exactly once, and search returns at most 50 results.
- **Why:** Small outputs and clear errors (`isError`) help agents use fewer, more purposeful calls.
- **Change made:** After the Reviewer's failed `search_code` call (it gave a file path to a folder-only tool), I changed `search_code` to accept a single file too.
