"""The IRC corpus shape as a fixture: the counter against the survey's reader.

`OPPONENT_BASELINE.md` section 5 item 1 says what the IRC Poker Database is
for -- "Test with the IRC corpus. Point the counter, the shrinkage and the
bucketing at it and check they reproduce sane distributions before any of it
sees a live table" -- and nothing else. It is not a baseline: `BASELINE` is
observed from the bot's own hands, never seeded from an archive.

**Nothing from the real corpus is committed here.** That corpus "states
copyright with no grant, so it is read and measured and never copied in"
(`OPPONENT_BASELINE.md` section 1). What this file builds instead is a small
run of hands written in the corpus's own `pdb` line format, from the table in
`ADA` below, so that `research/parse_irc_baseline.py` -- the reader that
document's numbers came out of -- can be pointed at it unchanged. The test
then feeds the same hands to the notebook and checks the two agree.

The line format, from that script's own docstring:

    AAiyAAh   916828992  9  5 r   rc    r     rr        1000  180    0 4c Jd
    name      timestamp  n  pos pre flop  turn  river   bank  bet  won [cards]

Action letters: `-` no action, `B` posted blind, `f` fold, `k` check, `b` bet,
`c` call, `r` raise, `A` all-in.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from pokerbot.notebook import Notebook
from pokerbot.record import SCHEMA, Event, HandRecord

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "parse_irc_baseline.py"

SEATS = 6
SMALL_BLIND, BIG_BLIND = 1, 2
#: Fixed-limit bet sizes, small bet before the turn and big bet after, which
#: is the structure the IRC hold'em channel played.
BET_SIZE = (2.0, 2.0, 4.0, 4.0)
STREET_KEYS = ("pre", "flop", "turn", "river")

#: The one player the two readers are compared on. Four kinds of hand, each
#: repeated, chosen so the figures come out round and the arithmetic in
#: `test_the_counter_agrees_with_the_surveys_own_reader` can be followed.
#:
#:   ten hands  raise and bet every street, and show
#:   ten hands  call and call every street, and show
#:   five hands call, then fold to the flop bet
#:   25 hands   fold before the flop
ADA = "ada"
ADA_POSITION = 3  # never in a blind, so the blinds never confuse the picture
HAND_KINDS = (
    ("bettor", 10),
    ("caller", 10),
    ("flop_folder", 5),
    ("preflop_folder", 25),
)

#: Everyone else. Ten names over five seats and fifty hands is 25 hands each,
#: which is below the hand floor the test asks the script for, so `ada` is the
#: only player in the quartile table and its median *is* her rate.
OTHERS = (
    "bea", "cleo", "dot", "edie", "flo",
    "gil", "hana", "iris", "jo", "kit",
)


def _rows_for(kind: str) -> dict[int, dict[str, str]]:
    """One hand's action strings, by position. Position 1 and 2 post blinds."""
    blank = {"pre": "-", "flop": "-", "turn": "-", "river": "-", "shown": False}
    rows = {pos: dict(blank) for pos in range(1, SEATS + 1)}
    rows[1]["pre"] = "Bf"
    rows[2]["pre"] = "Bf"
    for pos in (5, 6):
        rows[pos]["pre"] = "f"
    if kind == "bettor":
        rows[3] |= {"pre": "r", "flop": "b", "turn": "b", "river": "b", "shown": True}
        rows[4] |= {"pre": "c", "flop": "c", "turn": "c", "river": "c", "shown": True}
    elif kind == "caller":
        rows[3] |= {"pre": "cc", "flop": "kc", "turn": "kc", "river": "kc", "shown": True}
        rows[4] |= {"pre": "r", "flop": "b", "turn": "b", "river": "b", "shown": True}
    elif kind == "flop_folder":
        rows[3] |= {"pre": "cc", "flop": "kf"}
        rows[4] |= {"pre": "r", "flop": "b"}
    elif kind == "preflop_folder":
        rows[3]["pre"] = "f"
        rows[4]["pre"] = "r"
    else:  # pragma: no cover - the four kinds above are the whole table
        raise ValueError(kind)
    return rows


def hands() -> list[tuple[int, dict[int, dict[str, str]], dict[int, str]]]:
    """Fifty hands: the timestamp, the action strings, and who sat where."""
    out = []
    kinds = [kind for kind, count in HAND_KINDS for _ in range(count)]
    for index, kind in enumerate(kinds):
        seated = {ADA_POSITION: ADA}
        spare = [pos for pos in range(1, SEATS + 1) if pos != ADA_POSITION]
        for offset, pos in enumerate(spare):
            seated[pos] = OTHERS[(index * len(spare) + offset) % len(OTHERS)]
        out.append((900_000_000 + index, _rows_for(kind), seated))
    return out


def write_corpus(root: Path) -> Path:
    """Write the fixture out in the corpus's own directory and line shape."""
    folder = root / "199501" / "pdb"
    folder.mkdir(parents=True)
    lines = []
    for stamp, rows, seated in hands():
        for pos in range(1, SEATS + 1):
            row = rows[pos]
            fields = [
                seated[pos], str(stamp), str(SEATS), str(pos),
                row["pre"], row["flop"], row["turn"], row["river"],
                "1000", "8", "0",
            ]
            if row["shown"]:
                fields += ["4c", "Jd"]
            lines.append(" ".join(fields))
    (folder / "pdb.holdem").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# the bridge: one IRC hand, written out as a HandRecord
# ---------------------------------------------------------------------------


def record_from_hand(rows, seated) -> HandRecord:
    """Turn one hand's per-player action strings into a record to count.

    The corpus stores each street as one string of that player's own actions
    with no ordering between players (the script's own docstring says so), so
    an order has to be chosen: position order, starting after the blinds
    before the flop and at the small blind after it. Every stat compared
    below -- whether a player put money in, whether they raised, whether they
    saw a flop, whether they showed -- is the same whatever order is chosen.
    """
    button = SEATS - 1  # puts position 1 in the small blind and 2 in the big
    events: list[Event] = []
    for seat, amount in ((0, float(SMALL_BLIND)), (1, float(BIG_BLIND))):
        events.append(
            Event(index=len(events), kind="blind", street=0, seat=seat, amount=amount)
        )
    contributions = [0.0] * SEATS
    contributions[0], contributions[1] = float(SMALL_BLIND), float(BIG_BLIND)
    folded = [False] * SEATS

    letters = {}
    for pos, row in rows.items():
        seat = pos - 1
        letters[seat] = {}
        for street, key in enumerate(STREET_KEYS):
            text = row[key].lstrip("B") if street == 0 else row[key]
            letters[seat][street] = [c for c in text if c not in "-"]

    for street in range(4):
        if street and any(letters[seat][street] for seat in range(SEATS)):
            events.append(Event(index=len(events), kind="board", street=street))
        start = 2 if street == 0 else 0
        order = [(start + i) % SEATS for i in range(SEATS)]
        pointer = {seat: 0 for seat in range(SEATS)}
        committed = {0: float(SMALL_BLIND), 1: float(BIG_BLIND)} if street == 0 else {}
        level = float(BIG_BLIND) if street == 0 else 0.0
        while True:
            moved = False
            for seat in order:
                queue = letters[seat][street]
                if pointer[seat] >= len(queue):
                    continue
                letter = queue[pointer[seat]]
                pointer[seat] += 1
                moved = True
                mine = committed.get(seat, 0.0)
                if letter in "fQK":
                    move, amount = "fold", 0.0
                elif letter == "k":
                    move, amount = "call", 0.0
                elif letter == "c":
                    move, amount = "call", level - mine
                elif letter == "A":
                    move, amount = "all_in", level - mine + BET_SIZE[street]
                else:  # b or r
                    move, amount = "pot", level - mine + BET_SIZE[street]
                events.append(
                    Event(
                        index=len(events),
                        kind="action",
                        street=street,
                        seat=seat,
                        action=move,
                        amount=amount,
                    )
                )
                committed[seat] = mine + amount
                level = max(level, committed[seat])
                contributions[seat] += amount
                if move == "fold":
                    folded[seat] = True
            if not moved:
                break

    return HandRecord(
        schema=SCHEMA,
        commit="irc-fixture",
        seed=0,
        seats=SEATS,
        button=button,
        small_blind=SMALL_BLIND,
        big_blind=BIG_BLIND,
        stacks=[1000.0] * SEATS,
        engine="irc-fixture",
        betting_abstraction="fchpa",
        game_string="irc-fixture",
        events=events,
        hole_cards=[[] for _ in range(SEATS)],
        board=[],
        contributions=contributions,
        payouts=list(contributions),
        net=[0.0] * SEATS,
        folded=folded,
        pot=sum(contributions),
        finished=True,
    )


def run_reader(corpus: Path, min_hands: int) -> str:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--corpus", str(corpus), "--min-hands", str(min_hands)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


def quartile_row(report: str, size: int) -> list[str]:
    """The `size`-handed line of the script's per-table-size distribution."""
    for line in report.splitlines():
        match = re.match(rf"\s*{size}\s+[\d,]+\s+[\d,]+\s+(\d+)\s+(.*)", line)
        if match and int(match.group(1)) > 0:
            return match.group(2).split()
    raise AssertionError(f"the reader printed no {size}-handed row:\n{report}")


# ---------------------------------------------------------------------------
# the test
# ---------------------------------------------------------------------------


def test_the_counter_agrees_with_the_surveys_own_reader(tmp_path):
    """One player, two readers, the same numbers.

    `ada` plays fifty hands: ten she raises before the flop and bets every
    street, ten she calls before the flop and then checks and calls every
    street, five she calls and then folds to the flop bet, and 25 she folds
    before the flop.
    So, by the definitions in `OPPONENT_MODEL_DESIGN.md` section 4.2 and in
    the script's docstring, which are the same definitions:

      hands dealt      50
      vpip             10 + 10 + 5 = 25 of 50        = 0.500
      pfr              10 of 50                      = 0.200
      saw a flop       10 + 10 + 5 = 25
      showed at the end   10 + 10 = 20 of 25         = 0.800
      postflop bets and raises  10 hands x 3 streets = 30
      postflop calls            10 hands x 3 streets = 30
      AF = 30/30                                     = 1.00

    The script is asked for a hand floor of 40, which only `ada` clears --
    the other ten names play 25 hands each -- so the quartiles it prints at
    six seats are hers three times over, and its median is her rate.
    """
    corpus = write_corpus(tmp_path / "corpus")
    report = run_reader(corpus, min_hands=40)
    vpip, pfr, af, wtsd = quartile_row(report, SEATS)
    assert vpip == "50.0/50.0/50.0"
    assert pfr == "20.0/20.0/20.0"
    assert af == "1.00/1.00/1.00"
    assert wtsd == "80.0/80.0/80.0"

    book = Notebook()
    for _stamp, rows, seated in hands():
        record = record_from_hand(rows, seated)
        names = {pos - 1: name for pos, name in seated.items()}
        assert book.observe(record, names)

    assert book.hands(ADA) == 50
    assert book.tally(ADA, "vpip") == (25.0, 50.0)
    assert book.tally(ADA, "pfr") == (10.0, 50.0)
    assert book.tally(ADA, "wtsd") == (20.0, 25.0)
    postflop_br = sum(book.tally(ADA, f"af_bets_raises[{s}]")[0] for s in ("flop", "turn", "river"))
    postflop_calls = sum(book.tally(ADA, f"af_calls[{s}]")[0] for s in ("flop", "turn", "river"))
    assert (postflop_br, postflop_calls) == (30.0, 30.0)

    # The same four figures, formatted the way the script formats them.
    assert f"{book.tally(ADA, 'vpip')[0] / book.hands(ADA) * 100:.1f}" == "50.0"
    assert f"{book.tally(ADA, 'pfr')[0] / book.hands(ADA) * 100:.1f}" == "20.0"
    assert f"{postflop_br / postflop_calls:.2f}" == "1.00"
    k, n = book.tally(ADA, "wtsd")
    assert f"{k / n * 100:.1f}" == "80.0"


def test_the_fixture_is_the_corpus_shape_and_not_the_corpus(tmp_path):
    """Nothing here is copied from an archive that grants no licence."""
    corpus = write_corpus(tmp_path / "corpus")
    lines = (corpus / "199501" / "pdb" / "pdb.holdem").read_text().splitlines()
    assert len(lines) == 50 * SEATS
    assert all(len(line.split()) >= 11 for line in lines)
    names = {line.split()[0] for line in lines}
    assert names == {ADA} | set(OTHERS)
    assert not list(ROOT.glob("tests/data/**/pdb.*"))
