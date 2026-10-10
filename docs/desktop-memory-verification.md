# Reviewed desktop memory validation

The public snapshot contains 117 offline tests, including 21 reviewed-note reader tests. Fixtures are generated in temporary directories; the checked-in demonstration is explicitly fictional. No private diary, recording or credential is required.

## Reproduce

```sh
python3 -m unittest discover -s tests -v
python3 examples/desktop-memory/write-demo-config.py
python3 bin/desktop-memory --config .local/desktop-memory-demo.json read --date 2000-01-01
```

Coverage includes curation status/privacy/path/hash gates, edited-note rejection, symlink containment, date and output limits, authentication-shaped content holds, per-day corrupt-checkpoint isolation, immutable search snapshots, and no note/checkpoint mutation. Calendar underflow, corrupt daily records, snapshot rereads and malformed curation scalars failed added regression tests on the earlier implementation and passed after correction.

An earlier local Codex App fresh-context evaluation selected the skill for a personal-history question and performed no retrieval for an unrelated language question. This is historical same-family evaluation, not public CI proof of model behavior on every machine. Follow the integration guide to test the user's authorized setup.

Live recorder fallback, future implicit model choices, remote-executor access, complete capture coverage and formal typing are outside the offline suite. The reader reports saved cloud receipts without advancing them. Privacy/review holds are not absence of memory and do not authorize a raw-record fallback.
