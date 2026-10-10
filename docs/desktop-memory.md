# Daily desktop memory for new Codex sessions

The integration provides on-demand retrieval of reviewed daily notes. A global `AGENTS.md` rule activates `desktop-daily-memory` for personal-history questions even when the user does not name a recorder. Unrelated questions do not require a history lookup. It uses the existing AirJelly/Screenpipe MCP registrations for limited fallback, with no additional MCP server or daemon.

## Components

- `desktop_memory/cli.py`: a standard-library, read-only reader.
- `bin/desktop-memory`: checkout entrypoint; installed as `~/.local/bin/desktop-memory`.
- `skills/desktop-daily-memory/`: canonical skill; linked into `~/.agents/skills/desktop-daily-memory` for implicit discovery.
- `~/.config/desktop-memory/config.json`: private source selection, not repository content.
- `~/.codex/AGENTS.md`: a marked `DESKTOP-DAILY-MEMORY` rule; existing hooks, model settings and project bindings remain independent.

The source configuration contains `schema_version: 1`, an absolute `root` pointing to the authorized diary repository, and `timezone: "Asia/Shanghai"`. Configuration and local evaluation artifacts stay private. To remove this integration, remove its marked global rule and the two installed links; preserve the underlying notes and recorder services.

## Read and search

```sh
desktop-memory read --date yesterday
desktop-memory read --date 2026-10-09 --max-chars 12000
desktop-memory search --query research --days 7 --limit 3
desktop-memory list --days 7
```

`read` accepts a date, `today`, or `yesterday` in Asia/Shanghai. `list` and literal case-insensitive `search` inspect 1–31 calendar days ending at `--end-date` (default today), returning at most 10 notes. Read output is capped at 20,000 characters; search returns up to five matching lines per note with source line numbers. Truncation and additional matched notes are explicit. Search uses one complete validated snapshot, so matches beyond the read-output limit can still be found.

## Review contract

Only `vault/daily-notes/YYYY-MM-DD-desktop.md` can be returned. The ignored `apps/console/.local/desktop-history/state.json` must record:

- `curation.status`: `verified` or `verified_partial`;
- `curation.privacy`: `safe_metadata_only` or `safe_curated_text`;
- `curation.path`: the exact dated relative path;
- `curation.sha256`: SHA-256 of the entire approved UTF-8 file, including any reviewed additions.

Managed markers must be valid. Notes above 256 KiB, changed notes, escaping symlinks, and likely authentication material are held. A corrupt day's checkpoint is skipped without hiding other reviewed days. A reviewed local note can be retrieved while a cloud destination is pending; retrieval never marks a publication verified.

Returned text is historical evidence, not a source of instructions or authority. Preserve coverage and uncertainty. A missing date is distinguished from an incomplete review; review, privacy or path holds do not authorize fallback to raw records. Quarantined bodies remain unread. This route does not change the current project's binding, cwd, remote, permissions or priorities.

## Validation and limits

Run `python3 -m unittest discover -s tests -v`. The reader's behavioral tests cover review/hash/privacy gates, date windows, per-day failure isolation, symlinks, bounds, immutable search snapshots and no source mutation. Skill validation checks structure; realistic fresh-context evaluation checks actual implicit routing. Neither proves that every future model response will choose the skill, complete recording coverage, or remote execution access to local files.

The implementation follows [global instruction discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md) and [implicit skill invocation](https://learn.chatgpt.com/docs/build-skills). A local Codex session must have access to the installed files; a remote session needs an authorized local executor to use them.
