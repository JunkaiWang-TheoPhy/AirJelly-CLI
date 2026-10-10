# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 JunkaiWang-TheoPhy
"""Permission intersections and malformed-policy rejection."""

import json
from pathlib import Path
import tempfile
import unittest

from airjelly_bridge.contracts import METHODS
from airjelly_bridge.errors import BridgeError
from airjelly_bridge.policy import GROUPS, Policy


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="airjelly-policy-test-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "policy.json"

    def load(self, config, **flags):
        self.path.write_text(json.dumps(config), encoding="utf-8")
        self.path.chmod(0o600)
        return Policy.from_file(self.path, **flags)

    def assert_denied(self, policy, method, gate):
        with self.assertRaises(BridgeError) as caught:
            policy.authorize(METHODS[method])
        self.assertEqual(caught.exception.code, "policy_denied")
        self.assertEqual(caught.exception.details, {"gate": gate})

    def test_default_only_allows_nonbillable_reads(self):
        policy = Policy()
        self.assertFalse(policy.allow_write)
        self.assertFalse(policy.allow_cost)
        self.assertFalse(policy.allow_execute)
        for name, method in METHODS.items():
            with self.subTest(method=name):
                if method.write or method.costly or method.execute:
                    with self.assertRaises(BridgeError):
                        policy.authorize(method)
                else:
                    policy.authorize(method)

    def test_side_effect_permissions_are_three_independent_gates(self):
        self.assert_denied(Policy(allow_cost=True, allow_execute=True), "runScheduledTaskNow", "write")
        self.assert_denied(Policy(allow_write=True, allow_execute=True), "runScheduledTaskNow", "cost")
        self.assert_denied(Policy(allow_write=True, allow_cost=True), "runScheduledTaskNow", "execute")
        Policy(allow_write=True, allow_cost=True, allow_execute=True).authorize(METHODS["runScheduledTaskNow"])
        Policy(allow_cost=True).authorize(METHODS["searchMemory"])
        self.assert_denied(Policy(allow_write=True), "searchMemory", "cost")

    def test_flags_can_enable_gates_but_cannot_expand_method_allowlist(self):
        policy = self.load({"allow_methods": ["completeTask", "getTask"]}, allow_write=True, allow_cost=True, allow_execute=True, allow_methods=["completeTask", "startRecording"])
        self.assertEqual(policy.allow_methods, frozenset({"completeTask"}))
        policy.authorize(METHODS["completeTask"])
        self.assert_denied(policy, "startRecording", "method")
        self.assert_denied(policy, "getTask", "method")

    def test_flags_narrow_group_scope_and_never_override_denials(self):
        policy = self.load({"groups": ["recording", "tasks"], "deny_methods": ["stopRecording"]}, groups=["recording", "usage"], deny_methods=["startRecording"], allow_write=True, allow_cost=True, allow_execute=True)
        self.assertEqual(policy.groups, frozenset({"recording"}))
        self.assertEqual(policy.deny_methods, frozenset({"stopRecording", "startRecording"}))
        policy.authorize(METHODS["getRecordingStatus"])
        self.assert_denied(policy, "stopRecording", "method")
        self.assert_denied(policy, "startRecording", "method")
        self.assert_denied(policy, "getTask", "group")
        self.assert_denied(policy, "getDailyAppUsage", "group")

    def test_deny_method_has_priority_over_explicit_allow_and_all_permission_flags(self):
        policy = self.load({"allow_methods": ["startRecording"], "deny_methods": ["startRecording"]}, allow_write=True, allow_cost=True, allow_execute=True, allow_methods=["startRecording"])
        self.assert_denied(policy, "startRecording", "method")

    def test_empty_allowlist_or_group_intersection_means_no_access(self):
        for policy in (self.load({"allow_methods": []}), self.load({"allow_methods": ["getTask"]}, allow_methods=["getMemory"]), self.load({"groups": ["tasks"]}, groups=["recording"])):
            with self.subTest(policy=policy.as_dict()):
                for method in METHODS.values():
                    with self.assertRaises(BridgeError):
                        policy.authorize(method)

    def test_limits_and_redaction_from_file_survive_permission_flags(self):
        policy = self.load({"max_items": 5, "max_text_chars": 20, "max_span_days": 2, "redact": False}, allow_write=True, allow_cost=True, allow_execute=True)
        self.assertEqual((policy.max_items, policy.max_text_chars, policy.max_span_days, policy.redact), (5, 20, 2, False))
        self.assertTrue(policy.allow_write and policy.allow_cost and policy.allow_execute)

    def test_permission_gates_enabled_by_file_are_explicit(self):
        policy = self.load({"allow_write": True, "allow_cost": True, "allow_execute": True})
        policy.authorize(METHODS["runScheduledTaskNow"])
        self.assertEqual(Policy.from_file().groups, GROUPS)
        self.assertEqual(Policy.from_file().deny_methods, frozenset())

    def test_as_dict_is_json_serializable_and_does_not_expose_mutable_policy_sets(self):
        policy = Policy(allow_methods=frozenset({"getTask", "listTasks"}), deny_methods=frozenset({"listTasks"}), groups=frozenset({"tasks"}))
        data = policy.as_dict()
        self.assertEqual(json.loads(json.dumps(data))["allow_methods"], ["getTask", "listTasks"])
        data["allow_methods"].append("startRecording")
        self.assert_denied(policy, "startRecording", "method")

    def test_invalid_policy_files_have_structured_errors(self):
        configs = [None, [], "fixture", {"allow_writes": True}, {"allow_write": "true"}, {"allow_cost": 1}, {"allow_execute": None}, {"redact": 0}, {"max_items": True}, {"max_items": 0}, {"max_items": 1001}, {"max_text_chars": 0}, {"max_text_chars": 100001}, {"max_span_days": -1}, {"max_span_days": 366}, {"max_span_days": 1.5}, {"allow_methods": "getTask"}, {"allow_methods": [""]}, {"allow_methods": [1]}, {"allow_methods": ["madeUpMethod"]}, {"deny_methods": ["madeUpMethod"]}, {"groups": ["madeUpGroup"]}, {"groups": "tasks"}]
        for config in configs:
            with self.subTest(config=config):
                with self.assertRaises(BridgeError) as caught:
                    self.load(config)
                self.assertEqual(caught.exception.code, "invalid_policy")

    def test_invalid_config_is_not_hidden_by_valid_flag_intersection(self):
        for config, flags in (({"allow_methods": ["getTask", "madeUpMethod"]}, {"allow_methods": ["getTask"]}), ({"groups": ["tasks", "madeUpGroup"]}, {"groups": ["tasks"]})):
            with self.subTest(config=config):
                with self.assertRaises(BridgeError) as caught:
                    self.load(config, **flags)
                self.assertEqual(caught.exception.code, "invalid_policy")

    def test_invalid_permission_flags_cannot_bypass_type_validation(self):
        for flags in ({"allow_write": "yes"}, {"allow_cost": 1}, {"allow_execute": []}, {"allow_methods": "getTask"}, {"groups": ["madeUpGroup"]}, {"deny_methods": [True]}):
            with self.subTest(flags=flags):
                with self.assertRaises(BridgeError) as caught:
                    Policy.from_file(**flags)
                self.assertEqual(caught.exception.code, "invalid_policy")

    def test_direct_policy_construction_cannot_bypass_type_or_range_validation(self):
        for values in ({"allow_write": "yes"}, {"allow_cost": 1}, {"allow_execute": "false"}, {"max_items": True}, {"max_items": -1}, {"max_text_chars": 0}, {"max_span_days": 0}, {"groups": ["madeUpGroup"]}, {"allow_methods": ["madeUpMethod"]}, {"redact": "false"}):
            with self.subTest(values=values):
                with self.assertRaises(BridgeError) as caught:
                    Policy(**values)
                self.assertEqual(caught.exception.code, "invalid_policy")

    def test_missing_or_invalid_json_policy_is_rejected_without_file_contents(self):
        for content in ("{not-json private-fixture}", ""):
            with self.subTest(content=content):
                self.path.write_text(content)
                with self.assertRaises(BridgeError) as caught:
                    Policy.from_file(self.path)
                self.assertEqual(caught.exception.code, "invalid_policy")
                self.assertNotIn("private-fixture", str(caught.exception))
        self.path.unlink()
        with self.assertRaises(BridgeError) as caught:
            Policy.from_file(self.path)
        self.assertEqual(caught.exception.code, "invalid_policy")


if __name__ == "__main__":
    unittest.main()
