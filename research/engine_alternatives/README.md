# Research artefacts for `ENGINE_ALTERNATIVES.md`

Everything in this directory exists so the numbers in `ENGINE_ALTERNATIVES.md`
can be re-run by someone who does not believe them. **None of it is the bot.**

- It is **not on the bot's import path**: nothing outside this directory
  imports it, and nothing here is packaged or installed.
- It is **not a decision-making component of the project**. The chooser here is
  a measuring instrument used to answer "is a decision-time architecture fast
  enough on this laptop", not a candidate to ship. Whether anything of this
  shape may ship at all is the carve-out question `ENGINE_ALTERNATIVES.md`
  raises against `CLAUDE.md`'s forefront rule, and that question is not settled
  here.
- It is **not covered by the project's tests** and is excluded from them.

## What each file is

| File | What it does |
| --- | --- |
| `chooser.py` | The decision-time chooser: for each of a few candidate moves, guess the opponents' cards, play the hand out at random many times, take the best average. Prints how many rollouts each candidate got, its mean result and the standard error of that mean. |
| `resample_opponents.py` | The workaround for the multiway crash at `universal_poker.cc:1111`: redraws the other seats' hole cards by replaying the hand's history. |
| `bench_speed.py` | Complete hands per second for OpenSpiel (`fcpa` and `fullgame`), `texasholdem` and PokerKit, in both a four-move menu mode and a real-sizing mode, so engines are compared doing equal work. |
| `bench_cfr.py` | External-sampling MCCFR on `universal_poker` with no card abstraction: rounds run and brand-new situations still appearing per round. |
| `bench_play.py` | `variance`: the spread of one seat's per-hand result, which sets how many hands any strength claim needs. `headtohead`: the chooser against five random opponents, reported with a confidence interval. |
| `raw/` | The exact output of the runs quoted in `ENGINE_ALTERNATIVES.md`. |

## The game every file uses

52 cards, no-limit, 6 seats, 20,000-chip stacks (200 big blinds), blinds
50/100, four betting rounds, unless a file says otherwise. Two betting
abstractions appear throughout and the difference is large:

- `fcpa` - fold / call / pot-sized bet / all-in. A four-move menu.
- `fullgame` - every whole-chip raise-to amount is a separate legal move;
  19,803 of them at the first decision of this game.

## How to run them

These need `open_spiel`, `texasholdem` and `pokerkit`, which the project's own
tests do not use. Install them into a throwaway environment - `.venv-engines/`
is already ignored by git - and run from inside this directory:

    python3 -m venv .venv-engines
    .venv-engines/bin/pip install open_spiel==2.0.2 texasholdem==0.11.0 pokerkit==0.7.5

    cd research/engine_alternatives
    ../../.venv-engines/bin/python bench_speed.py 10
    ../../.venv-engines/bin/python bench_cfr.py 45
    ../../.venv-engines/bin/python bench_play.py variance 100000
    ../../.venv-engines/bin/python bench_play.py headtohead 900
    ../../.venv-engines/bin/python chooser.py fcpa 20 0.25
    ../../.venv-engines/bin/python chooser.py fullgame 20 0.25
    ../../.venv-engines/bin/python resample_opponents.py 10

Measured on macOS 15.2 (24.2.0), Apple M4, 10 cores, 16 GiB, Python 3.13.15,
`open_spiel` 2.0.2, on 2026-09-15. Wall-clock timings on a laptop move by tens
of percent between runs; `bench_speed.py` is quoted as a range over repeats for
that reason.
