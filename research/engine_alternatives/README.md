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
| `pypoker_playouts.py` | PyPokerEngine's `Emulator` API driven as a search would drive it - per-seat stacks, "what is legal here", clone a position and play the clone out - and how many play-outs a second that buys. |
| `bench_requirements.py` | The pass/fail checks behind the candidate sections: distinct legal bet sizes, seat counts that work, chips conserved over piles of random hands, and which sub-packages import on this Python. |
| `paired_session.py` | Runs `chooser.py` twice, `bench_speed.py`, `resample_opponents.py` and `pypoker_playouts.py` back to back, several times over, recording the machine's load average beside every figure. Timings from different sessions on this laptop are not comparable, and most of the numbers in `ENGINE_ALTERNATIVES.md` are compared with each other, so this is how they are taken. |
| `raw/` | The exact output of the runs quoted in `ENGINE_ALTERNATIVES.md`. |

## The game every file uses

52 cards, no-limit, 6 seats, 20,000-chip stacks (200 big blinds), blinds
50/100, four betting rounds, unless a file says otherwise. Two betting
abstractions appear throughout and the difference is large:

- `fcpa` - fold / call / pot-sized bet / all-in. A four-move menu.
- `fullgame` - every whole-chip raise-to amount is a separate legal move;
  19,803 of them at the first decision of this game.

## How to run them

These need the candidate engines, which the project's own tests do not use.
Install them into a throwaway environment - `.venv-engines/` is already ignored
by git - and run from inside this directory:

    python3 -m venv .venv-engines
    .venv-engines/bin/pip install open_spiel==2.0.2 texasholdem==0.11.0 \
        pokerkit==0.7.5 pypokerengine==1.0.1 rlcard==1.2.0 clubs==0.1.4

**Start with the paired session.** It is the one that produces the play-out
counts, the engine speeds and the redraw rates, and it produces them in an order
that makes them comparable with each other:

    cd research/engine_alternatives
    ../../.venv-engines/bin/python paired_session.py 6 10   # -> raw/paired_session.txt

The rest are run on their own, because nothing else is compared against them:

    ../../.venv-engines/bin/python bench_cfr.py 45          # -> raw/cfr.txt
    ../../.venv-engines/bin/python bench_requirements.py    # -> raw/requirements.txt
    ../../.venv-engines/bin/python bench_play.py variance 100000
    ../../.venv-engines/bin/python bench_play.py headtohead 900

And each program the paired session drives can be run singly, which is how to
read what it is doing:

    ../../.venv-engines/bin/python bench_speed.py 10
    ../../.venv-engines/bin/python chooser.py fcpa 20 0.25
    ../../.venv-engines/bin/python chooser.py fullgame 20 0.25
    ../../.venv-engines/bin/python resample_opponents.py 10
    ../../.venv-engines/bin/python pypoker_playouts.py 10

## Reading a timing off this machine

This laptop is not idle, and its throughput moves by a factor of two with what
else is running. So two rules apply to every timing quoted in
`ENGINE_ALTERNATIVES.md`, and `paired_session.py` enforces both:

- **Check the machine is quiet first.** The one-minute **load average** is
  roughly how many programs were queued waiting for a processor core; this
  machine has 10 cores, and above about 4 the timings stop meaning anything.
  The session waits while the load is above 4, for up to 30 minutes, then runs
  anyway and says in the output that it did.
- **Record the load beside the figure**, and quote a range over repeats rather
  than a single number. Every `--- ... ---` banner in `raw/paired_session.txt`
  carries the load average the run beneath it started at.

Measured on macOS 15.2 (24.2.0), Apple M4, 10 cores, 16 GiB, Python 3.13.15,
`open_spiel` 2.0.2, on 2026-09-15 and 2026-09-16.
