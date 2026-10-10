# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 JunkaiWang-TheoPhy
"""All public named contracts, including ordering and restricted updates."""

from copy import deepcopy
import unittest

from airjelly_bridge.contracts import METHODS, validate_params
from airjelly_bridge.errors import BridgeError


class ContractTests(unittest.TestCase):
    def assert_invalid(self, name, params):
        with self.assertRaises(BridgeError) as caught:
            validate_params(name, params)
        self.assertEqual(caught.exception.code, "invalid_params")

    def test_all_43_public_methods_have_exact_argument_mapping(self):
        cases = {
            "listEvents": ({"endTimeMs": 200, "startTimeMs": 100}, [100, 200]),
            "getTask": ({"id": "task_1"}, ["task_1"]),
            "listTasks": ({"filter": {"status": ["open", "completed"], "limit": 5}}, [{"status": ["open", "completed"], "limit": 5}]),
            "listOpenTasks": ({"limit": 5}, [5]),
            "getTaskMemories": ({"taskId": "task_1"}, ["task_1"]),
            "createTask": ({"task": {"title": "Review", "description": "Notes", "l1_scene": "build", "start_time": 10, "due_date": 20}}, [{"title": "Review", "description": "Notes", "l1_scene": "build", "start_time": 10, "due_date": 20}]),
            "updateTask": ({"patch": {"title": "Done", "description": "", "l1_scene": "build", "next_steps": ["Read"], "progress_summary": "Partial", "due_date": 0}, "id": "task_1"}, ["task_1", {"title": "Done", "description": "", "l1_scene": "build", "next_steps": ["Read"], "progress_summary": "Partial", "due_date": 0}]),
            "completeTask": ({"id": "task_1"}, ["task_1"]),
            "reopenTask": ({"id": "task_1"}, ["task_1"]),
            "snoozeTask": ({"untilMs": 300, "id": "task_1"}, ["task_1", 300]),
            "archiveTask": ({"id": "task_1"}, ["task_1"]),
            "unarchiveTask": ({"id": "task_1"}, ["task_1"]),
            "createScheduledTask": ({"schedule": {"title": "Review", "instruction": "Read notes", "schedule_kind": "once", "rrule": None, "timezone": "Asia/Shanghai", "start_at": 300, "end_at": None, "task_id": "task_1"}}, [{"title": "Review", "instruction": "Read notes", "schedule_kind": "once", "rrule": None, "timezone": "Asia/Shanghai", "start_at": 300, "end_at": None, "task_id": "task_1"}]),
            "listScheduledTasks": ({"filter": {"status": "active", "limit": 5}}, [{"status": "active", "limit": 5}]),
            "getScheduledTask": ({"id": 1}, [1]),
            "updateScheduledTask": ({"patch": {"title": "Review", "instruction": "Read", "schedule_kind": "rrule", "rrule": "FREQ=DAILY", "timezone": "Asia/Shanghai", "start_at": "2026-10-10T09:30:00+08:00", "end_at": None, "status": "paused"}, "id": 1}, [1, {"title": "Review", "instruction": "Read", "schedule_kind": "rrule", "rrule": "FREQ=DAILY", "timezone": "Asia/Shanghai", "start_at": "2026-10-10T09:30:00+08:00", "end_at": None, "status": "paused"}]),
            "pauseScheduledTask": ({"id": 1}, [1]),
            "resumeScheduledTask": ({"id": 1}, [1]),
            "archiveScheduledTask": ({"id": 1}, [1]),
            "listScheduledTaskRuns": ({"limit": 5, "scheduledTaskId": 1}, [1, 5]),
            "listScheduledTaskUpcomingOccurrences": ({"filter": {"start_ms": 100, "end_ms": 200, "status": "active", "task_id": "task_1", "include_archived": True, "limit": 5}}, [{"start_ms": 100, "end_ms": 200, "status": "active", "task_id": "task_1", "include_archived": True, "limit": 5}]),
            "listScheduledTaskRunHistory": ({"filter": {"scheduled_task_id": 1, "status": "completed", "occurrence_at_after": 100, "occurrence_at_before": 200, "limit": 5}}, [{"scheduled_task_id": 1, "status": "completed", "occurrence_at_after": 100, "occurrence_at_before": 200, "limit": 5}]),
            "getScheduledTaskOverview": ({"options": {"upcoming_start_ms": 100, "upcoming_end_ms": 200, "upcoming_limit": 5, "history_limit": 3, "include_archived": False}}, [{"upcoming_start_ms": 100, "upcoming_end_ms": 200, "upcoming_limit": 5, "history_limit": 3, "include_archived": False}]),
            "runScheduledTaskNow": ({"id": 1}, [1]),
            "retryScheduledTaskRun": ({"runId": 2}, [2]),
            "searchMemory": ({"filter": {"memory_types": ["event"], "task_id": "task_1", "app_name": "Editor", "start_time_after": 100, "start_time_before": 200, "limit": 5}, "query": "notes"}, ["notes", {"memory_types": ["event"], "task_id": "task_1", "app_name": "Editor", "start_time_after": 100, "start_time_before": 200, "limit": 5}]),
            "listMemories": ({"filter": {"memory_types": ["event"], "task_id": "task_1", "app_name": "Editor", "start_time_after": 100, "start_time_before": 200, "limit": 5}}, [{"memory_types": ["event"], "task_id": "task_1", "app_name": "Editor", "start_time_after": 100, "start_time_before": 200, "limit": 5}]),
            "getMemory": ({"id": "mem_1"}, ["mem_1"]),
            "resolveScreenshotPaths": ({"ids": [1, "2"]}, [[1, "2"]]),
            "listPersons": ({}, []),
            "getEventsForEntity": ({"entityId": "entity_1"}, ["entity_1"]),
            "getDailyAppUsage": ({"date": "2026-10-10"}, ["2026-10-10"]),
            "getAppUsageRange": ({"endDate": "2026-10-10", "startDate": "2026-10-09"}, ["2026-10-09", "2026-10-10"]),
            "getTopApps": ({"limit": 5, "endDate": "2026-10-10", "startDate": "2026-10-09"}, ["2026-10-09", "2026-10-10", 5]),
            "getAppSessions": ({"date": "2026-10-10"}, ["2026-10-10"]),
            "getAppIcons": ({"appNames": ["Editor", "Browser"]}, [["Editor", "Browser"]]),
            "dismissReminder": ({"id": 1}, [1]),
            "snoozeReminder": ({"durationMinutes": 1.5, "id": 1}, [1, 1.5]),
            "getRecordingStatus": ({}, []),
            "getRecordingPermissions": ({}, []),
            "getRecordingStats": ({}, []),
            "startRecording": ({}, []),
            "stopRecording": ({}, []),
        }
        self.assertEqual(len(cases), 43)
        self.assertEqual(set(cases), set(METHODS))
        for name, (params, expected) in cases.items():
            with self.subTest(name=name):
                self.assertEqual(validate_params(name, params), expected)
                self.assertEqual(METHODS[name].name, name)
                self.assertIn(METHODS[name].group, {"events", "tasks", "schedules", "memories", "persons", "usage", "reminders", "recording"})

    def test_optional_parameters_are_omitted_without_null_or_defaults(self):
        for name in ("listTasks", "listOpenTasks", "listScheduledTasks", "listScheduledTaskUpcomingOccurrences", "listScheduledTaskRunHistory", "getScheduledTaskOverview", "listMemories"):
            with self.subTest(name=name):
                self.assertEqual(validate_params(name, {}), [])
        self.assertEqual(validate_params("searchMemory", {"query": "notes"}), ["notes"])
        self.assertEqual(validate_params("listScheduledTaskRuns", {"scheduledTaskId": 1}), [1])
        self.assertEqual(validate_params("getTopApps", {"startDate": "2026-10-09", "endDate": "2026-10-10"}), ["2026-10-09", "2026-10-10"])
        self.assertEqual(validate_params("listTasks", {"filter": {}}), [{}])

    def test_unknown_top_level_fields_rejected_for_every_method(self):
        for name in METHODS:
            with self.subTest(name=name):
                self.assert_invalid(name, {"not_public": True})

    def test_unknown_nested_fields_rejected(self):
        for name, field, params in (
            ("listTasks", "filter", {}),
            ("listScheduledTasks", "filter", {}),
            ("listScheduledTaskUpcomingOccurrences", "filter", {}),
            ("listScheduledTaskRunHistory", "filter", {}),
            ("getScheduledTaskOverview", "options", {}),
            ("listMemories", "filter", {}),
            ("searchMemory", "filter", {"query": "notes"}),
            ("createTask", "task", {}),
            ("updateTask", "patch", {"id": 1}),
            ("createScheduledTask", "schedule", {}),
            ("updateScheduledTask", "patch", {"id": 1}),
        ):
            with self.subTest(name=name):
                self.assert_invalid(name, {**params, field: {"not_public": True}})

    def test_task_patch_system_fields_always_rejected(self):
        for field in ("id", "status", "start_time", "end_time", "event_count", "total_duration_seconds", "last_active_at", "created_at", "updated_at", "scheduler_state", "scheduler_archived", "is_commitment", "snoozed_until", "blocked_reason", "origin", "embedding"):
            with self.subTest(field=field):
                self.assert_invalid("updateTask", {"id": 1, "patch": {field: 1}})
        self.assertEqual(set(METHODS["updateTask"].schema["properties"]["patch"]["properties"]), {"title", "description", "l1_scene", "next_steps", "progress_summary", "due_date"})

    def test_schedule_patch_rejects_system_fields(self):
        for field in ("next_run_at", "last_run_at", "created_at", "updated_at", "metadata", "task_id", "overlap_policy", "catch_up_policy", "confirmation_policy"):
            with self.subTest(field=field):
                self.assert_invalid("updateScheduledTask", {"id": 1, "patch": {field: 1}})

    def test_ids_accept_only_positive_integers_or_nonblank_strings(self):
        for value in (1, 9, "task_1", "1"):
            with self.subTest(value=value):
                self.assertEqual(validate_params("getTask", {"id": value}), [value])
        for value in (True, False, 0, -1, 1.0, "", " ", None, [], {}):
            with self.subTest(value=value):
                self.assert_invalid("getTask", {"id": value})
                self.assert_invalid("resolveScreenshotPaths", {"ids": [value]})

    def test_integer_boolean_array_and_string_types_are_strict(self):
        for value in (True, 1.0, "1", None):
            with self.subTest(limit=value):
                self.assert_invalid("listOpenTasks", {"limit": value})
                self.assert_invalid("listEvents", {"startTimeMs": value, "endTimeMs": 100})
        for value in (1, "true", None):
            with self.subTest(boolean=value):
                self.assert_invalid("getScheduledTaskOverview", {"options": {"include_archived": value}})
        for value in ("step", [1], [None], ("step",)):
            with self.subTest(steps=value):
                self.assert_invalid("updateTask", {"id": 1, "patch": {"next_steps": value}})
        self.assert_invalid("createTask", {"task": {"title": 123}})
        self.assert_invalid("getAppIcons", {"appNames": [True]})
        self.assert_invalid("listMemories", {"filter": {"memory_types": "event"}})
        self.assert_invalid("listTasks", {"filter": {"status": [1]}})
        self.assert_invalid("listTasks", {"filter": {"scheduler_archived": True}})

    def test_required_parameters_rejected_when_missing(self):
        for name, method in METHODS.items():
            if method.schema["required"]:
                with self.subTest(name=name):
                    self.assert_invalid(name, {})
        self.assert_invalid("createTask", {"task": {}})
        self.assert_invalid("createScheduledTask", {"schedule": {"title": "Review"}})
        self.assert_invalid("listScheduledTaskRuns", {"limit": 5})
        self.assert_invalid("getTopApps", {"startDate": "2026-10-10", "limit": 5})

    def test_raw_parameter_shape_and_method_name_rejected(self):
        for value in (None, [], "{}", 1):
            with self.subTest(value=value):
                self.assert_invalid("getRecordingStatus", value)
        self.assert_invalid("getRecordingStatus", {1: True})
        for name in ("notPublic", [], None):
            self.assert_invalid(name, {})

    def test_real_handler_read_filters_are_preserved(self):
        task_filter = {
            "status": "future-status", "origin": "manual", "l1_scene": "future-scene",
            "last_active_at_after": 10, "last_active_at_before": 20,
            "start_time_after": 10, "start_time_before": 20,
            "updated_at_after": 10, "updated_at_before": 20,
            "scheduler_state": ["future-state"], "scheduler_archived": 1, "limit": 8,
        }
        self.assertEqual(validate_params("listTasks", {"filter": task_filter}), [task_filter])
        schedule_filter = {"status": ["active", "future-status"], "task_id": None, "include_archived": True, "next_run_at_after": 10, "next_run_at_before": 20, "limit": 8}
        self.assertEqual(validate_params("listScheduledTasks", {"filter": schedule_filter}), [schedule_filter])

    def test_validation_and_output_do_not_mutate_or_alias_input(self):
        params = {"id": 1, "patch": {"next_steps": ["Read"], "description": "notes"}}
        original = deepcopy(params)
        schema = deepcopy(METHODS["updateTask"].schema)
        args = validate_params("updateTask", params)
        self.assertEqual(params, original)
        self.assertEqual(METHODS["updateTask"].schema, schema)
        args[1]["next_steps"].append("Write")
        args[1]["description"] = "changed"
        self.assertEqual(params, original)
        bad = {"id": 1, "patch": {"next_steps": [False]}}
        before = deepcopy(bad)
        self.assert_invalid("updateTask", bad)
        self.assertEqual(bad, before)

    def test_nullable_schedule_fields_preserve_explicit_null(self):
        self.assertEqual(validate_params("updateScheduledTask", {"id": 1, "patch": {"end_at": None, "rrule": None}}), [1, {"end_at": None, "rrule": None}])
        self.assert_invalid("updateTask", {"id": 1, "patch": {"due_date": None}})
        self.assert_invalid("listTasks", {"filter": None})

    def test_open_vocabularies_are_not_invented_enums(self):
        self.assertEqual(validate_params("updateScheduledTask", {"id": 1, "patch": {"schedule_kind": "future-kind", "status": "future-status"}}), [1, {"schedule_kind": "future-kind", "status": "future-status"}])
        self.assertEqual(validate_params("listMemories", {"filter": {"memory_types": ["future-memory-type"]}}), [{"memory_types": ["future-memory-type"]}])

    def test_write_cost_and_execution_metadata(self):
        future_execution = {"createScheduledTask", "updateScheduledTask", "resumeScheduledTask"}
        self.assertEqual({name for name, method in METHODS.items() if method.costly}, {"createTask", "searchMemory", "runScheduledTaskNow", "retryScheduledTaskRun", "startRecording"} | future_execution)
        self.assertEqual({name for name, method in METHODS.items() if method.execute}, {"runScheduledTaskNow", "retryScheduledTaskRun"} | future_execution)
        for name in ("createTask", "updateTask", "completeTask", "reopenTask", "snoozeTask", "archiveTask", "unarchiveTask", "createScheduledTask", "updateScheduledTask", "pauseScheduledTask", "resumeScheduledTask", "archiveScheduledTask", "runScheduledTaskNow", "retryScheduledTaskRun", "dismissReminder", "snoozeReminder", "startRecording", "stopRecording"):
            with self.subTest(name=name):
                self.assertTrue(METHODS[name].write)
        self.assertFalse(METHODS["searchMemory"].write)
        for name in ("pauseScheduledTask", "archiveScheduledTask"):
            with self.subTest(name=name):
                self.assertTrue(METHODS[name].write)
                self.assertFalse(METHODS[name].execute)
                self.assertFalse(METHODS[name].costly)

    def test_limits_dates_and_snooze_duration_rejected_when_invalid(self):
        for limit in (0, -1):
            self.assert_invalid("listOpenTasks", {"limit": limit})
        self.assert_invalid("listTasks", {"filter": {"scheduler_archived": 2}})
        for value in (0, -1, True, float("inf"), float("nan")):
            with self.subTest(duration=value):
                self.assert_invalid("snoozeReminder", {"id": 1, "durationMinutes": value})
        for value in ("2026/10/10", "2026-10-1", "", "today", 20261010):
            self.assert_invalid("getDailyAppUsage", {"date": value})

    def test_dates_require_real_calendar_days(self):
        for value in ("2026-13-01", "2026-00-01", "2026-02-29", "2026-04-31", "2026-10-00"):
            with self.subTest(date=value):
                self.assert_invalid("getDailyAppUsage", {"date": value})
                self.assert_invalid("getAppSessions", {"date": value})
                self.assert_invalid("getAppUsageRange", {"startDate": value, "endDate": "2026-10-10"})
                self.assert_invalid("getTopApps", {"startDate": "2026-10-10", "endDate": value})
        self.assertEqual(validate_params("getDailyAppUsage", {"date": "2024-02-29"}), ["2024-02-29"])
        self.assertEqual(METHODS["getDailyAppUsage"].schema["properties"]["date"].get("format"), "date")

    def test_schedule_timestamps_require_valid_iso8601_with_timezone(self):
        for value in (
            "garbage", "2026-10-10", "2026-10-10T09:30:00",
            "2026-13-01T09:30:00+08:00", "2026-02-29T09:30:00+08:00",
            "2026-10-10T24:30:00Z", "2026-10-10T09:60:00Z",
            "2026-10-10T09:30:00+24:00", "2026-10-10T09:30:00+08:99",
            "2026-10-10 09:30:00+08:00", "2026-10-10T09:30:00+0800",
        ):
            with self.subTest(timestamp=value):
                self.assert_invalid("updateScheduledTask", {"id": 1, "patch": {"start_at": value}})
                self.assert_invalid("updateScheduledTask", {"id": 1, "patch": {"end_at": value}})
                self.assert_invalid("createScheduledTask", {"schedule": {
                    "title": "Review", "instruction": "Read", "schedule_kind": "once",
                    "timezone": "Asia/Shanghai", "start_at": value,
                }})

    def test_valid_schedule_timestamps_and_formats(self):
        for value in (0, 1791595800000, "2026-10-10T09:30:00+08:00", "2026-10-10T01:30:00Z", "2026-10-10t01:30:00z", "2026-10-10T01:30:00.123-04:00"):
            with self.subTest(timestamp=value):
                self.assertEqual(validate_params("updateScheduledTask", {"id": 1, "patch": {"start_at": value, "end_at": value}}), [1, {"start_at": value, "end_at": value}])
        for field in ("start_at", "end_at"):
            schema = METHODS["updateScheduledTask"].schema["properties"]["patch"]["properties"][field]
            if field == "end_at":
                schema = schema["anyOf"][0]
            self.assertEqual(schema["anyOf"][1].get("format"), "date-time")


if __name__ == "__main__":
    unittest.main()
