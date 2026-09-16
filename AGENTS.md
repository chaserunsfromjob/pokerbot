# Working on pokerbot

Read `CLAUDE.md` before making changes. Its project rules also apply to Codex;
this file is an entry point, not a replacement for them. Read `README.md` for
setup, `REFERENCE_NOTES.md` for the current engine's limitations, and
`OPPONENT_MODEL_DESIGN.md` for opponent-model work.

## Current implementation

- `vendor/poker_ai/` is a source copy of the reference engine, not a submodule.
  It currently uses a 20-card deck and fixed-limit betting. Do not describe it
  as a finished standard 52-card no-limit bot.
- Opponent-model modules described under `pokerbot/opponent/` are a design,
  not implemented modules. Engine alternatives are still under evaluation;
  check current branches and documentation before choosing an engine.
- AI-written integration, capture, bookkeeping, and opponent statistics must
  respect the boundary in `CLAUDE.md`. Poker evaluation and action selection
  stay with engine code. `treys` is a test reference only.
- Keep computation within hours on one laptop, as required by `CLAUDE.md`.

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
- `CLAUDE.md` says the project should remain private. Check actual repository
  visibility before proposing publication; do not treat cloning or contributor
  access as authorization to change visibility or distribute the project.
