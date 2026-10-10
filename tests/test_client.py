# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 JunkaiWang-TheoPhy
"""Transport and policy boundaries, exercised against synthetic loopback data."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from airjelly_bridge.client import Client
from airjelly_bridge.contracts import METHODS
from airjelly_bridge.errors import BridgeError
from airjelly_bridge.policy import Policy


VERSION = "1.0.13"
TOKEN = "test-runtime-secret-0123456789"
DAY = 86400000

# Handwritten public-signature examples catch accidental positional reordering.
CASES = {
    "listEvents": ({"endTimeMs": DAY, "startTimeMs": 0}, [0, DAY]),
    "getTask": ({"id": 7}, [7]),
    "listTasks": ({"filter": {"status": ["open"], "limit": 4}}, [{"status": ["open"], "limit": 4}]),
    "listOpenTasks": ({"limit": 4}, [4]),
    "getTaskMemories": ({"taskId": "task-7"}, ["task-7"]),
    "createTask": ({"task": {"title": "Synthetic task", "description": "fixture"}}, [{"title": "Synthetic task", "description": "fixture"}]),
    "updateTask": ({"patch": {"title": "Revised fixture", "next_steps": ["read"]}, "id": 7}, [7, {"title": "Revised fixture", "next_steps": ["read"]}]),
    "completeTask": ({"id": 7}, [7]),
    "reopenTask": ({"id": 7}, [7]),
    "archiveTask": ({"id": 7}, [7]),
    "unarchiveTask": ({"id": 7}, [7]),
    "snoozeTask": ({"untilMs": DAY, "id": 7}, [7, DAY]),
    "createScheduledTask": ({"schedule": {"title": "Synthetic schedule", "instruction": "fixture only", "schedule_kind": "once", "timezone": "Asia/Shanghai", "start_at": DAY}}, [{"title": "Synthetic schedule", "instruction": "fixture only", "schedule_kind": "once", "timezone": "Asia/Shanghai", "start_at": DAY}]),
    "listScheduledTasks": ({"filter": {"include_archived": False}}, [{"include_archived": False}]),
    "getScheduledTask": ({"id": 8}, [8]),
    "updateScheduledTask": ({"patch": {"title": "Fixture revision"}, "id": 8}, [8, {"title": "Fixture revision"}]),
    "pauseScheduledTask": ({"id": 8}, [8]),
    "resumeScheduledTask": ({"id": 8}, [8]),
    "archiveScheduledTask": ({"id": 8}, [8]),
    "listScheduledTaskRuns": ({"limit": 4, "scheduledTaskId": 8}, [8, 4]),
    "listScheduledTaskUpcomingOccurrences": ({"filter": {"start_ms": 0, "end_ms": DAY}}, [{"start_ms": 0, "end_ms": DAY}]),
    "listScheduledTaskRunHistory": ({"filter": {"scheduled_task_id": 8, "limit": 4}}, [{"scheduled_task_id": 8, "limit": 4}]),
    "getScheduledTaskOverview": ({"options": {"upcoming_limit": 4, "history_limit": 4}}, [{"upcoming_limit": 4, "history_limit": 4}]),
    "runScheduledTaskNow": ({"id": 8}, [8]),
    "retryScheduledTaskRun": ({"runId": 9}, [9]),
    "searchMemory": ({"filter": {"app_name": "Fixture"}, "query": "synthetic"}, ["synthetic", {"app_name": "Fixture"}]),
    "listMemories": ({"filter": {"memory_types": ["event"], "limit": 4}}, [{"memory_types": ["event"], "limit": 4}]),
    "getMemory": ({"id": 10}, [10]),
    "resolveScreenshotPaths": ({"ids": [10, "shot-11"]}, [[10, "shot-11"]]),
    "listPersons": ({}, []),
    "getEventsForEntity": ({"entityId": 12}, [12]),
    "getDailyAppUsage": ({"date": "2026-10-10"}, ["2026-10-10"]),
    "getAppUsageRange": ({"endDate": "2026-10-10", "startDate": "2026-10-09"}, ["2026-10-09", "2026-10-10"]),
    "getTopApps": ({"limit": 4, "endDate": "2026-10-10", "startDate": "2026-10-09"}, ["2026-10-09", "2026-10-10", 4]),
    "getAppSessions": ({"date": "2026-10-10"}, ["2026-10-10"]),
    "getAppIcons": ({"appNames": ["Fixture", "Synthetic"]}, [["Fixture", "Synthetic"]]),
    "dismissReminder": ({"id": 13}, [13]),
    "snoozeReminder": ({"durationMinutes": 2.5, "id": 13}, [13, 2.5]),
    "getRecordingStatus": ({}, []),
    "getRecordingPermissions": ({}, []),
    "getRecordingStats": ({}, []),
    "startRecording": ({}, []),
    "stopRecording": ({}, []),
}


class LoopbackFixture:
    """In-memory fake AirJelly, never connected to the installed application."""

    def __init__(self, token=TOKEN):
        self.token = token
        self.requests = []
        self.responses = {}
        self.rpc_data = {"fixture": True}
        self.drop_rpc = False
        self.rpc_wait = None
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.handle_api()

            def do_POST(self):
                self.handle_api()

            def handle_api(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                body = json.loads(raw) if raw else None
                fixture.requests.append({"path": self.path, "body": body, "headers": dict(self.headers)})
                if self.path == "/rpc" and fixture.rpc_wait is not None:
                    fixture.rpc_wait.wait(2)
                if self.path == "/rpc" and fixture.drop_rpc:
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                if self.path in fixture.responses:
                    status, result, headers = fixture.responses[self.path]
                elif self.path == "/health":
                    status, result, headers = 200, {"ok": True, "version": VERSION}, {}
                elif self.path == "/capabilities":
                    status, result, headers = 200, {"ok": True, "data": {"appVersion": VERSION, "apiVersion": "1", "methods": list(METHODS)}}, {}
                elif self.path == "/rpc" and self.headers.get("Authorization") == "Bearer " + fixture.token:
                    status, result, headers = 200, {"ok": True, "data": fixture.rpc_data}, {}
                else:
                    status, result, headers = 401, {"ok": False, "error": "fixture authorization failure"}, {}
                response = result if isinstance(result, bytes) else json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                for name, value in headers.items():
                    self.send_header(name, value)
                self.end_headers()
                try:
                    self.wfile.write(response)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()

    def close(self):
        if self.rpc_wait is not None:
            self.rpc_wait.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    @property
    def rpc_requests(self):
        return [request for request in self.requests if request["path"] == "/rpc"]


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="airjelly-test-")
        self.addCleanup(self.directory.cleanup)
        self.runtime = Path(self.directory.name) / "runtime.json"
        self.server = LoopbackFixture()
        self.addCleanup(self.server.close)
        self.write_runtime()
        self.client = Client(self.runtime)

    def write_runtime(self, server=None, **overrides):
        server = self.server if server is None else server
        descriptor = {"pid": os.getpid(), "port": server.port, "token": server.token, "version": VERSION}
        descriptor.update(overrides)
        self.runtime.write_text(json.dumps(descriptor), encoding="utf-8")
        self.runtime.chmod(0o600)

    def assert_error(self, code, callback):
        with self.assertRaises(BridgeError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_all_43_contracts_send_exact_authenticated_positional_args(self):
        self.assertEqual(len(CASES), 43)
        self.assertEqual(set(CASES), set(METHODS))
        client = Client(self.runtime, Policy(allow_write=True, allow_cost=True, allow_execute=True))
        for method, (params, expected_args) in CASES.items():
            with self.subTest(method=method):
                original = deepcopy(params)
                self.assertEqual(METHODS[method].to_args(params), expected_args)
                result = client.call(method, params)
                self.assertTrue(result["ok"])
                request = self.server.rpc_requests[-1]
                self.assertEqual(request["body"], {"method": method, "args": expected_args})
                self.assertEqual(request["headers"]["Authorization"], "Bearer " + TOKEN)
                self.assertEqual(params, original)
        self.assertEqual(len(self.server.rpc_requests), 43)

    def test_optional_arguments_are_omitted_without_synthetic_defaults(self):
        cases = {"listTasks": ({}, []), "listOpenTasks": ({}, []), "listScheduledTaskRuns": ({"scheduledTaskId": 8}, [8]), "getTopApps": ({"startDate": "2026-10-09", "endDate": "2026-10-10"}, ["2026-10-09", "2026-10-10"]), "searchMemory": ({"query": "fixture"}, ["fixture"])}
        client = Client(self.runtime, Policy(allow_cost=True))
        for method, (params, expected) in cases.items():
            with self.subTest(method=method):
                client.call(method, params)
                self.assertEqual(self.server.rpc_requests[-1]["body"]["args"], expected)

    def test_default_denies_all_side_effects_before_network_access(self):
        for name, method in METHODS.items():
            if method.write or method.costly or method.execute:
                with self.subTest(method=name):
                    self.assert_error("policy_denied", lambda: self.client.call(name, CASES[name][0]))
        self.assertEqual(self.server.requests, [])

    def test_all_execution_gates_are_required_independently(self):
        for flags, gate in (({}, "write"), ({"allow_write": True}, "cost"), ({"allow_write": True, "allow_cost": True}, "execute")):
            with self.subTest(gate=gate):
                client = Client(self.runtime, Policy(**flags))
                error = self.assert_error("policy_denied", lambda: client.call("runScheduledTaskNow", {"id": 8}))
                self.assertEqual(error.details["gate"], gate)
        self.assertEqual(self.server.requests, [])

    def test_dry_run_does_not_read_runtime_or_send_any_http_request(self):
        self.runtime.unlink()
        client = Client(self.runtime, Policy(allow_write=True))
        result = client.call("updateTask", {"id": 7, "patch": {"title": "fixture"}}, dry_run=True)
        self.assertTrue(result["meta"]["dry_run"])
        self.assertEqual(result["data"]["args"], [7, {"title": "fixture"}])
        self.assertEqual(self.server.requests, [])

    def test_dry_run_still_enforces_policy_and_schema(self):
        self.assert_error("policy_denied", lambda: self.client.call("stopRecording", {}, dry_run=True))
        self.assert_error("invalid_params", lambda: self.client.call("getTask", {"id": True}, dry_run=True))
        self.assertEqual(self.server.requests, [])

    def test_invalid_contract_input_never_reaches_http(self):
        cases = [("getTask", {}), ("getTask", {"id": True}), ("getTask", {"id": 0}), ("getTask", {"id": " "}), ("getTask", {"id": 1, "token": TOKEN}), ("getRecordingStatus", {"force": True}), ("listTasks", {"filter": {"limit": True}}), ("listTasks", {"filter": {"status": {"sql": "fixture"}}}), ("updateTask", {"id": 1, "patch": {"status": "done"}}), ("updateTask", {"id": 1, "patch": {"next_steps": "fixture"}}), ("getAppIcons", {"appNames": [1]}), ("getTask", [1])]
        client = Client(self.runtime, Policy(allow_write=True))
        for method, params in cases:
            with self.subTest(method=method, params=params):
                self.assert_error("invalid_params", lambda: client.call(method, params))
        self.assertEqual(self.server.requests, [])

    def test_api_token_is_only_sent_to_rpc_and_never_logged_or_in_doctor(self):
        self.server.responses["/health"] = (200, {"ok": True, "version": VERSION, "token": TOKEN, "runtime": str(self.runtime)}, {})
        self.server.responses["/capabilities"] = (200, {"ok": True, "data": {"appVersion": VERSION, "apiVersion": "1", "methods": list(METHODS), "token": TOKEN, "runtime": str(self.runtime), "pid": os.getpid()}}, {})
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            doctor = self.client.doctor()
            capabilities = self.client.capabilities()
            result = self.client.call("getRecordingStatus", {})
        printable = json.dumps([doctor, capabilities, result], ensure_ascii=False) + output.getvalue()
        self.assertNotIn(TOKEN, printable)
        self.assertNotIn(str(self.runtime), printable)
        self.assertNotIn('"pid"', printable)
        for request in self.server.requests:
            self.assertEqual(request["headers"].get("Authorization"), "Bearer " + TOKEN if request["path"] == "/rpc" else None)

    def test_proxy_environment_cannot_intercept_loopback_authentication(self):
        proxy = LoopbackFixture()
        self.addCleanup(proxy.close)
        url = f"http://127.0.0.1:{proxy.port}"
        with patch.dict(os.environ, {"http_proxy": url, "HTTP_PROXY": url, "https_proxy": url, "HTTPS_PROXY": url, "all_proxy": url, "ALL_PROXY": url, "NO_PROXY": "", "no_proxy": ""}):
            Client(self.runtime).call("getRecordingStatus", {})
        self.assertEqual(proxy.requests, [])
        self.assertEqual(len(self.server.rpc_requests), 1)

    def test_redirects_never_forward_credentials_to_another_server(self):
        destination = LoopbackFixture()
        self.addCleanup(destination.close)
        for endpoint in ("/health", "/rpc"):
            with self.subTest(endpoint=endpoint):
                self.server.responses[endpoint] = (307, b"", {"Location": f"http://127.0.0.1:{destination.port}/stolen"})
                self.assert_error("unsafe_redirect", lambda: self.client.call("getRecordingStatus", {}))
                del self.server.responses[endpoint]
        self.assertEqual(destination.requests, [])

    def test_each_call_rereads_rotated_runtime_port_and_token(self):
        self.client.call("getRecordingStatus", {})
        replacement = LoopbackFixture(token="rotated-test-runtime-secret")
        self.addCleanup(replacement.close)
        self.write_runtime(replacement)
        self.client.call("getRecordingStatus", {})
        self.assertEqual(len(self.server.rpc_requests), 1)
        self.assertEqual(len(replacement.rpc_requests), 1)
        self.assertEqual(replacement.rpc_requests[0]["headers"]["Authorization"], "Bearer " + replacement.token)

    def test_write_timeout_has_unknown_outcome_without_automatic_retry(self):
        self.server.rpc_wait = threading.Event()
        client = Client(self.runtime, Policy(allow_write=True), timeout=0.1)
        error = self.assert_error("outcome_unknown", lambda: client.call("completeTask", {"id": 7}))
        self.server.rpc_wait.set()
        self.assertEqual(len(self.server.rpc_requests), 1)
        self.assertIn("reconcile", error.message.lower())
        self.assertNotIn(TOKEN, json.dumps(error.as_dict()))

    def test_read_connection_drop_has_structured_error_without_retry(self):
        self.server.drop_rpc = True
        self.assert_error("connection_failed", lambda: self.client.call("getRecordingStatus", {}))
        self.assertEqual(len(self.server.rpc_requests), 1)

    def test_backend_errors_do_not_reveal_private_response_text(self):
        secret = TOKEN + " private fixture /Users/fixture/person"
        cases = [(500, {"ok": False, "error": secret}, "upstream_http_error"), (200, {"ok": False, "error": secret}, "upstream_error"), (200, (secret + " not JSON").encode(), "connection_failed"), (200, [secret], "upstream_error")]
        for status, body, code in cases:
            with self.subTest(status=status, code=code):
                self.server.responses["/rpc"] = (status, body, {})
                error = self.assert_error(code, lambda: self.client.call("getRecordingStatus", {}))
                self.assertNotIn(secret, json.dumps(error.as_dict()))
                self.assertNotIn(TOKEN, str(error))
                if status == 500:
                    self.assertEqual(error.details, {"http_status": 500})

    def test_response_byte_limit_rejects_oversized_rpc_body(self):
        self.server.rpc_data = "x" * 4096
        client = Client(self.runtime, max_response_bytes=2048)
        self.assert_error("response_too_large", lambda: client.call("getRecordingStatus", {}))

    def test_invalid_response_byte_limits_are_rejected_at_construction(self):
        for value in (0, -1, True, "4096", 1.5):
            with self.subTest(value=value):
                self.assert_error("invalid_params", lambda: Client(self.runtime, max_response_bytes=value))

    def test_oversized_request_is_rejected_before_rpc_send(self):
        client = Client(self.runtime, Policy(allow_write=True))
        self.assert_error("invalid_params", lambda: client.call("updateTask", {"id": 7, "patch": {"description": "x" * (1024 * 1024)}}))
        self.assertEqual(self.server.rpc_requests, [])

    def test_invalid_timeouts_are_rejected(self):
        for value in (0, -1, True, 121, "15", float("nan"), float("inf")):
            with self.subTest(value=value):
                self.assert_error("invalid_params", lambda: Client(self.runtime, timeout=value))

    def test_health_and_capability_versions_must_match_runtime(self):
        for endpoint, body in (("/health", {"ok": True, "version": "2.0.3"}), ("/capabilities", {"ok": True, "data": {"appVersion": "2.0.3", "apiVersion": "1", "methods": list(METHODS)}})):
            with self.subTest(endpoint=endpoint):
                self.server.responses[endpoint] = (200, body, {})
                self.assert_error("runtime_mismatch", lambda: self.client.call("getRecordingStatus", {}))
                del self.server.responses[endpoint]
        self.assertEqual(self.server.rpc_requests, [])

    def test_missing_runtime_version_does_not_authenticate_unidentified_service(self):
        self.write_runtime(version=None)
        self.server.responses["/health"] = (200, {"ok": True}, {})
        self.server.responses["/capabilities"] = (200, {"ok": True, "data": {"apiVersion": "1", "methods": list(METHODS)}}, {})
        with self.assertRaises(BridgeError):
            self.client.call("getRecordingStatus", {})
        self.assertEqual(self.server.rpc_requests, [])

    def test_invalid_capability_shapes_return_structured_errors(self):
        for data in (None, [], {"appVersion": VERSION, "apiVersion": "2", "methods": list(METHODS)}, {"appVersion": VERSION, "apiVersion": "1", "methods": [None]}, {"appVersion": VERSION, "apiVersion": "1", "methods": [{}]}, {"appVersion": VERSION, "apiVersion": "1", "methods": [TOKEN]}):
            with self.subTest(data=data):
                self.server.responses["/capabilities"] = (200, {"ok": True, "data": data}, {})
                with self.assertRaises(BridgeError):
                    self.client.doctor()
        self.assertEqual(self.server.rpc_requests, [])

    def test_missing_live_method_is_rejected_before_rpc_send(self):
        self.server.responses["/capabilities"] = (200, {"ok": True, "data": {"appVersion": VERSION, "apiVersion": "1", "methods": ["listPersons"]}}, {})
        self.assert_error("unsupported_method", lambda: self.client.call("getRecordingStatus", {}))
        self.assertEqual(self.server.rpc_requests, [])

    def test_doctor_reports_capability_difference_and_catalog_has_policy_flags(self):
        self.server.responses["/capabilities"] = (200, {"ok": True, "data": {"appVersion": VERSION, "apiVersion": "1", "methods": ["getRecordingStatus", "newPublicMethod"]}}, {})
        doctor = self.client.doctor()
        self.assertEqual(doctor["known_method_count"], 43)
        self.assertEqual(doctor["live_method_count"], 2)
        self.assertEqual(doctor["unknown_methods"], ["newPublicMethod"])
        self.assertIn("getTask", doctor["missing_methods"])
        catalog = {method["name"]: method for method in self.client.methods()}
        self.assertTrue(catalog["getRecordingStatus"]["available"])
        self.assertFalse(catalog["getTask"]["available"])
        self.assertFalse(catalog["startRecording"]["allowed"])
        self.assertFalse(catalog["searchMemory"]["allowed"])

    def test_runtime_permissions_symlink_and_stale_pid_are_rejected(self):
        self.runtime.chmod(0o644)
        self.assert_error("unsafe_runtime", self.client.doctor)
        self.runtime.chmod(0o600)
        target = self.runtime.with_name("private-runtime.json")
        self.runtime.rename(target)
        self.runtime.symlink_to(target)
        self.assert_error("unsafe_runtime", self.client.doctor)
        self.runtime.unlink()
        target.rename(self.runtime)
        self.write_runtime(pid=2147483647)
        self.assert_error("invalid_runtime", self.client.doctor)
        self.assertEqual(self.server.requests, [])

    def test_invalid_runtime_types_and_contents_are_rejected_before_http(self):
        for update in ({"port": True}, {"port": 0}, {"port": 65536}, {"pid": True}, {"pid": -1}, {"token": ""}, {"token": 1}):
            with self.subTest(update=update):
                self.write_runtime(**update)
                self.assert_error("invalid_runtime", self.client.doctor)
        for content in ("[]", "null", "invalid " + TOKEN, "x" * 65537):
            with self.subTest(size=len(content)):
                self.runtime.write_text(content)
                self.assert_error("invalid_runtime", self.client.doctor)
        self.assertEqual(self.server.requests, [])

    def test_time_ranges_and_nested_limits_are_denied_before_http(self):
        cases = [
            ("listEvents", {"startTimeMs": 0, "endTimeMs": 8 * DAY}),
            ("listEvents", {"startTimeMs": DAY, "endTimeMs": 0}),
            ("getAppUsageRange", {"startDate": "2026-10-01", "endDate": "2026-10-10"}),
            ("getAppUsageRange", {"startDate": "2026-10-10", "endDate": "2026-10-09"}),
            ("listTasks", {"filter": {"start_time_after": 0, "start_time_before": 8 * DAY}}),
            ("listTasks", {"filter": {"last_active_at_after": 0, "last_active_at_before": 8 * DAY}}),
            ("listTasks", {"filter": {"updated_at_after": 0, "updated_at_before": 8 * DAY}}),
            ("listScheduledTasks", {"filter": {"next_run_at_after": 0, "next_run_at_before": 8 * DAY}}),
            ("listScheduledTaskUpcomingOccurrences", {"filter": {"start_ms": 0, "end_ms": 8 * DAY}}),
            ("listScheduledTaskRunHistory", {"filter": {"occurrence_at_after": 0, "occurrence_at_before": 8 * DAY}}),
            ("getScheduledTaskOverview", {"options": {"upcoming_start_ms": 0, "upcoming_end_ms": 8 * DAY}}),
            ("listMemories", {"filter": {"limit": 201}}),
            ("getScheduledTaskOverview", {"options": {"upcoming_limit": 201}}),
        ]
        for name, params in cases:
            with self.subTest(method=name, params=params):
                self.assert_error("policy_denied", lambda: self.client.call(name, params))
        self.assertEqual(self.server.requests, [])

    def test_exact_maximum_date_span_is_allowed(self):
        self.client.call("listEvents", {"startTimeMs": 0, "endTimeMs": 7 * DAY})
        self.client.call("getAppUsageRange", {"startDate": "2026-10-01", "endDate": "2026-10-08"})
        self.assertEqual(len(self.server.rpc_requests), 2)

    def test_filter_then_paginate_then_project_fields_with_accurate_metadata(self):
        self.server.rpc_data = [
            {"id": 0, "app_name": "Other", "window_name": "Inbox", "text": "needle"},
            {"id": 1, "app_name": "Fixture", "window_name": "Other", "text": "needle"},
            {"id": 2, "app_name": "Fixture", "window_name": "Inbox", "text": "hay"},
            {"id": 3, "app_name": "FIXTURE", "window_name": "INBOX", "text": "NEEDLE", "details": {"source": "first"}},
            {"id": 4, "app_name": "Fixture", "window_name": "Inbox", "text": "needle", "details": {"source": "second"}},
            {"id": 5, "app_name": "Fixture", "window_name": "Inbox", "text": "needle", "details": {"source": "third"}},
        ]
        result = self.client.call("listEvents", {"startTimeMs": 0, "endTimeMs": DAY}, view={"app": "fixture", "window": "inbox", "contains": "Needle", "offset": 1, "limit": 1, "fields": ["id", "details.source", "missing"]})
        self.assertEqual(result["data"], [{"id": 4, "details.source": "second"}])
        self.assertEqual(result["meta"]["backend_batch_count"], 6)
        self.assertEqual(result["meta"]["filtered_count"], 3)
        self.assertEqual(result["meta"]["returned_count"], 1)
        self.assertTrue(result["meta"]["has_more_in_batch"])
        self.assertEqual(result["meta"]["pagination_scope"], "returned_backend_batch")
        self.assertEqual(self.server.rpc_requests[-1]["body"]["args"], [0, DAY])

    def test_output_text_caps_nested_items_and_secret_redaction(self):
        self.server.rpc_data = {"token": TOKEN, "nested": {"api_key": "synthetic-key", "text": "prefix " + TOKEN + " suffix", "credential": "Bearer synthetic-secret-0123456789"}, "long": "abcdefghijklmnopqrstuvwxyz", "items": list(range(8))}
        client = Client(self.runtime, Policy(max_items=3, max_text_chars=30))
        result = client.call("getMemory", {"id": 10}, view={"max_text_chars": 12})
        serialized = json.dumps(result["data"])
        self.assertNotIn(TOKEN, serialized)
        self.assertNotIn("synthetic-key", serialized)
        self.assertNotIn("synthetic-secret", serialized)
        self.assertEqual(result["data"]["token"], "[REDACTED]")
        self.assertEqual(result["data"]["long"], "abcdefghijkl…[truncated]")
        self.assertEqual(result["data"]["items"], [0, 1, 2])

    def test_runtime_token_is_scrubbed_even_when_user_disables_general_redaction(self):
        self.server.rpc_data = {"text": TOKEN, "password": "fixture-password"}
        result = Client(self.runtime, Policy(redact=False)).call("getMemory", {"id": 10})
        self.assertEqual(result["data"], {"text": "[REDACTED]", "password": "fixture-password"})

    def test_dict_field_projection_does_not_keep_unrequested_private_fields(self):
        self.server.rpc_data = {"id": 10, "text": "private fixture", "nested": {"value": 3}}
        result = self.client.call("getMemory", {"id": 10}, view={"fields": ["id", "nested.value"]})
        self.assertEqual(result["data"], {"id": 10, "nested.value": 3})

    def test_invalid_output_controls_never_reach_http(self):
        views = [{"limit": True}, {"limit": 0}, {"limit": 201}, {"offset": -1}, {"offset": 100001}, {"max_text_chars": 0}, {"max_text_chars": 2001}, {"fields": "id"}, {"fields": [""]}, {"fields": [1]}, {"app": 1}, {"window": None}, {"contains": False}, {"raw": True}, []]
        for view in views:
            with self.subTest(view=view):
                self.assert_error("invalid_params", lambda: self.client.call("getRecordingStatus", {}, view=view))
        self.assertEqual(self.server.requests, [])


if __name__ == "__main__":
    unittest.main()
