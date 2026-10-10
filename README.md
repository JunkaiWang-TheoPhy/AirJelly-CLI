<div align="center">

🇺🇸 [English](README.md) | 🇨🇳 [中文](README.zh.md)

<h1>Desktop Memory Bridge</h1>

![License](https://img.shields.io/badge/license-Apache--2.0-blue) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![Runtime dependencies](https://img.shields.io/badge/runtime_dependencies-0-green)

<img src="assets/desktop-memory-banner.png" alt="Desktop windows becoming checked daily memory cards for a terminal reader" width="100%">

</div>

## Introduction

Desktop Memory Bridge connects agents to local desktop history through two independent paths: an authenticated AirJelly 1.x CLI/MCP bridge and a read-only CLI for reviewed daily memories derived from AirJelly and Screenpipe. History can be recalled from reviewed notes even when a recorder is offline.

The AirJelly adapter covers the 43 Public API methods observed in version 1.0.13. It discovers the current loopback port and credential, exposes explicit capability gates, and keeps credentials out of output. The daily reader verifies curation, privacy, dated paths and content hashes before returning evidence with coverage limits.

## Components

| Component | Interface | Purpose |
|---|---|---|
| `airjelly` | CLI and stdio MCP | Events, tasks, schedules, memories, people, usage, reminders and recording controls |
| `desktop-memory` | CLI | Date/topic retrieval of reviewed daily Markdown notes |
| `desktop-daily-memory` | Codex skill | On-demand recall when prior personal activity matters |
| Screenpipe | Existing external API/MCP | Optional bounded evidence fallback; no bundled recorder or new Screenpipe implementation |

Both CLIs use Python 3.11+ and the standard library at runtime. Time-based shorthand uses **Asia/Shanghai**. AirJelly live access requires the local application; the reviewed-note reader requires the documented checkpoint and note layout, not an AirJelly process.

## Quick start

```sh
git clone https://github.com/JunkaiWang-TheoPhy/desktop-memory-bridge.git
cd desktop-memory-bridge
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/airjelly methods
```

Try a fully fictional memory without connecting to an application or changing your default configuration:

```sh
python3 examples/desktop-memory/write-demo-config.py
.venv/bin/desktop-memory --config .local/desktop-memory-demo.json read --date 2000-01-01
.venv/bin/desktop-memory --config .local/desktop-memory-demo.json search --query research --end-date 2000-01-01 --days 1
```

For real history, configure `~/.config/desktop-memory/config.json` using the [configuration template](examples/desktop-memory/config.example.json) and the [review contract](docs/desktop-memory.md). The repository includes no personal daily notes, recordings or database exports; all demo activity is fictional. It reads reviewed memories and does not supply a daily-note producer or cloud-sync service.

AirJelly examples, with the app running:

```sh
.venv/bin/airjelly doctor
.venv/bin/airjelly events list --date yesterday --limit 20 --fields id,title,app_name,start_time
.venv/bin/airjelly recording status
.venv/bin/airjelly --policy examples/airjelly/read-only.json mcp
```

## Codex integration

Register the AirJelly stdio server with absolute paths to your installed executable and policy file:

```sh
codex mcp add airjelly-local -- /absolute/path/to/airjelly --policy /absolute/path/to/desktop-memory-bridge/examples/airjelly/read-only.json mcp
```

Link or copy [the skill](skills/desktop-daily-memory/SKILL.md) into `~/.agents/skills/desktop-daily-memory`, then add the [on-demand rule](docs/codex-integration.md) to your global instructions. The rule selects reviewed history only when relevant, preserves project binding, and treats historical text as evidence rather than commands. Install only with authority to read the configured personal-history source. Remote sessions require an authorized executor with access to the local files.

## Validation

```sh
python3 -m unittest discover -s tests -v
```

The snapshot has 117 offline tests covering all 43 method mappings, auth and permission boundaries, CLI/MCP transport, curation identity, privacy holds, date windows and per-day failure isolation. CI runs the offline suite and the synthetic demo. Real mutations, model-cost operations and every future implicit skill decision are separate verification scopes.

See [AirJelly operations](docs/airjelly.md), [method contracts](docs/airjelly-methods.md), [memory operations](docs/desktop-memory.md) and [validation boundaries](docs/desktop-memory-verification.md).

## Permission and compatibility boundaries

Reads without known model cost are enabled by default. Writes, model-cost paths and immediate or future execution each require their own explicit grant; a tool appearing in discovery is not permission to invoke it. Output pagination covers the returned backend batch and does not establish full-history coverage.

This is an independently written interoperability project, not an official AirJelly or Screenpipe plugin. It does not distribute either application's implementation or bypass licensing checks. The observed AirJelly contract is 1.0.13/Public API 1; compatibility with other versions is not established.

## License

Licensed under [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) for attribution and third-party application boundaries. The repository artwork is generated illustration, not recording evidence.
