# CHECKPOINTS
_Append a line each time a milestone is reached and committed._

Format:
- YYYY-MM-DD | commit hash | milestone reached | how to verify
- 2026-10-15 | (the commit adding todo/) | To-do CLI and unittest tests written | `cd todo && python -m unittest -v`; `python todo.py add "x"`, `list`, `done 1`
- 2026-10-15 | (Reviewer hardening commit) | Robust loading (empty/corrupt/wrong-shape file) and atomic saves, +7 tests (UNVERIFIED, not run) | `cd todo && python -m unittest -v` should show 15 passing tests; `echo garbage > tasks.json; python todo.py list` should print an Error and exit 1
