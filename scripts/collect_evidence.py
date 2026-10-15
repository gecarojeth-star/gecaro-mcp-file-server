"""Gather grading evidence into evidence/ and summarize agent efficiency from the call log.

Usage:  python scripts/collect_evidence.py
        python scripts/collect_evidence.py --since 2026-10-15T04:30:00 --gap 10

Reads   logs/calls.jsonl   (every tool call: name, short args, ok/error, duration)
Writes  evidence/efficiency_summary.md, evidence/calls.jsonl, evidence/handoff/*.md,
        evidence/workspace_git_log.txt, evidence/demo_output/*.py

Safety: the repo is public, so nothing containing MCP_AUTH_TOKEN is ever written.
Times in the log are UTC; --since is read as UTC too.
"""
import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import config  # noqa: E402
from server.sandbox import HANDOFF_FILES  # noqa: E402

OUT_DIR = config.BASE_DIR / "evidence"


# ---------- log analysis ----------
def parse_ts(value: str) -> datetime:
    ts = datetime.fromisoformat(value)
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def load_calls(path: Path, since: datetime | None = None) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            row["_ts"] = parse_ts(row["ts"])
        except (ValueError, KeyError):
            continue
        if since is None or row["_ts"] >= since:
            rows.append(row)
    return sorted(rows, key=lambda r: r["_ts"])


def split_sessions(rows: list[dict], gap_minutes: float) -> list[list[dict]]:
    """A new session starts whenever there is a quiet gap longer than gap_minutes."""
    sessions: list[list[dict]] = []
    for row in rows:
        if sessions and row["_ts"] - sessions[-1][-1]["_ts"] <= timedelta(minutes=gap_minutes):
            sessions[-1].append(row)
        else:
            sessions.append([row])
    return sessions


def summarize(session: list[dict]) -> dict:
    tools = Counter(r["tool"] for r in session)
    errors = [r for r in session if not r.get("ok", True)]
    whole_reads = sum(
        1 for r in session
        if r["tool"] == "read_file"
        and r.get("args", {}).get("start_line") in (None, 1)
        and r.get("args", {}).get("end_line") is None
    )
    keys = [(r["tool"], json.dumps(r.get("args", {}), sort_keys=True)) for r in session]
    return {
        "start": session[0]["_ts"], "end": session[-1]["_ts"],
        "calls": len(session), "tools": tools, "errors": errors,
        "whole_reads": whole_reads, "repeated": len(keys) - len(set(keys)),
        "ms": sum(r.get("ms", 0) for r in session),
    }


def build_report(sessions: list[list[dict]], gap: float) -> str:
    out = ["# Agent efficiency summary", "",
           f"Generated from `logs/calls.jsonl`. Sessions are split by quiet gaps over {gap:g} minutes. "
           "Times are UTC.", "",
           "| # | Start | Calls | Errors | Whole-file reads | Repeated identical calls | Server time (ms) |",
           "|---|-------|-------|--------|------------------|--------------------------|------------------|"]
    summaries = [summarize(s) for s in sessions]
    for i, sm in enumerate(summaries, 1):
        out.append(f"| {i} | {sm['start']:%Y-%m-%d %H:%M} | {sm['calls']} | {len(sm['errors'])} | "
                   f"{sm['whole_reads']} | {sm['repeated']} | {sm['ms']:.0f} |")
    for i, sm in enumerate(summaries, 1):
        out += ["", f"## Session {i}  ({sm['start']:%Y-%m-%d %H:%M} to {sm['end']:%H:%M} UTC)", "",
                "Calls per tool: " + ", ".join(f"`{t}` x{n}" for t, n in sm["tools"].most_common()), ""]
        if sm["errors"]:
            out.append("Failed calls (what the agent had to recover from):")
            for r in sm["errors"]:
                out.append(f"- `{r['tool']}`: {str(r.get('error', ''))[:160]}")
        else:
            out.append("No failed calls.")
    out += ["", "## How to read this", "",
            "- **Calls**: fewer, purposeful calls score higher on Agent efficiency.",
            "- **Whole-file reads**: `read_file` without a line range. Fine for small handoff files, wasteful for big ones.",
            "- **Repeated identical calls**: same tool and arguments twice in one session (wasted work).",
            "- **Failed calls**: each failure should be followed by a changed approach, not a blind retry."]
    return "\n".join(out) + "\n"


# ---------- safe file writing ----------
class SecretFound(Exception):
    pass


def check_no_secret(text: str, label: str) -> None:
    token = config.AUTH_TOKEN
    if token and token in text:
        raise SecretFound(f"{label} contains MCP_AUTH_TOKEN; refusing to copy it into a public repo.")


def safe_write(dest: Path, text: str, label: str) -> bool:
    try:
        check_no_secret(text, label)
    except SecretFound as exc:
        print(f"SKIPPED: {exc}")
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    try:
        shown = dest.relative_to(config.BASE_DIR)
    except ValueError:
        shown = dest
    print(f"wrote   {shown}")
    return True


def collect_files(out_dir: Path) -> None:
    root = config.WORKSPACE_ROOT
    for name in sorted(HANDOFF_FILES):
        src = root / name
        if src.exists():
            safe_write(out_dir / "handoff" / name, src.read_text(encoding="utf-8"), name)
    demo = root / "todo"
    if demo.is_dir():
        for src in sorted(demo.glob("*.py")):
            safe_write(out_dir / "demo_output" / src.name, src.read_text(encoding="utf-8"), f"todo/{src.name}")
    if (root / ".git").exists():
        proc = subprocess.run(["git", "log", "--stat", "--date=iso"], cwd=root,
                              capture_output=True, text=True, timeout=config.GIT_TIMEOUT)
        if proc.returncode == 0:
            safe_write(out_dir / "workspace_git_log.txt", proc.stdout, "git log")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="only include calls at/after this UTC time, e.g. 2026-10-15T04:30:00")
    ap.add_argument("--gap", type=float, default=10, help="minutes of quiet that start a new session")
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()
    out_dir = Path(args.out)

    since = parse_ts(args.since) if args.since else None
    rows = load_calls(config.LOG_PATH, since)
    if not rows:
        print(f"No calls found in {config.LOG_PATH}. Run the server and use the tools first.")
        return 1
    sessions = split_sessions(rows, args.gap)
    report = build_report(sessions, args.gap)
    print(report)
    safe_write(out_dir / "efficiency_summary.md", report, "summary")
    raw = "\n".join(json.dumps({k: v for k, v in r.items() if k != "_ts"}, ensure_ascii=False) for r in rows)
    safe_write(out_dir / "calls.jsonl", raw + "\n", "calls log")
    collect_files(out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
