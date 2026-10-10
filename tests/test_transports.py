# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 JunkaiWang-TheoPhy
"""CLI and MCP protocol tests use a fake backend; no live writes occur."""

import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from airjelly_bridge import cli, mcp
from airjelly_bridge.contracts import METHODS, validate_params
from airjelly_bridge.policy import Policy


class FakeClient:
    def __init__(self, runtime_path=None, policy=None, timeout=15.0, max_response_bytes=4194304):
        self.runtime_path = runtime_path
        self.policy = policy or Policy()
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.calls = []
        self.capability_reads = 0
        self.failure = None

    def doctor(self):
        return {"ok": True, "recording": "running"}

    def capabilities(self):
        self.capability_reads += 1
        return {"appVersion": "1.0.13", "methods": list(METHODS)}

    def methods(self):
        return [{"name": method.name, "group": method.group} for method in METHODS.values()]

    def call(self, method, params, *, dry_run=False, view=None):
        if self.failure:
            raise self.failure
        args = validate_params(method, params)
        self.policy.authorize(METHODS[method])
        call = {"method": method, "params": dict(params), "args": args,
                "dry_run": dry_run, "view": view}
        self.calls.append(call)
        return {"ok": True, "method": method, "data": {"params": params, "args": args},
                "meta": {"dry_run": dry_run}}


def request(method, params=None, *, identifier=1):
    result = {"jsonrpc": "2.0", "id": identifier, "method": method}
    if params is not None:
        result["params"] = params
    return result


def initialize(version="2025-06-18", *, identifier=1):
    return request("initialize", {"protocolVersion": version, "capabilities": {},
                                  "clientInfo": {"name": "test-client", "version": "1"}},
                   identifier=identifier)


def ready(server, version="2025-06-18"):
    server.handle(initialize(version))
    server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})


class CLITests(unittest.TestCase):
    def invoke(self, arguments, *, stdin=""):
        self.out, self.err = io.StringIO(), io.StringIO()
        self.clients = []

        def factory(**kwargs):
            client = FakeClient(**kwargs)
            self.clients.append(client)
            return client

        code = cli.main(arguments, stdin=io.StringIO(stdin), stdout=self.out, stderr=self.err,
                        client_factory=factory)
        return code, json.loads(self.out.getvalue()) if self.out.getvalue() else None

    def test_doctor_has_one_json_output(self):
        code, result = self.invoke(["doctor"])
        self.assertEqual(code, 0)
        self.assertEqual(result, {"ok": True, "recording": "running"})
        self.assertEqual(len(self.out.getvalue().splitlines()), 1)
        self.assertEqual(self.err.getvalue(), "")

    def test_methods_groups_can_appear_after_command(self):
        code, result = self.invoke(["methods", "--group", "events", "--group", "recording"])
        self.assertEqual(code, 0)
        self.assertEqual({item["group"] for item in result}, {"events", "recording"})
        self.assertEqual(self.clients[0].policy.groups, frozenset({"events", "recording"}))

    def test_configuration_before_and_after_command_is_combined(self):
        code, _ = self.invoke(["--allow-method", "getRecordingStatus", "recording", "status",
                               "--allow-method", "listEvents", "--runtime", "/fake/runtime",
                               "--timeout", "3", "--max-response-bytes", "2048"])
        self.assertEqual(code, 0)
        self.assertEqual(self.clients[0].runtime_path, "/fake/runtime")
        self.assertEqual(self.clients[0].timeout, 3)
        self.assertEqual(self.clients[0].max_response_bytes, 2048)
        self.assertEqual(self.clients[0].policy.allow_methods, frozenset({"getRecordingStatus", "listEvents"}))

    def test_every_native_method_has_a_dynamic_group_alias(self):
        parser = cli.build_parser()
        for method in METHODS.values():
            with self.subTest(method=method.name):
                args = parser.parse_args([method.group, cli._alias(method)])
                self.assertEqual(args.method, method.name)
                native = parser.parse_args([method.group, cli._snake_case(method.name)])
                self.assertEqual(native.method, method.name)

    def test_date_converts_shanghai_day_to_native_milliseconds(self):
        code, _ = self.invoke(["events", "list", "--date", "2026-10-09"])
        self.assertEqual(code, 0)
        params = self.clients[0].calls[0]["params"]
        self.assertEqual(params, {"startTimeMs": 1791475200000, "endTimeMs": 1791561600000})
        self.assertEqual(self.clients[0].calls[0]["args"], [1791475200000, 1791561600000])

    def test_explicit_range_supports_epoch_ms_and_timezone_timestamp(self):
        code, _ = self.invoke(["call", "listEvents", "--start", "1791475200000",
                               "--end", "2026-10-10T00:00:00+08:00"])
        self.assertEqual(code, 0)
        self.assertEqual(self.clients[0].calls[0]["params"]["endTimeMs"], 1791561600000)

    def test_date_flags_reject_conflicts_and_incomplete_ranges(self):
        cases = [
            ["events", "list", "--date", "today", "--start", "1", "--end", "2"],
            ["events", "list", "--start", "1"],
            ["events", "list", "--start", "2", "--end", "1"],
            ["events", "list", "--start", "2026-10-09T00:00:00", "--end", "2"],
            ["events", "list", "--date", "2026-02-30"],
            ["events", "list", "--date", "today", "--params", '{"startTimeMs": 1}'],
            ["call", "getRecordingStatus", "--date", "today"],
        ]
        for args in cases:
            with self.subTest(args=args):
                code, result = self.invoke(args)
                self.assertEqual(code, 2)
                self.assertFalse(result["ok"])
                self.assertEqual(self.clients[0].calls, [])

    def test_params_are_read_from_json_file_and_stdin(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "params.json"
            path.write_text('{"id": 42}', encoding="utf-8")
            for source, stdin in [("@" + str(path), ""), ("-", '{"id": 42}')]:
                with self.subTest(source=source):
                    code, _ = self.invoke(["tasks", "get", "--params", source], stdin=stdin)
                    self.assertEqual(code, 0)
                    self.assertEqual(self.clients[0].calls[0]["params"], {"id": 42})

    def test_view_flags_remain_separate_from_native_parameters(self):
        code, _ = self.invoke(["events", "list", "--date", "2026-10-09", "--dry-run", "--limit", "4",
                               "--offset", "2", "--fields", "id, title", "--app", "Codex",
                               "--window", "Draft", "--contains", "prompt", "--max-text-chars", "80"])
        self.assertEqual(code, 0)
        call = self.clients[0].calls[0]
        self.assertTrue(call["dry_run"])
        self.assertEqual(call["view"], {"limit": 4, "offset": 2, "fields": ["id", "title"],
                                         "app": "Codex", "window": "Draft", "contains": "prompt",
                                         "max_text_chars": 80})
        self.assertEqual(set(call["params"]), {"startTimeMs", "endTimeMs"})

    def test_default_policy_prevents_writes_and_explicit_flags_grant_only_that_process(self):
        code, result = self.invoke(["recording", "stop"])
        self.assertEqual(code, 3)
        self.assertEqual(result["error"]["code"], "policy_denied")
        self.assertEqual(self.clients[0].calls, [])
        code, _ = self.invoke(["recording", "stop", "--allow-write", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertTrue(self.clients[0].calls[0]["dry_run"])
        code, _ = self.invoke(["recording", "start", "--allow-write", "--dry-run"])
        self.assertEqual(code, 3)
        code, _ = self.invoke(["recording", "start", "--allow-write", "--allow-cost", "--dry-run"])
        self.assertEqual(code, 0)

    def test_bad_cli_inputs_produce_json_and_usage_exit(self):
        cases = [["nonsense"], ["call", "getTask", "--params", "[]"],
                 ["call", "getTask", "--params", "{bad}"], ["doctor", "--timeout", "nan"],
                 ["doctor", "--timeout", "121"], ["call", "getTask", "--params", '{"id": NaN}'],
                 ["recording", "status", "--limit", "0"], ["methods", "--group", "unknown"],
                 ["doctor", "--runtime"]]
        for args in cases:
            with self.subTest(args=args):
                code, result = self.invoke(args)
                self.assertEqual(code, 2)
                self.assertFalse(result["ok"])

    def test_mcp_setup_failure_never_emits_cli_json_on_stdout(self):
        code, result = self.invoke(["mcp", "--policy", "/definitely/missing-policy.json"])
        self.assertEqual(code, 2)
        self.assertIsNone(result)
        self.assertEqual(json.loads(self.err.getvalue())["error"]["code"], "invalid_policy")

    def test_cli_mcp_mode_uses_stdio_and_exits_at_eof(self):
        lines = "\n".join(json.dumps(item) for item in [initialize(),
                          {"jsonrpc": "2.0", "method": "notifications/initialized"},
                          request("ping", identifier=2)]) + "\n"
        # invoke() expects a single CLI JSON value, so call main directly here.
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(["mcp"], stdin=io.StringIO(lines), stdout=out, stderr=err, client_factory=FakeClient)
        self.assertEqual(code, 0)
        results = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual([item["id"] for item in results], [1, 2])
        self.assertEqual(err.getvalue(), "")


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.server = mcp.Server(self.client)

    def call(self, method, params=None, identifier=2):
        return self.server.handle(request(method, params, identifier=identifier))

    def test_ping_works_before_initialization_but_other_requests_wait(self):
        self.assertEqual(self.call("ping")["result"], {})
        self.assertEqual(self.call("tools/list")["error"]["code"], -32000)
        self.server.handle(initialize())
        self.assertEqual(self.call("tools/list")["error"]["code"], -32000)
        self.server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertIn("tools", self.call("tools/list")["result"])

    def test_initialization_negotiates_all_supported_versions_and_latest_fallback(self):
        for version in [*mcp.PROTOCOL_VERSIONS, "future-version"]:
            with self.subTest(version=version):
                server = mcp.Server(self.client)
                result = server.handle(initialize(version))["result"]
                self.assertEqual(result["protocolVersion"], version if version in mcp.PROTOCOL_VERSIONS else "2025-06-18")
                self.assertIn("tools", result["capabilities"])
                self.assertIn("resources", result["capabilities"])
        self.assertEqual(self.client.capability_reads, 0)

    def test_discovery_is_offline_and_all_tools_have_named_schemas(self):
        ready(self.server)
        result = self.call("tools/list")["result"]["tools"]
        self.assertEqual(len(result), 43)
        self.assertEqual({tool["name"] for tool in result}, {"airjelly_" + name for name in METHODS})
        self.assertEqual(self.client.capability_reads, 0)
        for tool in result:
            definition = METHODS[tool["name"][9:]]
            self.assertEqual(tool["inputSchema"]["required"], definition.schema["required"])
            self.assertEqual(tool["inputSchema"]["additionalProperties"], False)
            self.assertIn("_view", tool["inputSchema"]["properties"])
            self.assertIn("_dry_run", tool["inputSchema"]["properties"])
            self.assertEqual(tool["annotations"]["readOnlyHint"], not (definition.write or definition.execute))
            if definition.write or definition.costly or definition.execute:
                self.assertIn("explicit policy grants", tool["description"])
        self.assertNotIn("_view", METHODS["listEvents"].schema["properties"])

    def test_mcp_arguments_match_native_parameters_and_separate_view(self):
        ready(self.server)
        result = self.call("tools/call", {"name": "airjelly_listEvents", "arguments": {
            "startTimeMs": 10, "endTimeMs": 20, "_dry_run": True,
            "_view": {"limit": 2, "fields": ["id"]}}})["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["data"]["args"], [10, 20])
        self.assertEqual(json.loads(result["content"][0]["text"]), result["structuredContent"])
        self.assertEqual(self.client.calls[0]["params"], {"startTimeMs": 10, "endTimeMs": 20})
        self.assertEqual(self.client.calls[0]["view"], {"limit": 2, "fields": ["id"]})

    def test_execution_and_cost_denials_are_tool_errors_without_bypasses(self):
        ready(self.server)
        for name, arguments in [("stopRecording", {}), ("startRecording", {}),
                                ("searchMemory", {"query": "weekly work"}),
                                ("runScheduledTaskNow", {"id": 1})]:
            with self.subTest(name=name):
                result = self.call("tools/call", {"name": "airjelly_" + name, "arguments": arguments})["result"]
                self.assertTrue(result["isError"])
                self.assertEqual(result["structuredContent"]["error"]["code"], "policy_denied")
        self.assertEqual(self.client.calls, [])
        result = self.call("tools/call", {"name": "airjelly_stopRecording", "arguments": {"allow_write": True}})
        self.assertEqual(result["error"]["code"], -32602)

    def test_grants_still_respect_allowlist_and_groups(self):
        self.client.policy = Policy(allow_write=True, allow_cost=True, allow_execute=True,
                                    allow_methods=frozenset({"getRecordingStatus"}))
        ready(self.server)
        result = self.call("tools/call", {"name": "airjelly_stopRecording"})["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["error"]["details"]["gate"], "method")

    def test_validation_errors_and_unknown_tool_are_protocol_errors(self):
        ready(self.server)
        cases = [
            {"name": "airjelly_nonexistent"}, {"name": "getRecordingStatus"},
            {"name": "airjelly_getTask", "arguments": {}},
            {"name": "airjelly_getTask", "arguments": {"id": True}},
            {"name": "airjelly_getTask", "arguments": []},
            {"name": "airjelly_getTask", "arguments": {"id": 1, "_dry_run": "false"}},
            {"name": "airjelly_getTask", "arguments": {"id": 1, "_view": {"allow_write": True}}},
            {"name": "airjelly_getTask", "arguments": {"id": 1, "_view": {"limit": True}}},
            {"name": "airjelly_getTask", "arguments": {"id": 1, "_view": {"max_text_chars": 0}}},
        ]
        for params in cases:
            with self.subTest(params=params):
                self.assertEqual(self.call("tools/call", params)["error"]["code"], -32602)
        self.assertEqual(self.client.calls, [])

    def test_unknown_protocol_method_and_unknown_resource_have_standard_errors(self):
        ready(self.server)
        self.assertEqual(self.call("not/a/method")["error"]["code"], -32601)
        self.assertEqual(self.call("resources/read", {"uri": "file:///private/runtime"})["error"]["code"], -32002)

    def test_resources_only_expose_static_contracts_and_sanitized_metadata(self):
        ready(self.server)
        resources = self.call("resources/list")["result"]["resources"]
        self.assertEqual(len(resources), 3)
        for resource in resources:
            result = self.call("resources/read", {"uri": resource["uri"]})["result"]["contents"]
            self.assertEqual(result[0]["uri"], resource["uri"])
            self.assertEqual(result[0]["mimeType"], "application/json")
            self.assertIsInstance(json.loads(result[0]["text"]), dict)
        self.assertEqual(self.client.calls, [])
        self.assertEqual(self.call("resources/templates/list")["result"], {"resourceTemplates": []})

    def test_protocol_meta_is_accepted_but_not_forwarded(self):
        ready(self.server)
        result = self.call("tools/call", {"name": "airjelly_getRecordingStatus",
                                          "_meta": {"progressToken": "p1"}})
        self.assertIn("result", result)
        self.assertEqual(self.client.calls[0]["params"], {})

    def test_notifications_do_not_produce_responses_or_execute_tools(self):
        ready(self.server)
        for message in [
            {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}},
            {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "airjelly_stopRecording"}},
            {"jsonrpc": "2.0", "method": "unknown/notification"},
            {"jsonrpc": "2.0", "id": 88, "result": {}},
        ]:
            self.assertIsNone(self.server.handle(message))
        self.assertEqual(self.client.calls, [])

    def test_invalid_envelopes_and_initialization_are_rejected(self):
        cases = [None, [], "text", {"method": "ping"}, {"jsonrpc": "2.0", "method": 1},
                 {"jsonrpc": "2.0", "id": None, "method": "ping"},
                 {"jsonrpc": "2.0", "id": True, "method": "ping"},
                 {"jsonrpc": "2.0", "id": 1, "method": "ping", "result": {}},
                 request("initialize", {"protocolVersion": "2025-06-18"}),
                 request("initialize", {"protocolVersion": "2025-06-18", "capabilities": [],
                                        "clientInfo": {"name": "test", "version": "1"}}),
                 request("notifications/initialized")]
        for message in cases:
            with self.subTest(message=message):
                response = self.server.handle(message)
                self.assertIn("error", response)
        self.server.handle(initialize())
        self.assertIn("error", self.server.handle(initialize(identifier=2)))

    def test_older_versions_omit_unsupported_result_extensions(self):
        for version in mcp.PROTOCOL_VERSIONS[:2]:
            with self.subTest(version=version):
                server = mcp.Server(self.client)
                ready(server, version)
                result = server.handle(request("tools/call", {"name": "airjelly_getRecordingStatus"}, identifier=2))["result"]
                self.assertNotIn("structuredContent", result)
                tools = server.handle(request("tools/list", identifier=3))["result"]["tools"]
                if version == "2024-11-05":
                    self.assertNotIn("annotations", tools[0])

    def test_older_protocol_batch_requests_are_supported_and_newest_rejects_them(self):
        ready(self.server, "2025-03-26")
        batch = [request("ping", identifier=2), {"jsonrpc": "2.0", "method": "unknown/notification"},
                 request("tools/call", {"name": "airjelly_getRecordingStatus"}, identifier=3)]
        responses = self.server.handle(batch)
        self.assertEqual([item["id"] for item in responses], [2, 3])
        newest = mcp.Server(self.client)
        ready(newest)
        self.assertEqual(newest.handle(batch)["error"]["code"], -32600)

    def test_unexpected_backend_exception_is_sanitized(self):
        ready(self.server)
        self.client.failure = RuntimeError("Bearer TOP-SECRET-TOKEN from private path")
        result = self.call("tools/call", {"name": "airjelly_getRecordingStatus"})
        self.assertEqual(result["error"]["code"], -32603)
        self.assertNotIn("TOP-SECRET", json.dumps(result))

    def test_stream_recovers_after_bad_utf8_bad_json_and_oversized_requests(self):
        stream = io.BytesIO(b"\xff\n{bad}\n" + b"x" * 500 + b"\n"
                            + json.dumps(request("ping", identifier="after-errors")).encode() + b"\n")
        output = io.StringIO()
        code = mcp.run(self.client, input_stream=stream, output_stream=output, max_request_bytes=100)
        self.assertEqual(code, 0)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([item.get("error", {}).get("code") for item in responses[:3]], [-32700, -32700, -32600])
        self.assertEqual(responses[3]["id"], "after-errors")
        self.assertEqual(responses[3]["result"], {})

    def test_empty_input_and_binary_output_exit_cleanly(self):
        self.assertEqual(mcp.run(self.client, input_stream=io.BytesIO(), output_stream=io.BytesIO()), 0)
        output = io.BytesIO()
        self.assertEqual(mcp.run(self.client, input_stream=io.BytesIO(b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n'),
                                 output_stream=output), 0)
        self.assertEqual(json.loads(output.getvalue())["result"], {})

    def test_real_entrypoints_do_not_need_an_online_application_for_discovery(self):
        root = Path(__file__).resolve().parents[1]
        messages = "\n".join(json.dumps(item) for item in [initialize(),
                             {"jsonrpc": "2.0", "method": "notifications/initialized"},
                             request("tools/list", identifier=2)]) + "\n"
        for command in [[sys.executable, "-m", "airjelly_bridge", "--runtime", "/missing/runtime.json", "mcp"],
                        [sys.executable, str(root / "bin/airjelly"), "--runtime", "/missing/runtime.json", "mcp"]]:
            with self.subTest(command=command):
                process = subprocess.run(command, input=messages, capture_output=True, text=True,
                                         cwd=root, timeout=5)
                self.assertEqual(process.returncode, 0, process.stderr)
                responses = [json.loads(line) for line in process.stdout.splitlines()]
                self.assertEqual([item["id"] for item in responses], [1, 2])
                self.assertEqual(len(responses[1]["result"]["tools"]), 43)
                self.assertEqual(process.stderr, "")


if __name__ == "__main__":
    unittest.main()
