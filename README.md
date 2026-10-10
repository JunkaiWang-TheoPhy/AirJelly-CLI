<div align="center">

🇺🇸 [English](README.md) | 🇨🇳 [中文](README.zh.md)

<h1>AirJelly-CLI</h1>

![License](https://img.shields.io/badge/license-Apache--2.0-blue) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![Runtime dependencies](https://img.shields.io/badge/runtime_dependencies-0-green)

<img src="assets/airjelly-cli-banner.png" alt="An authenticated local terminal relay with separate write, cost and execution controls" width="100%">

</div>

## Introduction

AirJelly CLI exposes the local AirJelly 1.x Public API through a command-line interface and stdio MCP server. It covers the 43 methods observed in AirJelly 1.0.13, discovers the current loopback port and credential, and applies separate read, write, model-cost and execution controls.

This repository contains the AirJelly adapter split from Desktop Memory Bridge. The independent reviewed-note reader and Codex recall skill live in [Desktop-Memory-CLI](https://github.com/JunkaiWang-TheoPhy/Desktop-Memory-CLI). Screenpipe continues to use its existing external API/MCP; no Screenpipe recorder or replacement CLI is included here.

## Components

| Component | Interface | Purpose |
|---|---|---|
| `airjelly-cli` | Python package | Standard-library adapter for the authenticated local Public API |
| `airjelly` | CLI | Events, tasks, schedules, memories, people, usage, reminders and recording controls |
| `airjelly mcp` | Stdio MCP | 43 typed tools named `airjelly_<publicMethodName>` and metadata resources |

Python 3.11+ and a running local AirJelly application are required for live calls. Tool discovery and dry runs work without the application. Event date shorthand uses **Asia/Shanghai**.

## Quick start

```sh
git clone https://github.com/JunkaiWang-TheoPhy/AirJelly-CLI.git
cd AirJelly-CLI
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/airjelly methods
.venv/bin/airjelly doctor
.venv/bin/airjelly events list --date yesterday --limit 20 --fields id,title,app_name,start_time
.venv/bin/airjelly recording status
```

Native methods are also available through `call`, with JSON parameters:

```sh
.venv/bin/airjelly call getDailyAppUsage --params '{"date":"2000-01-01"}'
.venv/bin/airjelly --policy examples/airjelly/read-only.json mcp
```

The runtime descriptor stays private. No credential needs to be copied into an MCP configuration, and no personal history, recordings or database exports are distributed in this repository.

When upgrading from the former combined checkout, use a fresh clone and virtual environment. The old `desktop-memory-bridge` distribution is a different package name; installing `airjelly-cli` does not automatically uninstall it. Fresh builds also avoid stale outputs from the combined package.

## Codex integration

Register the stdio server with absolute paths to your installed executable and policy file:

```sh
codex mcp add airjelly-local -- /absolute/path/to/AirJelly-CLI/.venv/bin/airjelly --policy /absolute/path/to/AirJelly-CLI/examples/airjelly/read-only.json mcp
```

Use the read-only profile for history queries. MCP exists only while the parent client holds stdin open; this bridge does not create a listener or permanent daemon. For on-demand retrieval of reviewed daily notes, install [Desktop-Memory-CLI](https://github.com/JunkaiWang-TheoPhy/Desktop-Memory-CLI) separately.

## Validation

```sh
.venv/bin/python -m unittest discover -s tests -v
```

The adapter has 96 offline tests covering all 43 method mappings, authentication, permission boundaries, CLI parsing, output controls and stdio MCP transport. Historical local validation exercised bounded reads against AirJelly 1.0.13. Real mutations, model-cost calls and automated execution remain separate verification scopes.

See [operations](docs/airjelly.md), [method contracts](docs/airjelly-methods.md) and [validation boundaries](docs/airjelly-verification.md).

## Permission and compatibility boundaries

Reads without known model cost are enabled by default. Writes, model-cost paths and immediate or future execution each require their own explicit grant. Listing a tool does not grant permission to invoke it. Output pagination covers the returned backend batch and does not establish full-history or all-day recording coverage.

This is an independently written interoperability project, not an official AirJelly plugin. It does not distribute the application or bypass licensing checks. The observed contract is AirJelly 1.0.13/Public API 1; compatibility with other versions is not established.

## License

Licensed under [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution and third-party application boundaries. Repository artwork is generated illustration, not recording evidence.
