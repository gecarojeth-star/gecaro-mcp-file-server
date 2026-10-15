import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO

import todo


class TodoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "tasks.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_empty_when_no_file(self):
        self.assertEqual(todo.list_tasks(self.path), [])

    def test_add_assigns_incrementing_ids(self):
        a = todo.add_task("one", self.path)
        b = todo.add_task("two", self.path)
        self.assertEqual((a["id"], b["id"]), (1, 2))
        self.assertFalse(a["done"])

    def test_add_persists_to_file(self):
        todo.add_task("persist me", self.path)
        tasks = todo.load_tasks(self.path)
        self.assertEqual(tasks[0]["text"], "persist me")

    def test_add_empty_text_rejected(self):
        with self.assertRaises(ValueError):
            todo.add_task("   ", self.path)

    def test_done_marks_task(self):
        todo.add_task("a", self.path)
        todo.add_task("b", self.path)
        todo.mark_done(2, self.path)
        tasks = todo.list_tasks(self.path)
        self.assertFalse(tasks[0]["done"])
        self.assertTrue(tasks[1]["done"])

    def test_done_unknown_id_raises(self):
        with self.assertRaises(KeyError):
            todo.mark_done(99, self.path)

    def test_cli_add_list_done(self):
        out = StringIO()
        with redirect_stdout(out):
            self.assertEqual(todo.main(["add", "write tests"], self.path), 0)
            self.assertEqual(todo.main(["done", "1"], self.path), 0)
            self.assertEqual(todo.main(["list"], self.path), 0)
        self.assertIn("1. [x] write tests", out.getvalue())

    def test_cli_done_unknown_id_returns_error(self):
        err = StringIO()
        with redirect_stderr(err):
            self.assertEqual(todo.main(["done", "5"], self.path), 1)
        self.assertIn("No task with ID 5", err.getvalue())


    def test_empty_file_treated_as_no_tasks(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("")
        self.assertEqual(todo.list_tasks(self.path), [])
        self.assertEqual(todo.add_task("x", self.path)["id"], 1)

    def test_corrupt_json_raises_value_error(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{not json")
        with self.assertRaises(ValueError):
            todo.load_tasks(self.path)

    def test_wrong_shape_raises_value_error(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write('{"id": 1}')
        with self.assertRaises(ValueError):
            todo.load_tasks(self.path)

    def test_cli_corrupt_file_returns_error_not_traceback(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("garbage")
        err = StringIO()
        with redirect_stderr(err):
            self.assertEqual(todo.main(["list"], self.path), 1)
        self.assertIn("not valid JSON", err.getvalue())

    def test_save_leaves_no_temp_file(self):
        todo.add_task("a", self.path)
        self.assertEqual(os.listdir(self.tmp.name), ["tasks.json"])

    def test_ids_not_reused_after_gap(self):
        todo.add_task("a", self.path)
        todo.add_task("b", self.path)
        tasks = todo.load_tasks(self.path)
        todo.save_tasks([t for t in tasks if t["id"] == 2], self.path)
        self.assertEqual(todo.add_task("c", self.path)["id"], 3)

    def test_done_twice_is_idempotent(self):
        todo.add_task("a", self.path)
        todo.mark_done(1, self.path)
        self.assertTrue(todo.mark_done(1, self.path)["done"])


if __name__ == "__main__":
    unittest.main()
