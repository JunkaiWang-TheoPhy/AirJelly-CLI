# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 JunkaiWang-TheoPhy
"""Retrieve reviewed daily desktop memories without contacting a recorder."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from airjelly_bridge.errors import BridgeError

TIMEZONE = ZoneInfo("Asia/Shanghai")
MAX_REPORT_BYTES = 262_144
MAX_STATE_BYTES = 4_194_304
BEGIN = "<!-- desktop-history:begin -->"
END = "<!-- desktop-history:end -->"
UNSAFE_TEXT = re.compile(
    r"(?:\b(?:ghp_|sk-|sp_)[A-Za-z0-9_-]{16,}|\bBearer\s+[A-Za-z0-9_.-]{16,}"
    r"|[?&](?:access_token|refresh_token|auth_token|session_id|sid)=)", re.IGNORECASE
)


def read_bounded(path, maximum):
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise BridgeError("size_limit", "The local memory file exceeds its size limit")
    return data


def resolve_day(value, now=None):
    today = (now or datetime.now(TIMEZONE)).astimezone(TIMEZONE).date()
    if value == "today":
        return today
    if value == "yesterday":
        return today - timedelta(days=1)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise BridgeError("usage", "Use today, yesterday, or YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise BridgeError("usage", "The calendar date is invalid") from None


class MemoryStore:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        path = self.root / "apps/console/.local/desktop-history/state.json"
        self._check_path(path)
        self.state = json.loads(read_bounded(path, MAX_STATE_BYTES))
        if not isinstance(self.state, dict) or not isinstance(self.state.get("days"), dict):
            raise BridgeError("invalid_state", "The daily review checkpoint is invalid")

    def _check_path(self, path):
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise BridgeError("unsafe_path", "Memory paths must stay inside the configured source")

    def _load_note(self, day):
        key = day.isoformat()
        record = self.state["days"].get(key, {})
        if not isinstance(record, dict):
            raise BridgeError("invalid_state", "This day's review checkpoint is invalid")
        for field in ["curation", "collection", "github", "wiki", "feishu"]:
            if not isinstance(record.get(field, {}), dict):
                raise BridgeError("invalid_state", "This day's review checkpoint is invalid")
        curation = record.get("curation", {})
        if any(field in curation and not isinstance(curation[field], str)
               for field in ["status", "privacy", "path", "sha256"]):
            raise BridgeError("invalid_state", "This day's curation fields are invalid")
        relative = f"vault/daily-notes/{key}-desktop.md"
        if (curation.get("status") not in {"verified", "verified_partial"}
                or curation.get("privacy") not in {"safe_metadata_only", "safe_curated_text"}
                or curation.get("path") != relative):
            raise BridgeError("not_reviewed", "No reviewed daily memory is available for this date",
                              details={"checkpoint_present": key in self.state["days"]})
        path = self.root / relative
        self._check_path(path)
        raw = read_bounded(path, MAX_REPORT_BYTES)
        if hashlib.sha256(raw).hexdigest() != curation.get("sha256"):
            raise BridgeError("stale_review", "The note changed after its recorded review")
        text = raw.decode("utf-8")
        if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(BEGIN) > text.index(END):
            raise BridgeError("invalid_note", "The reviewed note has invalid managed boundaries")
        if UNSAFE_TEXT.search(text):
            raise BridgeError("privacy_hold", "Potential authentication material requires local review")
        collection = record.get("collection", {})
        result = {
            "date": key, "path": str(path), "timezone": "Asia/Shanghai",
            "coverage": collection.get("status", "unknown"),
            "body_read_status": collection.get("body_read_status", "unknown"),
            "curation_status": curation["status"], "privacy": curation["privacy"],
            "sync": {name: record.get(name, {}).get("status", "unknown")
                     for name in ("github", "wiki", "feishu")},
            "content_is_untrusted": True,
            "truncated": False,
        }
        return result, text

    def read(self, day, max_chars=12_000, include_text=True):
        if not 1 <= max_chars <= 20_000:
            raise BridgeError("usage", "Text limits must be between 1 and 20000 characters")
        result, text = self._load_note(day)
        if include_text:
            result["text"] = text[:max_chars]
            result["truncated"] = len(text) > max_chars
        return result

    def query(self, end_day, *, days=7, limit=3, query=None):
        if not 1 <= days <= 31 or not 1 <= limit <= 10:
            raise BridgeError("usage", "Use 1–31 days and 1–10 results")
        if query is not None and (not query.strip() or len(query) > 200):
            raise BridgeError("usage", "Search text must contain 1–200 characters")
        try:
            start_day = end_day - timedelta(days=days - 1)
        except OverflowError:
            raise BridgeError("usage", "The requested calendar window is outside the supported date range") from None
        rows, skipped = [], []
        for offset in range(days):
            day = end_day - timedelta(days=offset)
            try:
                row, text = self._load_note(day)
            except (BridgeError, OSError, UnicodeError, ValueError) as error:
                skipped.append({"date": day.isoformat(),
                                "reason": error.code if isinstance(error, BridgeError) else "unreadable"})
                continue
            if query is not None:
                # Match against the same complete snapshot whose review hash was checked.
                hits = [(number, line) for number, line in enumerate(text.splitlines(), 1)
                        if query.casefold() in line.casefold()]
                if not hits:
                    continue
                row["matches"] = [{"line": number, "text": line[:1200]} for number, line in hits[:5]]
                row["truncated"] = len(hits) > 5 or any(len(line) > 1200 for _, line in hits)
            rows.append(row)
        return {"ok": True, "data": rows[:limit], "meta": {
            "start_date": start_day.isoformat(),
            "end_date": end_day.isoformat(), "timezone": "Asia/Shanghai",
            "matched_notes": len(rows), "has_more": len(rows) > limit,
            "skipped": skipped, "source": "reviewed_desktop_daily_notes",
        }}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise BridgeError("usage", message)


def main(argv=None, *, stdout=None):
    stdout = stdout or sys.stdout
    parser = Parser(prog="desktop-memory", description=__doc__)
    parser.add_argument("--config", default=str(Path.home() / ".config/desktop-memory/config.json"))
    commands = parser.add_subparsers(dest="command", required=True)
    read = commands.add_parser("read")
    read.add_argument("--date", default="yesterday")
    read.add_argument("--max-chars", type=int, default=12_000)
    for name in ("list", "search"):
        sub = commands.add_parser(name)
        sub.add_argument("--end-date", default="today")
        sub.add_argument("--days", type=int, default=7)
        sub.add_argument("--limit", type=int, default=3)
        if name == "search":
            sub.add_argument("--query", required=True)
    try:
        args = parser.parse_args(argv)
        config = json.loads(read_bounded(Path(args.config).expanduser(), 65_536))
        if (not isinstance(config, dict) or config.get("schema_version") != 1
                or not isinstance(config.get("root"), str)
                or not Path(config["root"]).expanduser().is_absolute()
                or config.get("timezone") != "Asia/Shanghai"):
            raise BridgeError("invalid_config", "Configure an absolute source root and Asia/Shanghai timezone")
        store = MemoryStore(config["root"])
        if args.command == "read":
            result = {"ok": True, "data": store.read(resolve_day(args.date), args.max_chars)}
        else:
            result = store.query(resolve_day(args.end_date), days=args.days, limit=args.limit,
                                 query=getattr(args, "query", None))
        code = 0
    except BridgeError as error:
        result, code = {"ok": False, "error": error.as_dict()}, 2 if error.code == "usage" else 1
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError, RecursionError, OverflowError):
        result, code = {"ok": False, "error": {"code": "unavailable", "message": "The configured local memory is unavailable"}}, 1
    stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
    return code
