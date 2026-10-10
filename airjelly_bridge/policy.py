# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 JunkaiWang-TheoPhy
"""Explicit local permission and output limits; never inferred from captured data."""

from dataclasses import dataclass
import json
from pathlib import Path

from .errors import BridgeError

GROUPS = frozenset({"events", "tasks", "schedules", "memories", "persons", "usage", "reminders", "recording"})


def _names(value, key):
    if value is None:
        return None
    if not isinstance(value, (list, tuple, set, frozenset)) or any(not isinstance(x, str) or not x for x in value):
        raise BridgeError("invalid_policy", f"{key} must contain nonempty strings")
    return frozenset(value)


@dataclass(frozen=True)
class Policy:
    allow_write: bool = False
    allow_cost: bool = False
    allow_execute: bool = False
    allow_methods: frozenset | None = None
    deny_methods: frozenset = frozenset()
    groups: frozenset = GROUPS
    max_items: int = 200
    max_text_chars: int = 2000
    max_span_days: int = 7
    redact: bool = True

    def __post_init__(self):
        for key in ("allow_write", "allow_cost", "allow_execute", "redact"):
            if type(getattr(self, key)) is not bool:
                raise BridgeError("invalid_policy", f"{key} must be boolean")
        for key, upper in (("max_items", 1000), ("max_text_chars", 100000), ("max_span_days", 365)):
            value = getattr(self, key)
            if type(value) is not int or not 1 <= value <= upper:
                raise BridgeError("invalid_policy", f"{key} must be an integer from 1 to {upper}")
        allowed = _names(self.allow_methods, "allow_methods")
        denied = _names(self.deny_methods, "deny_methods")
        groups = _names(self.groups, "groups")
        if denied is None or groups is None or groups - GROUPS:
            raise BridgeError("invalid_policy", "Invalid denied-method list or method group")
        from .contracts import METHODS
        if ((allowed or frozenset()) | denied) - METHODS.keys():
            raise BridgeError("invalid_policy", "Unknown method in policy")
        object.__setattr__(self, "allow_methods", allowed)
        object.__setattr__(self, "deny_methods", denied)
        object.__setattr__(self, "groups", groups)

    @classmethod
    def from_file(cls, path=None, *, allow_write=False, allow_cost=False, allow_execute=False,
                  allow_methods=None, deny_methods=None, groups=None):
        config = {}
        if path:
            try:
                config = json.loads(Path(path).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise BridgeError("invalid_policy", "Cannot read a valid policy JSON object") from None
        if not isinstance(config, dict):
            raise BridgeError("invalid_policy", "Policy must be an object")
        keys = set(cls.__dataclass_fields__)
        if set(config) - keys:
            raise BridgeError("invalid_policy", "Unknown policy keys", details=sorted(set(config) - keys))
        for key in ("allow_write", "allow_cost", "allow_execute", "redact"):
            if key in config and type(config[key]) is not bool:
                raise BridgeError("invalid_policy", f"{key} must be boolean")
        from .contracts import METHODS
        allowed = _names(config.get("allow_methods"), "allow_methods")
        narrowed = _names(allow_methods, "allow_methods")
        if ((allowed or frozenset()) | (narrowed or frozenset())) - METHODS.keys():
            raise BridgeError("invalid_policy", "Unknown method in allowlist")
        if narrowed is not None:
            allowed = narrowed if allowed is None else allowed & narrowed
        denied = (_names(config.get("deny_methods"), "deny_methods") or frozenset()) | (_names(deny_methods, "deny_methods") or frozenset())
        selected_groups = _names(config.get("groups"), "groups")
        selected_groups = GROUPS if selected_groups is None else selected_groups
        if selected_groups - GROUPS:
            raise BridgeError("invalid_policy", "Unknown method group")
        if groups is not None:
            narrowed_groups = _names(groups, "groups")
            if narrowed_groups - GROUPS:
                raise BridgeError("invalid_policy", "Unknown method group")
            selected_groups &= narrowed_groups
        if selected_groups - GROUPS:
            raise BridgeError("invalid_policy", "Unknown method group")
        if ((allowed or frozenset()) | denied) - METHODS.keys():
            raise BridgeError("invalid_policy", "Unknown method in policy")
        return cls(allow_write=config.get("allow_write", False) or allow_write,
                   allow_cost=config.get("allow_cost", False) or allow_cost,
                   allow_execute=config.get("allow_execute", False) or allow_execute,
                   allow_methods=allowed, deny_methods=denied, groups=selected_groups,
                   max_items=config.get("max_items", 200), max_text_chars=config.get("max_text_chars", 2000),
                   max_span_days=config.get("max_span_days", 7), redact=config.get("redact", True))

    def authorize(self, method):
        denied = None
        if method.name in self.deny_methods or (self.allow_methods is not None and method.name not in self.allow_methods):
            denied = "method"
        elif method.group not in self.groups:
            denied = "group"
        elif method.write and not self.allow_write:
            denied = "write"
        elif method.costly and not self.allow_cost:
            denied = "cost"
        elif method.execute and not self.allow_execute:
            denied = "execute"
        if denied:
            raise BridgeError("policy_denied", f"{method.name} is disabled by the {denied} policy", details={"gate": denied})

    def as_dict(self):
        return {"allow_write": self.allow_write, "allow_cost": self.allow_cost, "allow_execute": self.allow_execute,
                "allow_methods": None if self.allow_methods is None else sorted(self.allow_methods),
                "deny_methods": sorted(self.deny_methods), "groups": sorted(self.groups),
                "max_items": self.max_items, "max_text_chars": self.max_text_chars,
                "max_span_days": self.max_span_days, "redact": self.redact}
