# Agent efficiency summary

Generated from `logs/calls.jsonl`. Sessions are split by quiet gaps over 1 minutes. Times are UTC.

| # | Start | Calls | Errors | Whole-file reads | Repeated identical calls | Server time (ms) |
|---|-------|-------|--------|------------------|--------------------------|------------------|
| 1 | 2026-10-14 19:46 | 2 | 1 | 1 | 0 | 4 |
| 2 | 2026-10-14 20:25 | 2 | 1 | 1 | 0 | 3 |
| 3 | 2026-10-15 04:26 | 4 | 2 | 2 | 2 | 6 |
| 4 | 2026-10-15 04:51 | 2 | 0 | 1 | 0 | 21 |
| 5 | 2026-10-15 04:58 | 10 | 0 | 3 | 0 | 284 |
| 6 | 2026-10-15 05:00 | 12 | 1 | 5 | 0 | 224 |

## Session 1  (2026-10-14 19:46 to 19:46 UTC)

Calls per tool: `list_files` x1, `read_file` x1

Failed calls (what the agent had to recover from):
- `read_file`: path escapes the workspace root

## Session 2  (2026-10-14 20:25 to 20:25 UTC)

Calls per tool: `list_files` x1, `read_file` x1

Failed calls (what the agent had to recover from):
- `read_file`: path escapes the workspace root

## Session 3  (2026-10-15 04:26 to 04:27 UTC)

Calls per tool: `list_files` x2, `read_file` x2

Failed calls (what the agent had to recover from):
- `read_file`: path escapes the workspace root
- `read_file`: path escapes the workspace root

## Session 4  (2026-10-15 04:51 to 04:51 UTC)

Calls per tool: `list_files` x1, `read_file` x1

No failed calls.

## Session 5  (2026-10-15 04:58 to 04:59 UTC)

Calls per tool: `read_file` x3, `str_replace` x3, `write_file` x3, `git_commit` x1

No failed calls.

## Session 6  (2026-10-15 05:00 to 05:01 UTC)

Calls per tool: `read_file` x5, `str_replace` x4, `search_code` x1, `write_file` x1, `git_commit` x1

Failed calls (what the agent had to recover from):
- `search_code`: Folder not found: PLAN_LOG.md

## How to read this

- **Calls**: fewer, purposeful calls score higher on Agent efficiency.
- **Whole-file reads**: `read_file` without a line range. Fine for small handoff files, wasteful for big ones.
- **Repeated identical calls**: same tool and arguments twice in one session (wasted work).
- **Failed calls**: each failure should be followed by a changed approach, not a blind retry.
