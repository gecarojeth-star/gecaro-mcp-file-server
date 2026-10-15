import json
import shutil
import tempfile
import unittest
from pathlib import Path

from server import config
from server.errors import ToolInputError
from server.tools import (delete_file, git_commit, git_log, git_status, list_files,
                          read_file, search_code, str_replace, write_file)
from server.tools import gitlite


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self._old = (config.WORKSPACE_ROOT, config.LOG_PATH)
        config.WORKSPACE_ROOT = self.root
        config.LOG_PATH = self.root.parent / (self.root.name + "-calls.jsonl")

    def tearDown(self):
        if config.LOG_PATH.exists():
            config.LOG_PATH.unlink()
        config.WORKSPACE_ROOT, config.LOG_PATH = self._old
        self.tmp.cleanup()

    # --- write / read ---
    def test_write_then_read_roundtrip(self):
        self.assertIn("Created", write_file("notes/a.txt", "one\ntwo\nthree\n"))
        self.assertEqual(read_file("notes/a.txt"), "one\ntwo\nthree\n")
        self.assertIn("Overwrote", write_file("notes/a.txt", "x"))

    def test_read_line_range_and_errors(self):
        write_file("a.txt", "1\n2\n3\n4\n")
        out = read_file("a.txt", start_line=2, end_line=3)
        self.assertTrue(out.startswith("2\n3\n"))
        self.assertIn("lines 2-3 of 4", out)
        with self.assertRaises(ToolInputError):
            read_file("a.txt", start_line=99)
        with self.assertRaises(ToolInputError):
            read_file("missing.txt")

    def test_read_is_capped(self):
        write_file("big.txt", "a" * (config.MAX_READ_CHARS + 500))
        self.assertIn("truncated", read_file("big.txt"))

    def test_write_size_limit(self):
        with self.assertRaises(ToolInputError):
            write_file("huge.txt", "a" * (config.MAX_WRITE_BYTES + 1))

    def test_binary_file_is_refused(self):
        (self.root / "b.bin").write_bytes(b"\x00\x01\x02")
        with self.assertRaises(ToolInputError):
            read_file("b.bin")

    # --- str_replace ---
    def test_str_replace_unique_missing_multiple(self):
        write_file("a.txt", "hello world\nhello again\n")
        with self.assertRaises(ToolInputError) as ctx:
            str_replace("a.txt", "hello", "bye")
        self.assertIn("2 times", str(ctx.exception))
        with self.assertRaises(ToolInputError):
            str_replace("a.txt", "nope", "x")
        self.assertIn("line 2", str_replace("a.txt", "hello again", "bye again"))
        self.assertEqual(read_file("a.txt"), "hello world\nbye again\n")

    def test_line_endings_are_preserved(self):
        (self.root / "crlf.txt").write_bytes(b"a\r\nb\r\n")
        str_replace("crlf.txt", "b", "c")
        self.assertEqual((self.root / "crlf.txt").read_bytes(), b"a\r\nc\r\n")

    # --- delete ---
    def test_delete_is_gated(self):
        write_file("tmp.txt", "x")
        with self.assertRaises(ToolInputError):
            delete_file("tmp.txt")
        self.assertTrue((self.root / "tmp.txt").exists())
        self.assertIn("Deleted", delete_file("tmp.txt", confirm=True))
        self.assertFalse((self.root / "tmp.txt").exists())

    def test_handoff_files_and_folders_cannot_be_deleted(self):
        write_file("PROJECT_STATE.md", "x")
        with self.assertRaises(ToolInputError):
            delete_file("PROJECT_STATE.md", confirm=True)
        (self.root / "dir").mkdir()
        with self.assertRaises(ToolInputError):
            delete_file("dir", confirm=True)

    def test_tools_reject_escapes(self):
        for call in (lambda: read_file("../x"), lambda: write_file("../x", "a"),
                     lambda: delete_file("../x", confirm=True), lambda: list_files(".."),
                     lambda: search_code("a", path="..")):
            with self.assertRaises(ToolInputError):
                call()

    # --- list / search ---
    def test_list_and_search(self):
        write_file("src/app.py", "def main():\n    return 'Hello'\n")
        write_file("README.md", "# Title\n")
        listing = list_files()
        self.assertIn("src/", listing)
        self.assertIn("README.md", listing)
        self.assertIn("src/app.py", list_files(recursive=True))
        self.assertIn("src/app.py:2:", search_code("hello"))
        self.assertIn("No matches", search_code("zzz"))
        self.assertIn("No matches", search_code("hello", case_sensitive=True))

    def test_search_accepts_a_single_file_path(self):
        write_file("todo/todo.py", "def add_task():\n    pass\n")
        write_file("todo/other.py", "def add_task():\n    pass\n")
        out = search_code("add_task", path="todo/todo.py")
        self.assertIn("todo/todo.py:1:", out)
        self.assertNotIn("other.py", out)
        with self.assertRaises(ToolInputError) as ctx:
            search_code("x", path="todo/missing.py")
        self.assertIn("Path not found", str(ctx.exception))

    # --- git-lite ---
    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_git_status_commit_log(self):
        gitlite.ensure_repo()
        self.assertEqual(git_log(), "No commits yet.")
        write_file("a.txt", "x")
        self.assertIn("a.txt", git_status())
        self.assertIn("Committed", git_commit("add a"))
        self.assertEqual(git_commit("again"), "Nothing to commit.")
        self.assertIn("add a", git_log())
        with self.assertRaises(ToolInputError):
            git_commit("   ")

    # --- audit ---
    def test_every_call_is_logged_and_errors_are_clean(self):
        write_file("a.txt", "x")
        with self.assertRaises(ToolInputError):
            read_file("nope.txt")
        rows = [json.loads(l) for l in config.LOG_PATH.read_text().splitlines()]
        self.assertEqual([r["tool"] for r in rows], ["write_file", "read_file"])
        self.assertTrue(rows[0]["ok"])
        self.assertFalse(rows[1]["ok"])

    def test_unexpected_errors_do_not_leak_details(self):
        write_file("a.txt", "x")
        # a file as a parent folder triggers an unexpected-style path problem
        with self.assertRaises(ToolInputError) as ctx:
            write_file("a.txt/child.txt", "y")
        self.assertNotIn("Traceback", str(ctx.exception))
        self.assertNotIn(str(self.root), str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
