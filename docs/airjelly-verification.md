# AirJelly bridge validation receipt

Validated locally on 2026-10-10 against AirJelly 1.0.13, Public API version 1.

- Exact live capability match: 43 known methods, 43 live methods, no missing or unknown methods.
- Offline verification: 96 unit tests pass; all 43 positional RPC mappings were exercised against local mock services.
- CLI live reads: recording status, bounded event listing and selected application usage fields succeed.
- MCP live verification: initialization, 43 typed tools, recording-status read, policy resource and clean EOF exit succeed.
- MCP write gate: a stop-recording request is rejected as `policy_denied` under the default profile; recording remains running.
- Costs and writes: schema mapping, permission gates and uncertainty behavior were verified with mocks or dry runs. No real task mutation, scheduled execution or model-cost operation was run for validation.
- A local Codex registration using the read-only profile and runtime-discovered credentials was verified. This is historical local validation; configure your own instance without storing credentials in MCP configuration.

Negative controls caught unknown group/allowlist handling and invalid schedule time windows before correction. The former schedule metadata also failed a test requiring independent future-execution and cost grants. Invalid dates and timezone-less schedule timestamps failed their new tests before strict format validation was implemented.

The bridge depends on the local application and its current Public API contract. This receipt does not assert compatibility with a future API version, remote hosting, or actual live mutation behavior.
