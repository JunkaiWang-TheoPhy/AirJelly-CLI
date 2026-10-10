# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 JunkaiWang-TheoPhy
"""Authenticated, dynamically discovered loopback Public API calls."""

from datetime import date, datetime
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import stat
import urllib.error
import urllib.request

from .contracts import METHODS, validate_params
from .errors import BridgeError
from .policy import Policy

DEFAULT_RUNTIME = Path.home() / "Library/Application Support/AirJelly/runtime.json"
SECRET_KEYS = {"token", "accesstoken", "refreshtoken", "apikey", "authorization", "password", "cookie", "secret", "appsecret"}
SECRET_PATTERN = re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|(?:sk-|sp-)[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._-]{16,})")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BridgeError("unsafe_redirect", "Local API redirects are not allowed")


def _timestamp(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value / 1000
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            try:
                return date.fromisoformat(value).toordinal() * 86400
            except ValueError:
                return None
    return None


def _check_bounds(params, policy):
    checked = False
    pairs = (("startTimeMs", "endTimeMs"), ("startDate", "endDate"),
             ("start_time_after", "start_time_before"), ("last_active_at_after", "last_active_at_before"),
             ("updated_at_after", "updated_at_before"), ("occurrence_at_after", "occurrence_at_before"),
             ("next_run_at_after", "next_run_at_before"),
             ("start_ms", "end_ms"), ("upcoming_start_ms", "upcoming_end_ms"))
    for key, value in params.items():
        if key == "limit" or key.endswith("_limit"):
            if isinstance(value, int) and value > policy.max_items:
                raise BridgeError("policy_denied", "Requested limit exceeds max_items")
        if isinstance(value, dict):
            checked = _check_bounds(value, policy) or checked
    for left, right in pairs:
        if left in params and right in params:
            a, b = _timestamp(params[left]), _timestamp(params[right])
            if a is not None and b is not None and (b < a or b - a > policy.max_span_days * 86400):
                raise BridgeError("policy_denied", "Time range is reversed or exceeds max_span_days")
            checked = a is not None and b is not None or checked
    return checked


def _pick(row, fields):
    result = {}
    for field in fields:
        value = row
        for part in field.split("."):
            if not isinstance(value, dict) or part not in value:
                break
            value = value[part]
        else:
            result[field] = value
    return result


def _clean(value, policy, max_chars, token):
    if isinstance(value, str):
        value = value.replace(token, "[REDACTED]") if token else value
        if policy.redact:
            value = SECRET_PATTERN.sub("[REDACTED]", value)
        return value if len(value) <= max_chars else value[:max_chars] + "…[truncated]"
    if isinstance(value, list):
        return [_clean(v, policy, max_chars, token) for v in value[:policy.max_items]]
    if isinstance(value, dict):
        return {k: "[REDACTED]" if policy.redact and re.sub(r"[_-]", "", k).lower() in SECRET_KEYS
                else _clean(v, policy, max_chars, token) for k, v in value.items()}
    return value


class Client:
    def __init__(self, runtime_path=None, policy=None, timeout=15.0, max_response_bytes=4194304):
        self.runtime_path = Path(runtime_path or DEFAULT_RUNTIME)
        self.policy = policy or Policy()
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 120:
            raise BridgeError("invalid_params", "Timeout must be greater than zero and at most 120 seconds")
        if type(max_response_bytes) is not int or not 1 <= max_response_bytes <= 33554432:
            raise BridgeError("invalid_params", "Response byte limit must be from 1 to 33554432")
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def _runtime(self):
        try:
            with self.runtime_path.open("r", encoding="utf-8") as stream:
                info = os.fstat(stream.fileno())
                if self.runtime_path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                    raise BridgeError("unsafe_runtime", "Runtime must be a private regular file owned by the current user")
                raw = stream.read(65537)
            if len(raw) > 65536:
                raise BridgeError("invalid_runtime", "Runtime descriptor is too large")
            runtime = json.loads(raw)
            if not isinstance(runtime, dict):
                raise ValueError
            port, token, pid = runtime.get("port"), runtime.get("token"), runtime.get("pid")
            if type(port) is not int or not 0 < port < 65536 or not isinstance(token, str) or not token or type(pid) is not int or pid <= 0:
                raise ValueError
            if not isinstance(runtime.get("version"), str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", runtime["version"]):
                raise ValueError
            os.kill(pid, 0)
            return runtime
        except BridgeError:
            raise
        except (OSError, ValueError):
            raise BridgeError("invalid_runtime", "AirJelly is not running or its runtime descriptor is invalid") from None

    def _request(self, runtime, endpoint, payload=None, *, write=False):
        url = f"http://127.0.0.1:{runtime['port']}{endpoint}"
        headers = {"Accept": "application/json"}
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if len(body) > 1024 * 1024:
                raise BridgeError("invalid_params", "Request exceeds the upstream one-megabyte limit")
            headers.update({"Content-Type": "application/json", "Authorization": "Bearer " + runtime["token"]})
        request = urllib.request.Request(url, data=body, headers=headers)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(self.max_response_bytes + 1)
            if len(raw) > self.max_response_bytes:
                raise BridgeError("response_too_large", "Response exceeds the configured byte limit; narrow the query")
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("ok") is not True:
                raise BridgeError("upstream_error", "AirJelly rejected the request; backend text is withheld to protect private data")
            return data
        except BridgeError:
            raise
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            raise BridgeError("outcome_unknown" if write and status >= 500 else "upstream_http_error",
                              "Reconcile write outcome before retrying" if write and status >= 500 else "AirJelly API request failed",
                              details={"http_status": status}) from None
        except (OSError, ValueError):
            code = "outcome_unknown" if write else "connection_failed"
            message = "Write outcome is unknown; reconcile state before retrying" if write else "Cannot read a valid response from the local AirJelly API"
            raise BridgeError(code, message) from None

    def _discover(self):
        runtime = self._runtime()
        health = self._request(runtime, "/health")
        capabilities = self._request(runtime, "/capabilities").get("data", {})
        if not isinstance(capabilities, dict):
            raise BridgeError("unsupported_api", "Invalid Public API capability object")
        if health.get("version") != runtime.get("version") or capabilities.get("appVersion") != runtime.get("version"):
            raise BridgeError("runtime_mismatch", "Runtime version does not match the local API identity")
        if capabilities.get("apiVersion") != "1" or not isinstance(capabilities.get("methods"), list):
            raise BridgeError("unsupported_api", "Unsupported Public API version or capability list")
        if any(not isinstance(name, str) or name == runtime["token"] or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,127}", name) for name in capabilities["methods"]):
            raise BridgeError("unsupported_api", "Invalid Public API method list")
        return runtime, {"apiVersion": capabilities["apiVersion"], "appVersion": capabilities["appVersion"],
                         "methods": capabilities["methods"]}

    def capabilities(self):
        _, result = self._discover()
        return result

    def doctor(self):
        _, cap = self._discover()
        live = set(cap["methods"])
        return {"ok": True, "app_version": cap["appVersion"], "api_version": cap["apiVersion"],
                "known_method_count": len(METHODS), "live_method_count": len(live),
                "missing_methods": sorted(METHODS.keys() - live), "unknown_methods": sorted(live - METHODS.keys()),
                "transport": "authenticated-loopback-rpc", "policy": self.policy.as_dict()}

    def methods(self):
        try:
            available = set(self.capabilities()["methods"])
        except BridgeError:
            available = None
        result = []
        for name, method in METHODS.items():
            try:
                self.policy.authorize(method)
                allowed = True
            except BridgeError:
                allowed = False
            result.append({"name": name, "group": method.group, "description": method.description,
                           "schema": deepcopy(method.schema), "write": method.write, "costly": method.costly,
                           "execute": method.execute, "available": None if available is None else name in available,
                           "allowed": allowed})
        return result

    def call(self, method, params, *, dry_run=False, view=None):
        if not isinstance(method, str) or method not in METHODS:
            raise BridgeError("unsupported_method", "Unknown AirJelly Public API method")
        definition = METHODS[method]
        args = validate_params(method, params)
        self.policy.authorize(definition)
        range_checked = _check_bounds(params, self.policy)
        view = {} if view is None else view
        allowed_view = {"limit", "offset", "fields", "app", "window", "contains", "max_text_chars"}
        if not isinstance(view, dict) or set(view) - allowed_view:
            raise BridgeError("invalid_params", "Unknown output-view controls")
        limit, offset, chars = view.get("limit", self.policy.max_items), view.get("offset", 0), view.get("max_text_chars", self.policy.max_text_chars)
        if type(limit) is not int or not 1 <= limit <= self.policy.max_items or type(offset) is not int or not 0 <= offset <= 100000 or type(chars) is not int or not 1 <= chars <= self.policy.max_text_chars:
            raise BridgeError("invalid_params", "Output limits exceed policy or are invalid")
        fields = view.get("fields")
        if fields is not None and (not isinstance(fields, list) or any(not isinstance(x, str) or not x for x in fields)):
            raise BridgeError("invalid_params", "fields must be an array of nonempty field paths")
        for key in ("app", "window", "contains"):
            if key in view and not isinstance(view[key], str):
                raise BridgeError("invalid_params", f"{key} must be a string")
        if dry_run:
            return {"ok": True, "method": method, "data": {"args": _clean(args, self.policy, chars, None)},
                    "meta": {"dry_run": True, "write": definition.write, "costly": definition.costly, "execute": definition.execute}}
        runtime, cap = self._discover()
        if method not in cap["methods"]:
            raise BridgeError("unsupported_method", "Installed AirJelly does not expose this method")
        data = self._request(runtime, "/rpc", {"method": method, "args": args}, write=definition.write).get("data")
        meta = {"app_version": cap["appVersion"], "dry_run": False, "read_only": not definition.write,
                "pagination_scope": "returned_backend_batch", "redacted": self.policy.redact,
                "text_limit": chars, "time_range_validated": range_checked}
        if isinstance(data, list):
            batch = data
            for key, column in (("app", "app_name"), ("window", "window_name")):
                if key in view:
                    batch = [row for row in batch if isinstance(row, dict) and str(row.get(column, "")).casefold() == view[key].casefold()]
            if "contains" in view:
                batch = [row for row in batch if view["contains"].casefold() in json.dumps(row, ensure_ascii=False).casefold()]
            meta.update({"backend_batch_count": len(data), "filtered_count": len(batch), "offset": offset,
                         "returned_count": len(batch[offset:offset + limit]), "has_more_in_batch": len(batch) > offset + limit})
            data = batch[offset:offset + limit]
            if fields is not None:
                data = [_pick(row, fields) if isinstance(row, dict) else row for row in data]
        elif fields is not None and isinstance(data, dict):
            data = _pick(data, fields)
        return {"ok": True, "method": method, "data": _clean(data, self.policy, chars, runtime["token"]), "meta": meta}
