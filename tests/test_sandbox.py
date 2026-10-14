import os
import tempfile
import unittest
from pathlib import Path

from server import config
from server.errors import ToolInputError
from server.sandbox import SandboxError, resolve_path


class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / "docs").mkdir()
        (self.root / ".git").mkdir()
        self._old = config.WORKSPACE_ROOT
        config.WORKSPACE_ROOT = self.root

    def tearDown(self):
        config.WORKSPACE_ROOT = self._old
        self.tmp.cleanup()

    def test_normal_paths_resolve_inside_root(self):
        self.assertEqual(resolve_path("docs/a.md"), self.root / "docs" / "a.md")
        self.assertEqual(resolve_path("."), self.root)
        self.assertEqual(resolve_path(""), self.root)

    def test_traversal_is_rejected(self):
        for bad in ["../x", "docs/../../x", "..", "docs/../..", "a/../../../etc/passwd",
                    "..\\x", "docs\\..\\..\\x"]:
            with self.subTest(bad=bad), self.assertRaises(SandboxError):
                resolve_path(bad)

    def test_absolute_paths_are_rejected(self):
        for bad in ["/etc/passwd", "C:\\Windows\\win.ini", "C:/Windows", "C:foo",
                    "\\\\server\\share\\f", "//server/share"]:
            with self.subTest(bad=bad), self.assertRaises(SandboxError):
                resolve_path(bad)

    def test_null_byte_and_non_string(self):
        with self.assertRaises(SandboxError):
            resolve_path("a\x00b")
        with self.assertRaises(SandboxError):
            resolve_path(None)

    def test_git_folder_is_protected(self):
        for bad in [".git", ".git/config", "./.GIT/hooks/pre-commit"]:
            with self.subTest(bad=bad), self.assertRaises(SandboxError):
                resolve_path(bad)

    def test_symlink_escape_is_rejected(self):
        outside = tempfile.TemporaryDirectory()
        try:
            try:
                os.symlink(outside.name, self.root / "link", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks not available on this system")
            with self.assertRaises(SandboxError):
                resolve_path("link/secret.txt")
        finally:
            outside.cleanup()

    def test_sandbox_error_is_a_tool_error(self):
        self.assertTrue(issubclass(SandboxError, ToolInputError))


if __name__ == "__main__":
    unittest.main()
