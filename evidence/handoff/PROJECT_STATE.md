# PROJECT_STATE
_Read this FIRST every session. Rewrite it before you stop._

## Goal
Small Python CLI to-do app in todo/: `add "text"`, `list`, `done ID`, stored in todo/tasks.json, with unittest tests.

## Current status
- todo/todo.py: functions + argparse CLI; tasks stored as {id, text, done}; IDs increment from max existing ID.
- Reviewer (Agent B) hardened it: empty tasks.json is treated as no tasks; corrupt JSON or wrong-shaped data raises ValueError (CLI prints "Error: ..." and exits 1 instead of a traceback); save_tasks writes to tasks.json.tmp then os.replace (atomic).
- todo/test_todo.py: 15 tests (8 original + 7 new: empty file, corrupt JSON, wrong shape, CLI corrupt file, no leftover temp file, ID not reused after gap, done twice idempotent).
- Committed. NO agent has been able to execute the tests (file-server tools only).

## Next step
Run `cd todo && python -m unittest -v` and fix any failures. This needs an agent or person with code execution.

## Open problems
- Tests unverified (never run, by Builder or Reviewer).
- tasks.json is only created on the first `add`.
- Not handled (deliberately): concurrent writers (no file locking); non-UTF-8 files; deleting tasks (no `delete` command).
- Validation requires each task to have int `id`, `text`, `done`; a hand-edited file with other shapes is rejected as an error.
