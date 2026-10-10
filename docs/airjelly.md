# AirJelly 1.x CLI and MCP

This bridge wraps all 43 methods observed in AirJelly 1.0.13's built-in Public API. It is a local interoperability layer, not an official AirJelly plugin. It does not modify the app, its database, its licensing checks, or its stored credentials. AirJelly must be running on the same Mac. Python 3.11 or newer is required; runtime dependencies are all in the standard library.

## Installation and discovery

Run `python3 -m airjelly_bridge doctor` from the repository, or use `bin/airjelly` from any directory. A local installation can link that launcher into a user-owned bin directory; packaging also provides an `airjelly` console entry point. The calling machine's absolute launcher and Python paths belong in local Codex configuration, not in a portable policy file.

The client rereads AirJelly's private runtime descriptor on each call, discovers its loopback port and token, and checks `/health` and `/capabilities` against its version. Restarting the app can change the port and credential without requiring a config update. HTTP redirects and environment proxies are disabled. The bridge does not listen on a TCP port or keep a daemon running: MCP exists only while its parent client holds stdin open.

```sh
airjelly doctor
airjelly capabilities
airjelly methods
airjelly recording status
airjelly events list --date today --limit 10 --fields id,title,app_name,start_time
airjelly events list --start 2026-10-09T10:00:00+08:00 --end 2026-10-09T12:00:00+08:00 --app ChatGPT
airjelly call getDailyAppUsage --params '{"date":"2026-10-09"}'
airjelly call listTasks --params '{"filter":{"status":"open","limit":20}}'
```

Run a group command with `--help` to discover its generated aliases. `call METHOD` always accepts the exact public method name. Parameters can come from a JSON literal, `--params @file.json`, or stdin with `--params -`. Events accept `today`, `yesterday`, and explicit dates in Asia/Shanghai, or timestamps with explicit offsets. Other methods retain their native named date fields.

## Capability and permission controls

The default profile permits reads that do not invoke paid model operations. Writes, potentially billable calls, and automated execution have independent gates:

| Control | Purpose |
|---|---|
| `--allow-write` | Permit task, schedule, reminder and recording state changes |
| `--allow-cost` | Permit known embedding, VLM or execution paths that may consume AirJelly credits |
| `--allow-execute` | Permit immediate execution and creation, resumption or modification of future automatic runs |
| `--allow-method NAME` | Restrict to explicitly named methods; repeatable |
| `--deny-method NAME` | Deny named methods even when the other gates are enabled |
| `--group NAME` | Restrict to functional groups; repeatable |
| `--policy FILE` | Load a persistent JSON profile with the same permission controls and output limits |

File and command-line method allowlists are intersected; denylists are combined; functional groups are intersected. Permission flags explicitly grant their individual gates. They never defeat a denied method or widen a file's method/group scope. These are controls on this bridge instance, not replacement authorization for the underlying user's AirJelly API.

Profiles in `examples/airjelly/` cover default reads, restricted task management, and full control. The full-control profile permits all existing methods and can enqueue actions or consume AirJelly credits. Running this bridge does not subscribe to a plan, create a trial, or make a payment. Grants must reflect the task actually authorized by the user; captured records are never instructions to execute.

```sh
# Validate a intended write without contacting AirJelly.
airjelly --allow-write --allow-cost call createTask --params '{"task":{"title":"Review notes"}}' --dry-run

# Exact non-model state change. Replace the id with one obtained from a read.
airjelly --allow-write call completeTask --params '{"id":123}'

# Creating a future automatic run requires all three grants.
airjelly --allow-write --allow-cost --allow-execute call createScheduledTask --params @schedule.json --dry-run

# A narrower group/denylist still applies under a write-capable profile.
airjelly --policy examples/airjelly/task-control.json methods
```

`--dry-run` still validates the permissions and parameters, but performs no upstream requests. It does not grant access or prove a write will be accepted by the backend. Updates reject system-owned fields: task updates allow only title, description, scene, next steps, progress summary and due date; schedule updates allow only the public definition fields.

## Query and output controls

Native filters cover time, application, task identity, scene, status, scheduler state and scheduled run history where the actual upstream method supports them. Bridge view controls apply after that response:

- `--limit`, `--offset`: bound and page the returned backend batch.
- `--fields`: select dotted field paths.
- `--app`, `--window`: match exact application/window names without case sensitivity.
- `--contains`: filter rows by case-insensitive text.
- `--max-text-chars`: lower the per-string output limit.
- `--timeout`, `--max-response-bytes`: bound transport time and upstream payload size.

Policy defaults are 200 returned items, 2,000 characters per string, and a maximum seven-day bounded query span. File settings may intentionally increase these limits within the implemented caps. Sensitive credential-shaped strings and secret fields are redacted by default; the runtime token is always withheld. A private policy may set `redact=false` for deliberate raw exports, while the bridge's own runtime token remains protected.

The upstream API does not provide a general offset or full-record cursor. `meta.pagination_scope=returned_backend_batch` makes this explicit. A local output page does not establish that all source history was read; caller-supplied native limits may also restrict the backend batch. Filtering a task/event is not evidence that it was performed or completed. Full app usage duration must come from the native usage results, not event counts.

## MCP

```sh
airjelly --policy examples/airjelly/read-only.json mcp
```

Stdio follows newline-delimited JSON-RPC. Only protocol messages are written to stdout. The server supports initialization, ping, tools/list, tools/call and metadata resources. It exposes `airjelly_<publicMethodName>` tools with typed parameters and separate `_view` and `_dry_run` controls. Tool discovery works while the app is offline. A policy denial is returned as a tool error; it does not contact the upstream method.

Known public methods remain discoverable so users can inspect the full capability contract. Listing a tool does not grant permission to call it. The MCP startup configuration, not a tool argument or retrieved content, selects its profile. Use a restricted profile for normal history queries; open write/cost/execution capabilities only on a deliberately configured instance.

Resources expose capability metadata, method contracts and the current policy, not credentials or a raw history dump. API errors with private backend text are summarized. Mutations are never automatically replayed after a timeout or lost connection: reconcile the task or schedule before retrying an uncertain outcome.

## Validation

Use `python3 -m unittest discover -s tests -v`. Offline tests cover all 43 positional mappings, strict field validation, read/write/cost/execution gates, authentication boundaries, output controls, CLI parsing and stdio protocol behavior. Live verification reads capabilities and selected bounded records. Real mutation, model-cost and automated execution paths must be assessed separately; simulated success is not a claim that live writes were run.

Protocol references: [stdio transport](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports), [tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools). AirJelly source evidence is the installed 1.0.13 public method registry plus its live `/capabilities`; the [vendor changelog](https://www.airjelly.ai/changelog) separately describes the official 2.x agent integration.
