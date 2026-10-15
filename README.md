# gecaro-mcp-file-server

A small **MCP file server** that lets AI agents (like Claude) read and edit files in **one safe folder** on my computer, over a public HTTPS link.

I built it for CS 3A/3B, Week 6 (Model Context Protocol), Midterms Pt 1. Two separate Claude chats used it to build and review a small to-do app, passing context to each other through handoff files.

**In one line:** Claude → HTTPS (ngrok) → Docker → this Python server → `workspace/` folder only.

---

## Contents

1. [What you need](#1-what-you-need)
2. [Get the code](#2-get-the-code)
3. [Install](#3-install)
4. [Run the tests](#4-run-the-tests)
5. [Run it on your computer](#5-run-it-on-your-computer)
6. [Check it with MCP Inspector](#6-check-it-with-mcp-inspector)
7. [Put it online (Docker + ngrok)](#7-put-it-online-docker--ngrok)
8. [Connect Claude](#8-connect-claude)
9. [The 9 tools](#9-the-9-tools)
10. [Security](#10-security)
11. [Handoff files and the 2-session demo](#11-handoff-files-and-the-2-session-demo)
12. [Project layout](#12-project-layout)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. What you need

- **Windows 10/11** (the steps use Command Prompt)
- **Python 3.13**
- **Git**
- **Node.js** (only for MCP Inspector, step 6)
- **Docker Desktop** (step 7)
- A free **ngrok** account (step 7)

> Use **Command Prompt**, not PowerShell. PowerShell may block the venv activate script.

---

## 2. Get the code

```
git clone https://github.com/gecarojeth-star/gecaro-mcp-file-server.git
cd gecaro-mcp-file-server
```

---

## 3. Install

```
py -3.13 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> **Why `mcp>=1.8,<2`?** Version 2 of the MCP SDK renamed `FastMCP`, which breaks this code. The pin keeps it on a version that works.

**Make your `.env` file** (it holds secrets and is never committed):

```
copy .env.example .env
```

Make a long random token:

```
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Open `.env` and paste it after `MCP_AUTH_TOKEN=`. The server refuses to start if the token is shorter than 24 characters.

---

## 4. Run the tests

```
python -m unittest -v
```

You should see **39 tests, all OK** (1 symlink test may be skipped on Windows, because making symlinks needs extra rights).

---

## 5. Run it on your computer

```
python -m server.main
```

The server now runs at `http://127.0.0.1:8000/mcp`.

On first start it:
- creates the `workspace/` folder (the only folder agents can touch),
- copies the 4 handoff files from `templates/` into it,
- makes `workspace/` a git repo (for the git tools).

Every tool call is logged to `logs/calls.jsonl`.

Stop it with `Ctrl+C`.

---

## 6. Check it with MCP Inspector

With the server running (step 5), open a **second** Command Prompt:

```
npx @modelcontextprotocol/inspector
```

In the Inspector page that opens (these steps match Inspector v2.11):

1. Click **Add Servers** and add a server:
   - **Server ID:** `file-server`
   - **Transport:** `streamable-http`
   - **URL:** `http://127.0.0.1:8000/mcp`
2. On the `file-server` card, click **Settings**, open **Custom Headers**, and click **+ Add Header**:
   - Name: `Authorization`
   - Value: `Bearer <your MCP_AUTH_TOKEN>` (the word `Bearer`, a space, then your token)
3. Turn on the switch on the `file-server` card (not the demo cards), then open the **Tools** tab. You should see **Tools (9)**.
4. Click `read_file`, set **Path** to `../secret.txt`, and click **Execute Tool**. It must fail with **"path escapes the workspace root"**.

> Don't screenshot the Custom Headers box with your token in it.

---

## 7. Put it online (Docker + ngrok)

Docker runs two containers:
- **mcp**: the server
- **tunnel**: ngrok, which gives it a public HTTPS address

Both have `restart: unless-stopped`, so they come back after a crash, a restart or a reboot.

### 7.1 Get your ngrok details

From your ngrok dashboard, copy:
- your **authtoken**
- your free **static domain** (looks like `something.ngrok-free.dev`)

Put them in `.env`:

```
NGROK_AUTHTOKEN=your-ngrok-authtoken
NGROK_DOMAIN=your-domain.ngrok-free.dev
```

> Don't mix them up: `NGROK_AUTHTOKEN` is from ngrok, `MCP_AUTH_TOKEN` is the one you made in step 3.

### 7.2 Start it

Stop the local server from step 5 first (`Ctrl+C`), because both use port 8000.

```
docker compose up -d --build
docker compose ps
```

Wait until `mcp` says **(healthy)** and `tunnel` says **Up**.

### 7.3 Test the public link

```
python scripts/check_remote.py https://your-domain.ngrok-free.dev/mcp
```

It reads your token from `.env` and **never prints it**. It checks:
1. a request with no token is refused,
2. connect (initialize),
3. list the tools,
4. `list_files` works,
5. a sandbox escape is refused.

You should see **ALL CHECKS PASSED**.

### 7.4 Make it survive a reboot

In **Docker Desktop → Settings → General**, turn on **"Start Docker Desktop when you sign in"**.

> Don't run `docker compose down` before a reboot. With `unless-stopped`, stopped containers stay stopped.

### Useful commands

| What | Command |
|---|---|
| Status | `docker compose ps` |
| Server logs | `docker compose logs mcp --tail 20` |
| Tunnel logs | `docker compose logs tunnel --tail 20` |
| Restart both | `docker compose restart` |
| Stop everything | `docker compose down` |

---

## 8. Connect Claude

Claude's Free plan has no field for a custom header, so the token goes **inside the URL path** instead:

```
https://your-domain.ngrok-free.dev/<your MCP_AUTH_TOKEN>/mcp
```

1. In Claude, add a **custom connector**.
2. Paste the URL above.
3. Choose **no sign-in**.
4. Open a new chat, turn the connector on, and ask:
   > Use my file server connector to list the files in the workspace root.

You should see a `list_files` call and your workspace files.

> ⚠️ Treat this URL like a password. Anyone who has it can use your server. If it leaks, make a new `MCP_AUTH_TOKEN`, run `docker compose up -d --force-recreate mcp`, and re-add the connector.

---

## 9. The 9 tools

All paths are relative to `workspace/`.

| Tool | What it does |
|---|---|
| `list_files` | List a folder (optionally recursive) |
| `read_file` | Read a text file, or only some lines |
| `write_file` | Create or overwrite a file |
| `str_replace` | Replace **exactly one** match of a text in a file |
| `delete_file` | Delete one file. **Needs `confirm=true`**. Can't delete handoff files or folders |
| `search_code` | Find a text in a folder or a single file |
| `git_status` | Show changed files |
| `git_commit` | Commit all workspace changes |
| `git_log` | Show recent commits |

Bad input returns a clear error (`isError`) that says what to do next, for example: *"Not deleted. Call delete_file again with confirm=true."*

There is **no tool that runs code**, on purpose (see [docs/DECISIONS.md](docs/DECISIONS.md)).

---

## 10. Security

| Risk | What stops it |
|---|---|
| Reading files outside the folder | Sandbox rejects `..`, absolute paths, drive letters, symlink escapes and null bytes |
| Breaking the workspace git history | `.git` can't be read or written |
| Strangers using the public URL | Secret token required (URL path or `Bearer` header), compared in constant time; everything else gets 401 |
| A weak or missing token | Server won't start with a token under 24 characters, or with no token on a public host |
| The token showing up in logs | Web access log is turned off |
| An agent deleting important files | `delete_file` needs `confirm=true`, and handoff files are protected |
| Not knowing what an agent did | Every call is logged to `logs/calls.jsonl` |
| Secrets in GitHub | `.env` is git-ignored; Docker gives the ngrok token only to the tunnel container |

The container also runs as a normal user, not root, and the server port is published only to `127.0.0.1`.

**Known tradeoffs:** a token in the URL is weaker than a header, the free ngrok plan is used, and my laptop must stay on. See the report for details.

---

## 11. Handoff files and the 2-session demo

Agents in separate chats don't share memory, so they share **4 files** in `workspace/`:

| File | Purpose |
|---|---|
| `PROJECT_STATE.md` | Where the project is now. Read first, rewrite before stopping |
| `PLAN_LOG.md` | Append-only: each session's plan and result |
| `CHECKPOINTS.md` | Milestones reached |
| `DECISIONS.md` | Choices made and why |

The server tells every agent: read `PROJECT_STATE.md` first, read before editing, and update the 4 files and `git_commit` before stopping.

### The demo

| Session | Role | Job | Logged calls |
|---|---|---|---|
| Chat 1 | **Agent A, Builder** | Wrote a Python to-do CLI and its tests | 10 |
| Chat 2 | **Agent B, Reviewer** | Found and fixed crash bugs, added 7 tests | 12 |

Agent B started with **no chat history**. It learned everything from the handoff files.

Honest notes:
- Each agent reported 1 more call than the server logged (most likely Claude's own "load tools" step, which never reaches the server).
- The Reviewer had 1 failed `search_code` call (it gave a file to a folder-only tool). Its next call took a different approach, not a retry. I then changed `search_code` to accept files.
- No agent could run the to-do tests, because there's no code-execution tool.

**Evidence** is in `evidence/`: the call log, an efficiency summary, the final handoff files, the demo code, the workspace git log, the Docker check results (`docker_remote_check.txt`, `docker_restart_check.txt`, `docker_reboot_check.txt`), and 17 numbered screenshots in `evidence/screenshots/` (secrets covered).

---

## 12. Project layout

```
server/
  main.py        start the server, add auth
  config.py      settings from environment / .env
  sandbox.py     keeps every path inside workspace/
  auth.py        token check (URL path or Bearer header)
  audit.py       logs every call to logs/calls.jsonl
  errors.py      clear error messages
  bootstrap.py   first-start setup
  tools/         files.py, search.py, gitlite.py
templates/       the 4 handoff file templates
tests/           unittest tests
scripts/
  check_remote.py      tests a running server
  collect_evidence.py  builds evidence/ from the log
docker/healthcheck.py
Dockerfile, docker-compose.yml, .dockerignore
evidence/        grading evidence
docs/            DECISIONS.md
.env.example     copy to .env
```

`workspace/`, `logs/` and `.env` are created on your computer and are git-ignored.

---

## 13. Troubleshooting

**"Port 8000 is already in use"**
Something else is using it, usually the Docker `mcp` container. Run `docker compose down`, or stop the other `python -m server.main` window.

**I changed `.env` but nothing changed**
Containers read `.env` only when they are **created**, not on restart. Run:
```
docker compose up -d --force-recreate
```

**Tunnel keeps restarting with `ERR_NGROK_105`**
Your ngrok authtoken is wrong. Check that `NGROK_AUTHTOKEN` in `.env` holds the token from the ngrok dashboard (not your `MCP_AUTH_TOKEN`), then run:
```
docker compose up -d --force-recreate tunnel
```

**"Flag --host-header has been deprecated"**
Only a warning. It still works.

**Server says the token is too short**
Make a new one with the command in step 3.

**Venv won't activate**
Use Command Prompt instead of PowerShell.

**`check_remote.py` fails right after a reboot**
The tunnel can start a few seconds before the server is ready. Wait 30 seconds and try again.
