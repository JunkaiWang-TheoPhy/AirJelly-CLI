# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 JunkaiWang-TheoPhy
"""Named parameter contracts for AirJelly 1.0.13's 43 public RPC methods.

The upstream RPC transport takes positional ``args``. Both bridge transports use
these named schemas so validation, field restrictions, and argument order agree.
The schemas intentionally leave upstream status and schedule-kind vocabularies
open rather than inventing enums. No coercion or caller-owned mutation occurs.
"""

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
import math
import re

from .errors import BridgeError


def _object(properties, required=(), description=None):
    schema = {
        "type": "object",
        "properties": deepcopy(properties),
        "required": list(required),
        "additionalProperties": False,
    }
    if description:
        schema["description"] = description
    return schema


def _nullable(schema):
    return {"anyOf": [deepcopy(schema), {"type": "null"}]}


_STRING = {"type": "string"}
_NONEMPTY = {"type": "string", "minLength": 1, "pattern": r"\S"}
_STRINGS = {"type": "array", "items": _STRING}
_STATUS = {"anyOf": [_NONEMPTY, {"type": "array", "items": _NONEMPTY}]}
_ID = {"anyOf": [{"type": "integer", "minimum": 1}, _NONEMPTY]}
_IDS = {"type": "array", "items": _ID}
_MS = {"type": "integer", "minimum": 0}
_TIME = {
    "anyOf": [_MS, {**_NONEMPTY, "format": "date-time"}],
    "description": "Epoch milliseconds or an ISO 8601 timestamp with timezone offset.",
}
_LIMIT = {"type": "integer", "minimum": 1}
_BOOL = {"type": "boolean"}
_DATE = {
    "type": "string",
    "format": "date",
    "pattern": r"^\d{4}-\d{2}-\d{2}$",
    "description": "Calendar date in YYYY-MM-DD form, using AirJelly's local day boundary.",
}

_TASK_CREATE = _object(
    {
        "title": _NONEMPTY,
        "description": _STRING,
        "l1_scene": _STRING,
        "start_time": _MS,
        "due_date": _MS,
    },
    ("title",),
)
_TASK_PATCH = _object(
    {
        "title": _NONEMPTY,
        "description": _STRING,
        "l1_scene": _STRING,
        "next_steps": _STRINGS,
        "progress_summary": _STRING,
        "due_date": _MS,
    },
    description="Only the six fields allowed by AirJelly's task:update-user-fields handler.",
)
_TASK_FILTER = _object(
    {
        "status": _STATUS,
        "origin": _STRING,
        "l1_scene": _STRING,
        "last_active_at_after": _MS,
        "last_active_at_before": _MS,
        "start_time_after": _MS,
        "start_time_before": _MS,
        "updated_at_after": _MS,
        "updated_at_before": _MS,
        "scheduler_state": _STATUS,
        "scheduler_archived": {"type": "integer", "minimum": 0, "maximum": 1},
        "limit": _LIMIT,
    },
    description="Read filters accepted by AirJelly 1.0.13's task:get-list handler.",
)
_SCHEDULE_CREATE = _object(
    {
        "title": _NONEMPTY,
        "instruction": _NONEMPTY,
        "schedule_kind": _NONEMPTY,
        "rrule": _nullable(_STRING),
        "timezone": _NONEMPTY,
        "start_at": _TIME,
        "end_at": _nullable(_TIME),
        "task_id": _nullable(_ID),
    },
    ("title", "instruction", "schedule_kind", "timezone", "start_at"),
)
_SCHEDULE_PATCH = _object(
    {
        "title": _NONEMPTY,
        "instruction": _NONEMPTY,
        "schedule_kind": _NONEMPTY,
        "rrule": _nullable(_STRING),
        "timezone": _NONEMPTY,
        "start_at": _TIME,
        "end_at": _nullable(_TIME),
        "status": _NONEMPTY,
    },
    description="Fields documented by the public updateScheduledTask method.",
)
_SCHEDULE_FILTER = _object(
    {
        "status": _STATUS,
        "task_id": _nullable(_ID),
        "include_archived": _BOOL,
        "next_run_at_after": _MS,
        "next_run_at_before": _MS,
        "limit": _LIMIT,
    },
    description="Read filters accepted by AirJelly 1.0.13's scheduled-task repository.",
)
_UPCOMING_FILTER = _object(
    {
        "start_ms": _MS,
        "end_ms": _MS,
        "status": _STATUS,
        "task_id": _nullable(_ID),
        "include_archived": _BOOL,
        "limit": _LIMIT,
    }
)
_HISTORY_FILTER = _object(
    {
        "scheduled_task_id": _ID,
        "status": _STATUS,
        "occurrence_at_after": _MS,
        "occurrence_at_before": _MS,
        "limit": _LIMIT,
    }
)
_OVERVIEW_OPTIONS = _object(
    {
        "upcoming_start_ms": _MS,
        "upcoming_end_ms": _MS,
        "upcoming_limit": _LIMIT,
        "history_limit": _LIMIT,
        "include_archived": _BOOL,
    }
)
_MEMORY_FILTER = _object(
    {
        "memory_types": _STRINGS,
        "task_id": _ID,
        "app_name": _STRING,
        "start_time_after": _MS,
        "start_time_before": _MS,
        "limit": _LIMIT,
    }
)


def _invalid(path, message):
    raise BridgeError("invalid_params", f"{path}: {message}", details={"path": path})


def _validate(schema, value, path):
    """Validate the small JSON Schema subset used by these static contracts."""
    if "anyOf" in schema:
        for option in schema["anyOf"]:
            try:
                _validate(option, value, path)
                return
            except BridgeError:
                pass
        _invalid(path, "does not match any permitted type or value")

    kind = schema.get("type")
    valid_type = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": type(value) is int,
        "number": type(value) in (int, float),
        "boolean": type(value) is bool,
        "null": value is None,
    }.get(kind, False)
    if not valid_type:
        _invalid(path, f"must be {kind}")

    if kind == "object":
        if any(not isinstance(key, str) for key in value):
            _invalid(path, "object field names must be strings")
        properties = schema["properties"]
        unknown = sorted(set(value) - set(properties))
        if unknown and not schema["additionalProperties"]:
            _invalid(path, f"unknown fields: {', '.join(unknown)}")
        missing = [key for key in schema["required"] if key not in value]
        if missing:
            _invalid(path, f"missing required fields: {', '.join(missing)}")
        for key, item in value.items():
            if key in properties:
                _validate(properties[key], item, f"{path}.{key}")
    elif kind == "array":
        for index, item in enumerate(value):
            _validate(schema["items"], item, f"{path}[{index}]")
    elif kind == "string":
        if len(value) < schema.get("minLength", 0):
            _invalid(path, "must not be empty")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            _invalid(path, f"must match {schema['pattern']}")
        if schema.get("format") == "date":
            try:
                date.fromisoformat(value)
            except ValueError:
                _invalid(path, "must be a valid calendar date in YYYY-MM-DD form")
        elif schema.get("format") == "date-time":
            # JSON Schema date-time uses the ISO 8601 / RFC 3339 form with
            # seconds and an explicit Z or ±HH:MM offset. fromisoformat alone
            # accepts spaces and normalizes invalid offset minutes, so check
            # the lexical form before validating its calendar and clock parts.
            if not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?"
                r"(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)", value
            ):
                _invalid(path, "must be an ISO 8601 date-time with an explicit timezone offset")
            try:
                parsed = datetime.fromisoformat(
                    value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
                )
            except ValueError:
                _invalid(path, "must have valid calendar, clock, and timezone values")
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                _invalid(path, "must include an explicit timezone offset")
    elif kind in ("integer", "number"):
        if kind == "number" and not math.isfinite(value):
            _invalid(path, "must be finite")
        if "minimum" in schema and value < schema["minimum"]:
            _invalid(path, f"must be at least {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            _invalid(path, f"must be at most {schema['maximum']}")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            _invalid(path, f"must be greater than {schema['exclusiveMinimum']}")


@dataclass(frozen=True)
class Method:
    name: str
    group: str
    description: str
    schema: dict
    write: bool = False
    costly: bool = False
    execute: bool = False

    def to_args(self, params: dict) -> list:
        _validate(self.schema, params, f"{self.name}.params")
        names = _ARGUMENTS[self.name]
        supplied = [index for index, key in enumerate(names) if key in params]
        if not supplied:
            return []
        last = max(supplied)
        # Current public signatures have only optional trailing parameters.
        # Never insert synthetic nulls or defaults into the native arguments.
        return [deepcopy(params[key]) for key in names[: last + 1]]


METHODS: dict[str, Method] = {}
_ARGUMENTS: dict[str, tuple[str, ...]] = {}


def _method(name, group, description, properties=None, required=(), *, write=False,
            costly=False, execute=False):
    properties = {} if properties is None else properties
    _ARGUMENTS[name] = tuple(properties)
    METHODS[name] = Method(
        name, group, description, _object(properties, required), write, costly, execute
    )


_method(
    "listEvents", "events", "List event memories within a time range.",
    {"startTimeMs": _MS, "endTimeMs": _MS}, ("startTimeMs", "endTimeMs"),
)
_method("getTask", "tasks", "Get a task by id.", {"id": _ID}, ("id",))
_method("listTasks", "tasks", "List tasks with optional read filters.", {"filter": _TASK_FILTER})
_method("listOpenTasks", "tasks", "List open tasks with an optional limit.", {"limit": _LIMIT})
_method(
    "getTaskMemories", "tasks", "Get memories for a task.",
    {"taskId": _ID}, ("taskId",),
)
_method(
    "createTask", "tasks", "Create a manual task; makes a potentially billable embedding API call.",
    {"task": _TASK_CREATE}, ("task",), write=True, costly=True,
)
_method(
    "updateTask", "tasks", "Update only the six user-editable task fields.",
    {"id": _ID, "patch": _TASK_PATCH}, ("id", "patch"), write=True,
)
for _name, _description in (
    ("completeTask", "Mark a task as completed."),
    ("reopenTask", "Reopen a completed task."),
    ("archiveTask", "Archive a task."),
    ("unarchiveTask", "Unarchive a task."),
):
    _method(_name, "tasks", _description, {"id": _ID}, ("id",), write=True)
_method(
    "snoozeTask", "tasks", "Snooze a task until an epoch millisecond timestamp.",
    {"id": _ID, "untilMs": _MS}, ("id", "untilMs"), write=True,
)
_method(
    "createScheduledTask", "schedules", "Create a background task schedule; future runs can perform actions and consume credits.",
    {"schedule": _SCHEDULE_CREATE}, ("schedule",), write=True, costly=True, execute=True,
)
_method(
    "listScheduledTasks", "schedules", "List scheduled tasks with optional read filters.",
    {"filter": _SCHEDULE_FILTER},
)
_method(
    "getScheduledTask", "schedules", "Get a scheduled task by id.", {"id": _ID}, ("id",),
)
_method(
    "updateScheduledTask", "schedules", "Update a schedule; future runs can perform actions and consume credits.",
    {"id": _ID, "patch": _SCHEDULE_PATCH}, ("id", "patch"), write=True, costly=True, execute=True,
)
for _name, _description in (
    ("pauseScheduledTask", "Pause a scheduled task and terminate its active execution."),
    ("archiveScheduledTask", "Archive a scheduled task."),
):
    _method(_name, "schedules", _description, {"id": _ID}, ("id",), write=True)
_method(
    "resumeScheduledTask", "schedules", "Resume a schedule; future runs can perform actions and consume credits.",
    {"id": _ID}, ("id",), write=True, costly=True, execute=True,
)
_method(
    "listScheduledTaskRuns", "schedules", "List runs for one scheduled task.",
    {"scheduledTaskId": _ID, "limit": _LIMIT}, ("scheduledTaskId",),
)
_method(
    "listScheduledTaskUpcomingOccurrences", "schedules", "List future scheduled task occurrences.",
    {"filter": _UPCOMING_FILTER},
)
_method(
    "listScheduledTaskRunHistory", "schedules", "List recent runs with result, error, and execution id.",
    {"filter": _HISTORY_FILTER},
)
_method(
    "getScheduledTaskOverview", "schedules", "Get upcoming occurrences and recent run history.",
    {"options": _OVERVIEW_OPTIONS},
)
_method(
    "runScheduledTaskNow", "schedules", "Create and enqueue an immediate run; can perform actions and consume credits.",
    {"id": _ID}, ("id",), write=True, costly=True, execute=True,
)
_method(
    "retryScheduledTaskRun", "schedules", "Retry a run by its run id; can perform actions and consume credits.",
    {"runId": _ID}, ("runId",), write=True, costly=True, execute=True,
)
_method(
    "searchMemory", "memories", "Hybrid semantic and full-text memory search; makes a potentially billable embedding API call.",
    {"query": _NONEMPTY, "filter": _MEMORY_FILTER}, ("query",), costly=True,
)
_method(
    "listMemories", "memories", "List memories by filter without a semantic embedding API call.",
    {"filter": _MEMORY_FILTER},
)
_method("getMemory", "memories", "Get a memory with resolved screenshot paths.", {"id": _ID}, ("id",))
_method(
    "resolveScreenshotPaths", "memories", "Resolve raw source screenshot ids to absolute file paths.",
    {"ids": _IDS}, ("ids",),
)
_method("listPersons", "persons", "List person entities with aliases and event counts.")
_method(
    "getEventsForEntity", "persons", "Get events linked to a specific entity id.",
    {"entityId": _ID}, ("entityId",),
)
_method("getDailyAppUsage", "usage", "Get aggregated app usage for one day.", {"date": _DATE}, ("date",))
_method(
    "getAppUsageRange", "usage", "Get daily aggregated app usage across a date range.",
    {"startDate": _DATE, "endDate": _DATE}, ("startDate", "endDate"),
)
_method(
    "getTopApps", "usage", "Get the most-used apps in a date range.",
    {"startDate": _DATE, "endDate": _DATE, "limit": _LIMIT}, ("startDate", "endDate"),
)
_method("getAppSessions", "usage", "Get raw app usage sessions for one day.", {"date": _DATE}, ("date",))
_method("getAppIcons", "usage", "Resolve app names to icon data URLs.", {"appNames": _STRINGS}, ("appNames",))
_method("dismissReminder", "reminders", "Dismiss a reminder by id.", {"id": _ID}, ("id",), write=True)
_method(
    "snoozeReminder", "reminders", "Snooze a reminder for a positive number of minutes.",
    {"id": _ID, "durationMinutes": {"type": "number", "exclusiveMinimum": 0}},
    ("id", "durationMinutes"), write=True,
)
_method("getRecordingStatus", "recording", "Check screen recording status.")
_method("getRecordingPermissions", "recording", "Check screen recording permission.")
_method("getRecordingStats", "recording", "Get screenshot count, disk usage, and recording date range.")
_method(
    "startRecording", "recording", "Begin screenshot capture and potentially billable VLM processing.",
    write=True, costly=True,
)
_method("stopRecording", "recording", "Stop AirJelly's screen recording task.", write=True)


def validate_params(method_name: str, params: dict) -> list:
    """Validate named parameters and return the exact upstream positional args."""
    if not isinstance(method_name, str) or method_name not in METHODS:
        raise BridgeError("invalid_params", "Unknown AirJelly method")
    return METHODS[method_name].to_args(params)
