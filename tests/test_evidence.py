import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from server import config
from scripts import collect_evidence as ce


def row(minute, tool="read_file", ok=True, args=None, error=None, second=0):
    r = {"ts": datetime(2026, 10, 15, 4, minute, second, tzinfo=timezone.utc).isoformat(),
         "tool": tool, "args": args or {}, "ok": ok, "ms": 5.0}
    if error:
        r["error"] = error
    return r


class EvidenceTests(unittest.TestCase):
    def test_sessions_split_on_quiet_gaps(self):
        rows = [dict(r, _ts=ce.parse_ts(r["ts"])) for r in (row(0), row(2), row(4), row(40), row(41))]
        sessions = ce.split_sessions(rows, gap_minutes=10)
        self.assertEqual([len(s) for s in sessions], [3, 2])

    def test_summary_counts(self):
        raw = [row(0, args={"path": "a"}), row(0, args={"path": "a"}, second=1),
               row(1, args={"path": "b", "start_line": 5, "end_line": 9}),
               row(2, tool="search_code", ok=False, error="Folder not found: x")]
        s = ce.summarize([dict(r, _ts=ce.parse_ts(r["ts"])) for r in raw])
        self.assertEqual(s["calls"], 4)
        self.assertEqual(len(s["errors"]), 1)
        self.assertEqual(s["whole_reads"], 2)   # two reads with no line range
        self.assertEqual(s["repeated"], 1)      # read_file a, twice
        self.assertEqual(s["tools"]["read_file"], 3)

    def test_report_mentions_failed_call(self):
        raw = [dict(row(0, tool="search_code", ok=False, error="Folder not found"), _ts=ce.parse_ts(row(0)["ts"]))]
        text = ce.build_report([raw], 10)
        self.assertIn("Failed calls", text)
        self.assertIn("Folder not found", text)

    def test_load_calls_skips_bad_lines_and_filters_since(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "calls.jsonl"
            log.write_text("\n".join([json.dumps(row(0)), "not json", json.dumps(row(30))]) + "\n")
            self.assertEqual(len(ce.load_calls(log)), 2)
            self.assertEqual(len(ce.load_calls(log, ce.parse_ts("2026-10-15T04:10:00"))), 1)

    def test_secret_is_never_written(self):
        old = config.AUTH_TOKEN
        config.AUTH_TOKEN = "s3cret" * 6
        try:
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / "x.txt"
                ok = ce.safe_write(dest, "leak: " + config.AUTH_TOKEN, "test")
                self.assertFalse(ok)
                self.assertFalse(dest.exists())
        finally:
            config.AUTH_TOKEN = old


if __name__ == "__main__":
    unittest.main()
