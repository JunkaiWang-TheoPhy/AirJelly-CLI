#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 JunkaiWang-TheoPhy
"""Write a demo-only config without touching the user's default configuration."""
import json
from pathlib import Path

fixture = Path(__file__).resolve().parent / "fixture"
output = Path(__file__).resolve().parents[2] / ".local/desktop-memory-demo.json"
output.parent.mkdir(mode=0o700, exist_ok=True)
expected = {"schema_version": 1, "root": str(fixture), "timezone": "Asia/Shanghai"}
if output.exists():
    if json.loads(output.read_text()) != expected:
        raise SystemExit("Preserving an existing config with different contents")
else:
    with output.open("x", encoding="utf-8") as stream:
        json.dump(expected, stream, indent=2)
        stream.write("\n")
output.chmod(0o600)
print(output.relative_to(Path(__file__).resolve().parents[2]))
