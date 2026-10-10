# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 JunkaiWang-TheoPhy
"""JSON command-line interface for the local AirJelly API."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import __version__
from .client import Client
from .contracts import METHODS
from .errors import BridgeError
from .policy import Policy

MAX_PARAMS_BYTES = 1_048_576
LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")

_GLOBAL_VALUES = {
    "--runtime", "--policy", "--timeout", "--max-response-bytes",
    "--allow-method", "--deny-method", "--group",
}
_GLOBAL_SWITCHES = {"--allow-write", "--allow-cost", "--allow-execute"}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise BridgeError("usage", message)


def _global_options_first(argv):
    """Accept configuration flags before or after any subcommand."""
    options, remaining = [], []
    iterator = iter(argv)
    for token in iterator:
        if token == "--":
            remaining.append(token)
            remaining.extend(iterator)
            break
        name = token.split("=", 1)[0]
        if name in _GLOBAL_SWITCHES:
            options.append(token)
        elif name in _GLOBAL_VALUES:
            options.append(token)
            if "=" not in token:
                value = next(iterator, None)
                if value is None:
                    raise BridgeError("usage", f"{name} requires a value")
                options.append(value)
        else:
            remaining.append(token)
    return options + remaining


def _snake_case(value):
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", value)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).lower()


def _alias(method):
    words = _snake_case(method.name).split("_")
    singular = method.group[:-3] + "y" if method.group.endswith("ies") else method.group.removesuffix("s")
    group_words = {method.group, singular}
    if method.group == "schedules":
        group_words.update({"scheduled", "task", "tasks"})
    words = [word for word in words if word not in group_words]
    if len(words) > 1 and words[0] == "get":
        words.pop(0)
    return "_".join(words) or "get"


def _nonnegative(value):
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer") from None
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return parsed


def _positive(value):
    parsed = _nonnegative(value)
    if parsed == 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _timeout(value):
    try:
        parsed = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a finite positive number") from None
    if not math.isfinite(parsed) or not 0 < parsed <= 120:
        raise argparse.ArgumentTypeError("must be greater than zero and at most 120 seconds")
    return parsed


def _call_options(parser, *, events=False):
    parser.add_argument("--params", default="{}", metavar="JSON|@FILE|-",
                        help="Native method parameters; use - to read JSON from stdin")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate and describe the call without making an API request")
    parser.add_argument("--limit", type=_positive,
                        help="Limit records in the local output view")
    parser.add_argument("--offset", type=_nonnegative,
                        help="Skip records in the local output view")
    parser.add_argument("--fields", help="Comma-separated fields in the local output view")
    parser.add_argument("--app", help="Filter the local output view by application")
    parser.add_argument("--window", help="Filter the local output view by window")
    parser.add_argument("--contains", help="Filter the local output view by text")
    parser.add_argument("--max-text-chars", type=_positive,
                        help="Truncate strings in the local output view")
    if events:
        parser.add_argument("--date", help="today, yesterday, or YYYY-MM-DD in Asia/Shanghai")
        parser.add_argument("--start", help="Start RFC3339 timestamp with timezone or epoch milliseconds")
        parser.add_argument("--end", help="End RFC3339 timestamp with timezone or epoch milliseconds")


def build_parser():
    parser = Parser(prog="airjelly", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--runtime", help="Path to the AirJelly runtime JSON (token is never printed)")
    parser.add_argument("--policy", help="Path to a JSON permission policy")
    parser.add_argument("--timeout", type=_timeout, default=15.0)
    parser.add_argument("--max-response-bytes", type=_positive, default=4_194_304)
    parser.add_argument("--allow-write", action="store_true", help="Permit write methods")
    parser.add_argument("--allow-cost", action="store_true", help="Permit methods that may incur cost")
    parser.add_argument("--allow-execute", action="store_true", help="Permit task execution")
    parser.add_argument("--allow-method", action="append", dest="allow_methods",
                        help="Restrict to a native method (repeatable)")
    parser.add_argument("--deny-method", action="append", dest="deny_methods",
                        help="Deny a native method (repeatable)")
    parser.add_argument("--group", action="append", dest="groups",
                        choices=sorted({method.group for method in METHODS.values()}),
                        help="Restrict policy and methods output to a group (repeatable)")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("doctor", "capabilities", "methods"):
        subcommands.add_parser(name)
    call = subcommands.add_parser("call", help="Call a native method by exact name")
    call.add_argument("method")
    _call_options(call, events=True)
    mcp = subcommands.add_parser("mcp", help="Serve MCP on stdin/stdout until EOF")
    mcp.add_argument("--max-request-bytes", type=_positive, default=MAX_PARAMS_BYTES)
    groups = {}
    used_aliases = set()
    for method in METHODS.values():
        if method.group not in groups:
            group_parser = subcommands.add_parser(method.group)
            groups[method.group] = group_parser.add_subparsers(dest="operation", required=True)
        alias = _alias(method)
        if (method.group, alias) in used_aliases:
            alias = _snake_case(method.name)
        used_aliases.add((method.group, alias))
        native_alias = _snake_case(method.name)
        aliases = [native_alias] if native_alias != alias else []
        method_parser = groups[method.group].add_parser(alias, aliases=aliases, help=method.description)
        method_parser.set_defaults(method=method.name)
        _call_options(method_parser, events=method.name == "listEvents")
    return parser


def _read_params(source, stdin):
    try:
        if source == "-":
            stream = getattr(stdin, "buffer", stdin)
            text = stream.read(MAX_PARAMS_BYTES + 1)
        elif source.startswith("@"):
            with Path(source[1:]).expanduser().open("rb") as stream:
                text = stream.read(MAX_PARAMS_BYTES + 1)
        else:
            text = source
        if len(text if isinstance(text, bytes) else text.encode("utf-8")) > MAX_PARAMS_BYTES:
            raise BridgeError("invalid_params", "Parameter JSON exceeds the 1 MiB limit")
        params = json.loads(text, parse_constant=_invalid_json_constant)
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        raise BridgeError("invalid_params", "Parameters must be readable UTF-8 JSON",
                          details={"kind": type(error).__name__}) from None
    if not isinstance(params, dict):
        raise BridgeError("invalid_params", "Parameters must be a JSON object")
    return params


def _invalid_json_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def _timestamp_ms(value):
    if re.fullmatch(r"\d+", value):
        return int(value)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise BridgeError("invalid_params", "Use an RFC3339 timestamp or epoch milliseconds") from None
    if parsed.tzinfo is None:
        raise BridgeError("invalid_params", "RFC3339 timestamps must include a timezone")
    return int(parsed.timestamp() * 1000)


def _event_range(args, params):
    selected_date = getattr(args, "date", None)
    start, end = getattr(args, "start", None), getattr(args, "end", None)
    if not selected_date and start is None and end is None:
        return
    if args.method != "listEvents":
        raise BridgeError("invalid_params", "Date range flags apply only to listEvents")
    if selected_date and (start is not None or end is not None):
        raise BridgeError("invalid_params", "Use --date or --start/--end, not both")
    if "startTimeMs" in params or "endTimeMs" in params:
        raise BridgeError("invalid_params", "Date flags conflict with native range parameters")
    if selected_date:
        today = datetime.now(LOCAL_TIMEZONE).date()
        try:
            day = {"today": today, "yesterday": today - timedelta(days=1)}.get(selected_date)
            day = day or date.fromisoformat(selected_date)
        except ValueError:
            raise BridgeError("invalid_params", "--date must be today, yesterday, or YYYY-MM-DD") from None
        lower = datetime.combine(day, time.min, LOCAL_TIMEZONE)
        upper = datetime.combine(day + timedelta(days=1), time.min, LOCAL_TIMEZONE)
        params["startTimeMs"] = int(lower.timestamp() * 1000)
        params["endTimeMs"] = int(upper.timestamp() * 1000)
    else:
        if start is None or end is None:
            raise BridgeError("invalid_params", "--start and --end are required together")
        params["startTimeMs"], params["endTimeMs"] = _timestamp_ms(start), _timestamp_ms(end)
    if params["startTimeMs"] >= params["endTimeMs"]:
        raise BridgeError("invalid_params", "The event range end must be after its start")


def _view(args):
    result = {}
    for key in ("limit", "offset", "app", "window", "contains", "max_text_chars"):
        value = getattr(args, key, None)
        if value is not None:
            result[key] = value
    if args.fields is not None:
        fields = [field.strip() for field in args.fields.split(",") if field.strip()]
        if not fields:
            raise BridgeError("invalid_params", "--fields must contain at least one field")
        result["fields"] = fields
    return result or None


def exit_code(error):
    if error.code in {"usage", "invalid_params", "invalid_arguments", "unknown_method", "unsupported_method",
                      "invalid_view", "invalid_policy"}:
        return 2
    if error.code in {"policy_denied", "permission_denied", "forbidden", "not_allowed"}:
        return 3
    if error.code in {"runtime_missing", "runtime_invalid", "invalid_runtime", "unsafe_runtime", "runtime_mismatch",
                      "offline", "unavailable", "connection_error", "connection_failed", "authentication_failed",
                      "unauthorized", "timeout", "api_unavailable", "unsupported_api"}:
        return 4
    return 1


def main(argv=None, *, stdin=None, stdout=None, stderr=None, client_factory=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    stdin, stdout, stderr = stdin or sys.stdin, stdout or sys.stdout, stderr or sys.stderr
    args = None
    try:
        args = build_parser().parse_args(_global_options_first(argv))
        policy = Policy.from_file(args.policy, allow_write=args.allow_write, allow_cost=args.allow_cost,
                                  allow_execute=args.allow_execute, allow_methods=args.allow_methods,
                                  deny_methods=args.deny_methods, groups=args.groups)
        client = (client_factory or Client)(runtime_path=args.runtime, policy=policy,
                                            timeout=args.timeout, max_response_bytes=args.max_response_bytes)
        if args.command == "mcp":
            from .mcp import run

            return run(client, input_stream=getattr(stdin, "buffer", stdin), output_stream=stdout,
                       max_request_bytes=args.max_request_bytes)
        if args.command == "doctor":
            result = client.doctor()
        elif args.command == "capabilities":
            result = client.capabilities()
        elif args.command == "methods":
            result = client.methods()
            if args.groups:
                result = [method for method in result if method["group"] in args.groups]
        else:
            params = _read_params(args.params, stdin)
            _event_range(args, params)
            result = client.call(args.method, params, dry_run=args.dry_run, view=_view(args))
        stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
        return 0 if not isinstance(result, dict) or result.get("ok", True) else 1
    except BridgeError as error:
        destination = stderr if (args and args.command == "mcp") or "mcp" in argv else stdout
        destination.write(json.dumps({"ok": False, "error": error.as_dict()}, ensure_ascii=False) + "\n")
        return exit_code(error)
    except (OSError, ValueError):
        destination = stderr if (args and args.command == "mcp") or "mcp" in argv else stdout
        destination.write(json.dumps({"ok": False, "error": {"code": "transport_error",
                                                             "message": "The local transport failed"}}) + "\n")
        return 1
    except KeyboardInterrupt:
        return 130
