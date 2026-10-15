"""Smoke-test a running MCP server over HTTP(S) and print a transcript.

Usage:  python scripts/check_remote.py https://your-domain.ngrok-free.dev/mcp
        python scripts/check_remote.py http://127.0.0.1:8000/mcp --out evidence/remote_check.txt

The token is read from MCP_AUTH_TOKEN (.env) or --token. It is never printed.
Checks: refused without token -> initialize -> tools/list -> list_files -> sandbox escape refused.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import config  # noqa: E402  (loads .env, no MCP SDK needed)

LINES: list[str] = []


def say(text: str = "") -> None:
    print(text)
    LINES.append(text)


def post(url, payload, token=None, session=None, proto=None):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "ngrok-skip-browser-warning": "1",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if session:
        headers["Mcp-Session-Id"] = session
    if proto:
        headers["MCP-Protocol-Version"] = proto
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.headers, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read().decode("utf-8", "replace")


def parse(body: str, content_type: str):
    """Return the JSON-RPC message from a JSON or SSE (text/event-stream) body."""
    if not body.strip():
        return None
    if "text/event-stream" in (content_type or ""):
        for line in body.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        return None
    return json.loads(body)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--token", default=config.AUTH_TOKEN)
    ap.add_argument("--out", help="also save the transcript to this file")
    args = ap.parse_args()
    ok = True

    def check(label, passed, detail=""):
        nonlocal ok
        ok = ok and passed
        say(f"[{'PASS' if passed else 'FAIL'}] {label}" + (f" - {detail}" if detail else ""))

    say(f"Target: {args.url}")
    if not args.token:
        say("No token found (set MCP_AUTH_TOKEN in .env or pass --token).")
        return 2

    status, _, _ = post(args.url, {"jsonrpc": "2.0", "id": 0, "method": "ping"})
    check("Request WITHOUT token is refused", status == 401, f"HTTP {status}")

    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "check_remote", "version": "1.0"}}}
    status, hdrs, body = post(args.url, init, token=args.token)
    msg = parse(body, hdrs.get("content-type")) if status == 200 else None
    result = (msg or {}).get("result", {})
    check("initialize with token", status == 200 and bool(result),
          f"HTTP {status}, server={result.get('serverInfo', {}).get('name')}")
    if status != 200 or not result:
        say(body[:300])
        return 1
    session = hdrs.get("mcp-session-id")
    proto = result.get("protocolVersion")

    status, _, _ = post(args.url, {"jsonrpc": "2.0", "method": "notifications/initialized"},
                        token=args.token, session=session, proto=proto)
    check("notifications/initialized accepted", status in (200, 202), f"HTTP {status}")

    status, hdrs, body = post(args.url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                              token=args.token, session=session, proto=proto)
    tools = [t["name"] for t in (parse(body, hdrs.get("content-type")) or {}).get("result", {}).get("tools", [])]
    check("tools/list", len(tools) >= 8, f"{len(tools)} tools: {', '.join(tools)}")

    def call(i, name, arguments):
        s, h, b = post(args.url, {"jsonrpc": "2.0", "id": i, "method": "tools/call",
                                  "params": {"name": name, "arguments": arguments}},
                       token=args.token, session=session, proto=proto)
        return (parse(b, h.get("content-type")) or {}).get("result", {})

    res = call(3, "list_files", {})
    text = "".join(c.get("text", "") for c in res.get("content", []))
    check("list_files returns the workspace", not res.get("isError") and "PROJECT_STATE.md" in text,
          text.replace("\n", " | ")[:120])

    res = call(4, "read_file", {"path": "../secret.txt"})
    text = "".join(c.get("text", "") for c in res.get("content", []))
    check("Sandbox escape '../secret.txt' is refused", bool(res.get("isError")) and "escapes" in text, text[:100])

    say("")
    say("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text("\n".join(LINES) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
