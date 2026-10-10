# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 JunkaiWang-TheoPhy
"""Behavioral checks for private, reviewed, bounded daily memory retrieval."""

import hashlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from datetime import date, datetime, timezone
from pathlib import Path

from airjelly_bridge.errors import BridgeError
from desktop_memory.cli import BEGIN, END, MAX_REPORT_BYTES, MemoryStore, main, resolve_day
from desktop_memory.cli import read_bounded


class DesktopMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state_path = self.root / "apps/console/.local/desktop-history/state.json"
        self.state_path.parent.mkdir(parents=True)
        self.notes = self.root / "vault/daily-notes"
        self.notes.mkdir(parents=True)
        self.state = {"schema_version": 1, "days": {}}
        self.config = self.root / "config.json"
        self.config.write_text(json.dumps({"schema_version": 1, "root": str(self.root), "timezone": "Asia/Shanghai"}))
        self.add_note("2026-10-09", "LeetCode discussed; completion unknown.")

    def save_state(self):
        self.state_path.write_text(json.dumps(self.state))

    def add_note(self, day, body):
        path = self.notes / f"{day}-desktop.md"
        path.write_text(f"{BEGIN}\n# {day}\n{body}\n{END}\n")
        self.state["days"][day] = {
            "curation": {"status": "verified_partial", "privacy": "safe_metadata_only",
                         "path": f"vault/daily-notes/{day}-desktop.md",
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
            "collection": {"status": "processed_with_gaps", "body_read_status": "quarantined_after_privacy_scan"},
            "github": {"status": "verified"}, "wiki": {"status": "pending"},
        }
        self.save_state()
        return path

    def test_read_preserves_partial_review_and_pending_sync(self):
        row = MemoryStore(self.root).read(date(2026, 10, 9))
        self.assertIn("completion unknown", row["text"])
        self.assertEqual(row["coverage"], "processed_with_gaps")
        self.assertEqual(row["body_read_status"], "quarantined_after_privacy_scan")
        self.assertEqual(row["sync"]["wiki"], "pending")
        self.assertTrue(row["content_is_untrusted"])

    def test_date_uses_shanghai_calendar_across_utc_boundary(self):
        now = datetime(2026, 10, 9, 20, 0, tzinfo=timezone.utc)
        self.assertEqual(resolve_day("today", now), date(2026, 10, 10))
        self.assertEqual(resolve_day("yesterday", now), date(2026, 10, 9))

    def test_traversal_and_invalid_dates_are_rejected(self):
        for value in ["../../private", "2026-02-30", "20261009", "2026-10-09/foo"]:
            with self.subTest(value=value), self.assertRaises(BridgeError):
                resolve_day(value)

    def test_unreviewed_or_unsafe_curation_never_returns_text(self):
        for field, value in [("status", "pending"), ("privacy", "unknown"), ("path", "raw/private.md")]:
            with self.subTest(field=field):
                self.add_note("2026-10-09", "LeetCode discussed")
                self.state["days"]["2026-10-09"]["curation"][field] = value
                self.save_state()
                with self.assertRaises(BridgeError) as caught:
                    MemoryStore(self.root).read(date(2026, 10, 9))
                self.assertEqual(caught.exception.code, "not_reviewed")

    def test_post_review_edit_is_not_retrieved(self):
        path = self.notes / "2026-10-09-desktop.md"
        path.write_text(path.read_text() + "unreviewed private addition")
        with self.assertRaises(BridgeError) as caught:
            MemoryStore(self.root).read(date(2026, 10, 9))
        self.assertEqual(caught.exception.code, "stale_review")

    def test_external_symlink_note_is_rejected(self):
        external = self.root.parent / (self.root.name + "-external-note")
        external.write_text("private external content")
        self.addCleanup(external.unlink)
        path = self.notes / "2026-10-09-desktop.md"
        path.unlink()
        path.symlink_to(external)
        with self.assertRaises(BridgeError) as caught:
            MemoryStore(self.root).read(date(2026, 10, 9))
        self.assertEqual(caught.exception.code, "unsafe_path")

    def test_external_symlink_directory_is_rejected(self):
        vault = self.root / "vault"
        external = self.root / "outside"
        external.mkdir()
        (self.notes / "2026-10-09-desktop.md").unlink()
        self.notes.rmdir()
        vault.rmdir()
        # An ancestor pointing outside the source root must not expose that source.
        vault.symlink_to(self.root.parent)
        with self.assertRaises(BridgeError) as caught:
            MemoryStore(self.root).read(date(2026, 10, 9))
        self.assertEqual(caught.exception.code, "unsafe_path")

    def test_search_only_reads_requested_date_window_and_desktop_notes(self):
        self.add_note("2026-10-08", "Old LeetCode discussion")
        (self.notes / "2026-10-09.md").write_text("LeetCode private chat")
        result = MemoryStore(self.root).query(date(2026, 10, 9), days=1, query="leetcode")
        self.assertEqual([r["date"] for r in result["data"]], ["2026-10-09"])
        self.assertNotIn("private chat", json.dumps(result))
        self.assertEqual(result["data"][0]["matches"][0]["line"], 3)

    def test_search_paginates_and_does_not_confuse_metadata_with_text(self):
        self.add_note("2026-10-08", "LeetCode alternative")
        result = MemoryStore(self.root).query(date(2026, 10, 9), days=2, query="LEETCODE", limit=1)
        self.assertEqual(len(result["data"]), 1)
        self.assertTrue(result["meta"]["has_more"])
        self.assertNotIn("text", result["data"][0])
        listed = MemoryStore(self.root).query(date(2026, 10, 9), days=2)
        self.assertNotIn("text", listed["data"][0])

    def test_search_reaches_beyond_read_output_limit(self):
        self.add_note("2026-10-09", "x" * 21_000 + "\nneedle")
        result = MemoryStore(self.root).query(date(2026, 10, 9), days=1, query="needle")
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["data"][0]["matches"][0]["text"], "needle")

    def test_read_truncation_is_explicit(self):
        row = MemoryStore(self.root).read(date(2026, 10, 9), max_chars=10)
        self.assertEqual(len(row["text"]), 10)
        self.assertTrue(row["truncated"])

    def test_missing_day_is_skipped_without_hiding_available_day(self):
        result = MemoryStore(self.root).query(date(2026, 10, 10), days=2, query="LeetCode")
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(result["meta"]["skipped"], [{"date": "2026-10-10", "reason": "not_reviewed"}])

    def test_authentication_material_blocks_even_a_reviewed_note(self):
        for text in ["https://example.invalid/?sid=do-not-print", "sk-" + "x" * 24]:
            with self.subTest(text=text):
                self.add_note("2026-10-09", text)
                with self.assertRaises(BridgeError) as caught:
                    MemoryStore(self.root).read(date(2026, 10, 9))
                self.assertEqual(caught.exception.code, "privacy_hold")

    def test_bounds_prevent_archive_and_output_expansion(self):
        store = MemoryStore(self.root)
        for days, limit in [(0, 1), (32, 1), (7, 11), (7, 0)]:
            with self.subTest(days=days, limit=limit), self.assertRaises(BridgeError):
                store.query(date(2026, 10, 9), days=days, limit=limit)
        for limit in [0, 20001]:
            with self.assertRaises(BridgeError):
                store.read(date(2026, 10, 9), max_chars=limit)

    def test_large_files_and_broken_managed_boundaries_are_rejected(self):
        self.add_note("2026-10-09", "x" * MAX_REPORT_BYTES)
        with self.assertRaises(BridgeError) as caught:
            MemoryStore(self.root).read(date(2026, 10, 9))
        self.assertEqual(caught.exception.code, "size_limit")
        self.add_note("2026-10-09", BEGIN + "\ninvalid nested block")
        with self.assertRaises(BridgeError) as caught:
            MemoryStore(self.root).read(date(2026, 10, 9))
        self.assertEqual(caught.exception.code, "invalid_note")

    def test_cli_emits_json_without_mutating_notes_or_checkpoint(self):
        output = io.StringIO()
        note_before = (self.notes / "2026-10-09-desktop.md").read_bytes()
        state_before = self.state_path.read_bytes()
        result = main(["--config", str(self.config), "read", "--date", "2026-10-09"], stdout=output)
        self.assertEqual(result, 0)
        self.assertTrue(json.loads(output.getvalue())["ok"])
        self.assertEqual(note_before, (self.notes / "2026-10-09-desktop.md").read_bytes())
        self.assertEqual(state_before, self.state_path.read_bytes())

    def test_cli_bad_arguments_are_structured(self):
        output = io.StringIO()
        result = main(["--config", str(self.config), "read", "--date", "../bad"], stdout=output)
        self.assertEqual(result, 2)
        self.assertEqual(json.loads(output.getvalue())["error"]["code"], "usage")

    def test_calendar_window_underflow_is_structured(self):
        for command in ["list", "search"]:
            with self.subTest(command=command):
                output = io.StringIO()
                argv = ["--config", str(self.config), command, "--end-date", "0001-01-01", "--days", "2"]
                if command == "search":
                    argv += ["--query", "LeetCode"]
                code = main(argv, stdout=output)
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(output.getvalue())["error"]["code"], "usage")

    def test_single_corrupt_day_does_not_hide_other_reviewed_days(self):
        for value in [[], {"curation": []}, {"curation": self.state["days"]["2026-10-09"]["curation"], "collection": []}]:
            with self.subTest(value=value):
                self.state["days"]["2026-10-10"] = value
                self.save_state()
                output = io.StringIO()
                code = main(["--config", str(self.config), "list", "--end-date", "2026-10-10", "--days", "2"], stdout=output)
                self.assertEqual(code, 0)
                result = json.loads(output.getvalue())
                self.assertEqual([row["date"] for row in result["data"]], ["2026-10-09"])
                self.assertEqual(result["meta"]["skipped"], [{"date": "2026-10-10", "reason": "invalid_state"}])

    def test_search_uses_one_validated_snapshot_when_file_disappears(self):
        reads = 0
        def disappearing_note(path, maximum):
            nonlocal reads
            if path.name.endswith("-desktop.md"):
                reads += 1
                if reads > 1:
                    raise FileNotFoundError("note removed after its validated snapshot")
            return read_bounded(path, maximum)
        output = io.StringIO()
        with patch("desktop_memory.cli.read_bounded", side_effect=disappearing_note):
            code = main(["--config", str(self.config), "search", "--end-date", "2026-10-09", "--days", "1", "--query", "LeetCode"], stdout=output)
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(output.getvalue())["data"]), 1)
        self.assertEqual(reads, 1)

    def test_malformed_curation_scalars_are_isolated(self):
        for field, value in [("status", []), ("privacy", {}), ("path", None), ("sha256", {})]:
            with self.subTest(field=field):
                self.add_note("2026-10-10", "reviewed current day")
                self.state["days"]["2026-10-10"]["curation"][field] = value
                self.save_state()
                output = io.StringIO()
                code = main(["--config", str(self.config), "list", "--end-date", "2026-10-10", "--days", "2"], stdout=output)
                self.assertEqual(code, 0)
                result = json.loads(output.getvalue())
                self.assertEqual([row["date"] for row in result["data"]], ["2026-10-09"])
                self.assertEqual(result["meta"]["skipped"], [{"date": "2026-10-10", "reason": "invalid_state"}])


if __name__ == "__main__":
    unittest.main()
