# Working on pokerbot

Read `CLAUDE.md` before making changes. Its project rules also apply to Codex;
this file is an entry point, not a replacement for them. Read `README.md` for
setup, `REFERENCE_NOTES.md` for the current engine's limitations, and
`OPPONENT_MODEL_DESIGN.md` for opponent-model work.

## Current implementation

- `vendor/poker_ai/` is a source copy of the reference engine, not a submodule.
  It currently uses a 20-card deck and fixed-limit betting. Do not describe it
  as a finished standard 52-card no-limit bot.
- `pokerbot/` uses PokerKit with isolated reopening repairs for rules and
  OpenSpiel for frozen equity sampling. Historical unpatched engines are only
  for replay; see `research/REOPENING_REPAIR.md`. Check
  `research/PROGRESS.md` for implemented features and unvalidated claims.
- Original coded strategies and trained models are authorized. Engines retain
  rules and hand ranking; `treys` remains a test oracle.
- There is no laptop compute ceiling. Record actual resource requirements.

## Setup and checks

Use Python 3.13 or newer and one environment at the repository root, `.venv`.
Follow the four setup commands in `README.md`; use `requirements-vendor.txt`
rather than the vendored engine's obsolete dependency pins. The editable install
requires both `--no-deps` and `--no-build-isolation`.

From the repository root:

```sh
.venv/bin/python tools/check_design_numbers.py
.venv/bin/python -m pytest tests -q
(cd vendor/poker_ai && ../../.venv/bin/python -m pytest test -q)
```

Install `requirements-research.txt` for the research harness.
Run the arithmetic checker whenever `OPPONENT_MODEL_DESIGN.md` changes. When
changing the engine or its integration, run the vendor suite as well. Three
vendor CLI tests do not assert command success; passing them does not prove
training works. The ground-truth suite currently exercises `treys` itself,
not a differential comparison with the vendor evaluator.

The engine creates a multiprocessing manager at import time. On macOS, use
the documented command form:

```sh
.venv/bin/python -c "from poker_ai.cli.runner import cli; cli()" --help
```

Keep engine imports in executable scripts behind the `__main__` guard, or in
functions called from that guard. See `research/seat_sweep.py` for an example.
Use the documented single-process training path for bounded smoke runs.

## Contribution workflow

- Inspect `git status` and current upstream changes before editing. Use a
  focused feature branch or worktree and preserve existing user changes.
- Prefer small pull requests with the behavior changed, checks run, and known
  limitations recorded. Keep vendored changes minimal and explain them in
  `REFERENCE_NOTES.md` when applicable.
- Do not commit environments, generated training files, credentials, or local
  caches. Existing `.gitignore` rules cover common generated files.
- Preserve source notices and provenance. Contributor authorization covers
  verified pushes to `codex/tonight`, not merges to main or visibility changes.
