# Where the opponent model's population baseline comes from

`OPPONENT_MODEL_DESIGN.md`'s open question Q1: before the bot has played a
single hand, what should it assume the *average* opponent does? This document
answers it with measurements taken on this laptop on 2026-09-16, not with
opinion.

---

## In plain words

The bot judges a person by comparing them with a typical player. A player who
folds more than typical is a target for bluffs; one who calls more than typical
is a target for value bets. So the bot needs a "typical player" to compare
against. The design calls that typical player `BASELINE`.

There are two ways to get one.

1. **Borrow it.** Take a pile of recorded hands that strangers played years ago,
   work out what the typical player did in them, and start with that.
2. **Earn it.** Sit at the table, fold every hand, watch, and build the typical
   player out of what the bot actually sees. The design calls this
   *observe-first*.

Borrowing is only worth doing if the borrowed typical player resembles the real
one. To find out, two piles of recorded hands were downloaded and measured:

- **The archive the question names**, from a 1990s chat-server poker game. It
  turns out to be almost entirely *fixed-limit* poker, where the size of every
  bet is fixed in advance. Our game is *no-limit*, where any bet can be any
  size up to everything in front of you.
- **A second archive of real-money no-limit hands from 2009**, which is the
  closest large free thing to the game the bot will actually play.

The measurements are blunt. In the 1990s fixed-limit archive the typical
nine-handed player put money in before the flop **39.6%** of the time. In the
2009 no-limit archive the typical nine-handed player did it **13.9%** of the
time. That is not a small difference in degree; it is a different game. Starting
the bot with the first number would tell it that nearly everyone at the table is
a wild gambler, and it would bluff into people who are not there.

**The recommendation is observe-first.** The numbers behind it, and the point at
which watching beats borrowing, are below.

Two terms used throughout, each explained before it is named. How often a player
voluntarily puts money in before the shared cards appear is *voluntarily put
money in pot*, **VPIP**. How often they raise before those cards is *preflop
raise*, **PFR**. How much they bet and raise after the cards appear, set against
how much they merely call, is the *aggression factor*, **AF** (2.0 means twice
as many bets and raises as calls). How often they fold when the player who
raised before the flop bets again on the flop is *fold to continuation bet*,
**FtCB**. How often they stay in a hand until the cards are turned face up is
*went to showdown*, **WTSD**.

---

## 1. What was measured, and on what

Nothing below is quoted from anybody else's summary. Two corpora were fetched to
a scratch directory outside this repository, parsed by two scripts committed
beside this document, and the scripts' raw output is committed too.

| | Corpus A | Corpus B |
| --- | --- | --- |
| Name | HandHQ no-limit cash logs inside the Poker Hand Histories dataset | IRC Poker Database, `holdem` channel |
| Game | **No-limit** hold'em, real money | **Fixed-limit** hold'em, play money |
| Era | 1-23 July 2009 | 1995-2001 (months parsed: Jan-Dec 1999) |
| Where from | `github.com/uoftcprg/phh-dataset` (MIT); full archive `zenodo.org/records/17136841` (CC BY 4.0) | `poker.cs.ualberta.ca/IRC/IRCdata.tgz` |
| Downloaded | 962 of the repository's 21,782 `.phhs` files, 706 MB | 548 MB of the 1,017,569,472-byte archive |
| Hands parsed | **949,193** | **447,669** distinct hands, 3,148,025 player-hand rows |
| Players seen | 88,898 distinct codes | 6,285 distinct nicknames |
| Parser | `research/parse_handhq_baseline.py` | `research/parse_irc_baseline.py` |
| Raw output | `research/handhq_baseline_output.txt` | `research/irc_baseline_output.txt` |

**The corpus is not in this repository and must never be.** Both scripts take a
`--corpus` path. The scratch copy used here lived in the session scratchpad and
came to 1.2 GB.

**Timings, with the 1-minute load average beside each, because other agents
share this laptop** (10-core Intel, macOS 15.2, Python 3.13.15):

| Step | Wall clock | 1-minute load average | When (UTC) |
| --- | --- | --- | --- |
| Download, corpus A (962 files, 706 MB, 12 parallel connections) | ~21 min | 3.85 start, 2.58 end | 02:38-02:59 |
| Download, corpus B (548 MB of one file, single connection) | ~30 min, **not finished** | 3.57 start, 3.40 at cut-off | 02:33-03:03 |
| **Parse, corpus A: 949,193 hands** | **2.3 s** on 8 worker processes (16.3 s of CPU) | 2.54 before, 3.13 after | 03:00 |
| **Parse, corpus B: 447,669 hands** | **3.6 s**, single process | 3.40 before, 3.40 after | 03:02 |
| Per-slice re-runs (20 network/stake slices, one run each) | ~40 s total | 3.3 | 03:03 |

Parsing is not the expensive part. **Downloading is**, at roughly 0.7 MB/s to
GitHub and 0.3 MB/s from Alberta while both ran at once. Parsing the entire
21.6-million-hand no-limit corpus would take about a minute of CPU on this
machine and about seven hours of downloading.

### What the sample is, and where it is thin

The 962 files were meant to be a stratified sample of all 27 network/stake
slices. The download was stopped early for time, so the sample it actually
produced is this, and the skew is stated rather than hidden:

- 20 of the 27 slices are present. **PartyPoker is absent entirely** - and it is
  the largest network in the corpus at 8,298,718 hands. Three PokerStars slices
  (50NL, 400NL, 600NL) are absent.
- Present: PokerStars 25NL (220 files, the deepest slice here), PokerStars 200NL
  (22) and 1000NL (40); all six Absolute Poker slices, all three Full Tilt, all
  five iPoker and all three Ongame slices at 40 files each.
- Because 40-file slices are spread across high stakes while only one micro-stake
  slice is deep, **the pooled figures below lean higher-stakes than the corpus as
  a whole**, which pushes VPIP down and PFR up relative to a true whole-corpus
  number. Section 4 measures how large that lean is and uses it, rather than
  wishing it away.

---

## 2. Corpus A: the 2009 no-limit population, per table size

Table size is the number of players **dealt in** (`len(players)`). Only 33.9% of
hands declare a seat count at all, so this is the fallback
`RESOURCES_EXPLOITATION.md` section 3.1 established: a nine-chair table with six
people sitting reads as six.

A player enters a row only after **100 hands at that table size**. Q1/median/Q3
are the quartiles across those players: a quarter of players sit below Q1, half
below the median, a quarter above Q3.

| Seats | Hands | Players | Qualifying | VPIP Q1/med/Q3 | PFR Q1/med/Q3 | AF Q1/med/Q3 | FtCB Q1/med/Q3 | WTSD Q1/med/Q3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 144,730 | 7,733 | 763 | 46.0 / **52.4** / 59.8 | 30.9 / **38.3** / 44.3 | 1.87 / **2.59** / 3.79 | 33.3 / **44.4** / 55.6 | 25.0 / **30.3** / 35.2 |
| 3 | 35,338 | 12,768 | 134 | 26.3 / **29.7** / 34.7 | 20.0 / **23.6** / 27.7 | 1.96 / **2.65** / 3.78 | 33.3 / **50.0** / 66.7 | 24.5 / **30.4** / 36.9 |
| 4 | 95,361 | 26,662 | 632 | 22.2 / **26.1** / 31.5 | 16.4 / **20.0** / 23.9 | 2.00 / **2.75** / 4.02 | 33.3 / **50.0** / 66.7 | 23.3 / **29.6** / 35.9 |
| 5 | 234,011 | 43,079 | 2,261 | 19.9 / **23.5** / 28.8 | 13.4 / **16.8** / 20.2 | 1.89 / **2.67** / 4.00 | 37.5 / **50.0** / 66.7 | 22.7 / **28.6** / 35.0 |
| 6 | 258,859 | 51,514 | 3,032 | 17.6 / **21.2** / 26.4 | 11.0 / **14.2** / 17.4 | 1.76 / **2.67** / 4.00 | 40.0 / **50.0** / 66.7 | 21.4 / **27.1** / 33.3 |
| 7 | 34,362 | 27,792 | 268 | 9.4 / **13.3** / 17.2 | 4.7 / **7.7** / 11.4 | 1.80 / **2.60** / 4.50 | 40.0 / **60.0** / 100.0 | 18.2 / **26.1** / 33.3 |
| 8 | 70,170 | 36,446 | 1,006 | 10.7 / **14.1** / 18.2 | 5.3 / **7.8** / 10.6 | 1.65 / **2.54** / 4.00 | 39.2 / **55.6** / 83.0 | 20.0 / **26.4** / 33.3 |
| 9 | 70,685 | 34,101 | 1,237 | 10.2 / **13.9** / 18.2 | 4.9 / **7.2** / 9.9 | 1.51 / **2.35** / 3.84 | 40.0 / **60.0** / 85.2 | 19.4 / **25.6** / 33.3 |
| 10 | 5,677 | 2,196 | 137 | 9.8 / **12.3** / 15.5 | 6.5 / **8.2** / 10.6 | 1.68 / **2.67** / 4.19 | 41.4 / **60.0** / 100.0 | 18.5 / **27.6** / 40.0 |

All figures are percentages except AF, which is a ratio. Ten-seat tables exist in
this corpus; the brief asked for 2-9 and the tenth row is included because it is
there.

**The pooled rate** - every numerator added up over every denominator, with no
hand floor, which is the exact shape `OPPONENT_MODEL_DESIGN.md` section 4.3 gives
`BASELINE`:

| Seats | VPIP | PFR | AF | FtCB | WTSD | FtCB chances per hand | Flops seen per hand |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 0.520 | 0.357 | 2.49 | 0.450 | 0.306 | 0.084 | 0.373 |
| 3 | 0.357 | 0.219 | 2.37 | 0.472 | 0.313 | 0.052 | 0.268 |
| 4 | 0.310 | 0.186 | 2.33 | 0.491 | 0.307 | 0.045 | 0.230 |
| 5 | 0.284 | 0.161 | 2.27 | 0.497 | 0.301 | 0.045 | 0.219 |
| 6 | 0.265 | 0.140 | 2.23 | 0.513 | 0.289 | 0.043 | 0.212 |
| 7 | 0.230 | 0.094 | 2.11 | 0.536 | 0.286 | 0.031 | 0.212 |
| 8 | 0.216 | 0.087 | 2.08 | 0.543 | 0.288 | 0.030 | 0.198 |
| 9 | 0.206 | 0.081 | 2.06 | 0.548 | 0.281 | 0.030 | 0.187 |
| 10 | 0.167 | 0.085 | 2.26 | 0.535 | 0.292 | 0.023 | 0.127 |

Two side-results worth keeping, both of which the design currently carries as
admitted placeholders in its Table C:

- **Chances per hand are measured now, not guessed.** A fold-to-continuation-bet
  chance arrives 0.030 times per hand at nine-handed and 0.084 at heads-up; the
  design's placeholder for that row is 0.15, so it is **five times optimistic**
  at a full table, and the hands needed for a usable FtCB number are five times
  what Table C says.
- The parser's structural test for "this hand reached a showdown" agrees with the
  logs' own record of cards being shown on **93.6% to 97.7%** of hands at every
  table size from 2 to 9. That is the parser checking itself against the corpus.

### How many hands does the archive hold *per person*

This is the question that decides whether an archive can profile an individual
rather than a population.

| Seats | Players with 30+ hands | 100+ | 200+ | 1,000+ |
| --- | --- | --- | --- | --- |
| 2 | 1,900 | 763 | 327 | 13 |
| 5 | 6,857 | 2,261 | 1,043 | 95 |
| 6 | 9,031 | 3,032 | 1,425 | 118 |
| 8 | 3,888 | 1,006 | 355 | 3 |
| 9 | 4,531 | 1,237 | 451 | 7 |

Across all table sizes: **9,743 players have 100 or more hands, and 612 have
1,000 or more**, out of 88,898. So roughly **11% of the people in this sample
have enough hands for a stable preflop read, and 0.7% have enough for a postflop
one** - and every one of them is a 2009 anonymised code who will never sit at the
operator's table.

---

## 3. Corpus B: the IRC archive the question names

One correction to the question first: **the IRC archive is not a 2009 archive.**
It is 1995-2001. The 2009 archive is the separate HandHQ no-limit one measured
above. The two get conflated easily and they answer differently.

The IRC `holdem` channel is **fixed-limit**, and that is what the numbers below
describe. Twelve monthly files for 1999 were extracted from the part of the
archive that had downloaded, one of which was truncated and discarded.

| Seats | Hands | Players | Qualifying | VPIP Q1/med/Q3 | PFR Q1/med/Q3 | AF Q1/med/Q3 | WTSD Q1/med/Q3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 87,839 | 1,999 | 215 | 40.1 / **48.8** / 56.2 | 11.0 / **21.8** / 34.7 | 1.45 / **2.04** / 2.96 | 35.6 / **42.1** / 48.8 |
| 3 | 103,948 | 2,667 | 234 | 45.1 / **53.0** / 62.1 | 8.8 / **16.7** / 28.5 | 1.16 / **1.67** / 2.27 | 36.9 / **41.8** / 47.3 |
| 4 | 106,213 | 3,200 | 237 | 40.1 / **50.0** / 59.6 | 6.6 / **14.0** / 21.1 | 1.02 / **1.49** / 2.02 | 34.6 / **40.0** / 45.5 |
| 5 | 124,818 | 3,633 | 275 | 37.0 / **47.9** / 57.4 | 5.9 / **11.0** / 17.9 | 0.83 / **1.35** / 1.88 | 33.3 / **39.1** / 44.5 |
| 6 | 213,917 | 4,199 | 484 | 33.3 / **44.5** / 55.6 | 4.6 / **8.0** / 14.5 | 0.75 / **1.16** / 1.58 | 34.1 / **38.7** / 43.3 |
| 7 | 305,259 | 4,712 | 669 | 32.0 / **41.4** / 54.3 | 3.8 / **7.5** / 12.0 | 0.73 / **1.07** / 1.53 | 32.9 / **37.1** / 42.4 |
| 8 | 422,135 | 5,150 | 903 | 30.4 / **40.5** / 53.7 | 3.6 / **6.8** / 11.4 | 0.71 / **1.03** / 1.45 | 31.8 / **36.7** / 41.7 |
| 9 | 611,702 | 5,366 | 1,215 | 29.4 / **39.6** / 53.0 | 3.3 / **6.1** / 10.5 | 0.67 / **0.97** / 1.34 | 31.7 / **36.5** / 41.4 |
| 10 | 1,172,194 | 5,360 | 1,846 | 29.8 / **40.0** / 54.1 | 3.3 / **6.1** / 10.3 | 0.65 / **0.92** / 1.27 | 31.3 / **36.0** / 41.3 |

Counts are player-hand rows, not distinct hands. WTSD here uses "the log recorded
this player's cards" as a stand-in for reaching a showdown, because the IRC
per-player record stores each street as that one player's own actions with no
ordering between players. For the same reason **fold-to-continuation-bet cannot
be computed from the IRC format at all** without rebuilding every betting
sequence from the roster, and this document does not claim it.

What the IRC corpus does have that the no-limit one does not: **real nicknames**,
and deep per-person samples - 3,038 players with 100+ hands and **700 with
1,000+**, out of 6,285. It is a far better corpus for *testing* profiling code
than the no-limit one. It is a far worse corpus for *seeding* a no-limit prior.

### The two corpora side by side, nine-handed

| | IRC 1999, fixed-limit | HandHQ 2009, no-limit | Gap |
| --- | --- | --- | --- |
| Median VPIP | 39.6% | 13.9% | **25.7 points** |
| Median PFR | 6.1% | 7.2% | 1.1 points |
| Median AF | 0.97 | 2.35 | **2.4x** |
| Median WTSD | 36.5% | 25.6% | **10.9 points** |
| Pooled VPIP | 0.399 | 0.206 | **19.3 points** |
| Flops seen per hand | 0.446 | 0.187 | **2.4x** |

Every gap is in the direction fixed-limit betting predicts. When a call costs one
small bet and can never cost a stack, players see nearly two and a half times as
many flops and call rather than raise. Transplanting that player into a no-limit
game as "average" is not a small error.

---

## 4. Is a 2009 fixed-limit-heavy corpus a usable prior for today's no-limit games

Stated plainly, in three parts.

**The IRC archive: no.** Not as a baseline for no-limit play. Its no-limit
channel is a rounding error - 9,447 hands over ten months, of which 135 are at
7-9 seats, as `RESOURCES_EXPLOITATION.md` section 3.2 counted from the archive.
Its limit-hold'em population sits 25.7 VPIP points away from the no-limit
population at the same table size. It remains useful for two other things: a
named-player corpus for testing the counting and shrinkage code, and a
reproduction target for the published clustering studies.

**The 2009 no-limit archive: usable only as a warm-up, at a weight it has to
earn.** It is the right game, the right table sizes and real money. What it is
not is *this* table. Three named holes:

1. **Era.** Seventeen years. Nothing in this measurement bounds that drift,
   because no modern corpus of the same kind is free to fetch.
2. **Stake and network.** Measured here, and it is large. Running the same parser
   over each slice separately, the median six-handed player's VPIP ranges from
   **17.0%** (Full Tilt 50NL) to **25.7%** (Absolute Poker 1000NL), and the
   pooled six-handed VPIP from **0.234** (iPoker 400NL) to **0.313** (Absolute
   Poker 50NL). That is a spread of roughly **8 VPIP points inside a single
   three-week window**, before a single day of era drift is added.
3. **Format.** The operator's likely table is a phone or club app, which is not
   any of these six networks.

**The modern comparison.** Poker Copilot, a Mac tracking product, publishes a
statistics guide (visited 2026-09-16, HTTP 200) that gives player types by
VPIP/PFR from its own users' databases. Its figures: solid six-handed regulars
"generally have a VPIP/PFR between 19/17 and 25/23", winning regulars at higher
stakes "closer to 28/20 or 27/19", full-ring winning regulars "between 11/8 and
16/14", losing players 30/5 to 40/15, and "whales" 52/5 to 75/10. Set against the
2009 corpus measured above - six-handed median 21.2/14.2, nine-handed median
13.9/7.2 - **the six-handed VPIP agrees within about two points, and the PFR is
three to eight points lower in 2009 than the vendor's modern winning range.**
That is the expected direction: the population has become more aggressive
preflop since 2009 without playing many more hands. Two cautions, because this is
the weakest evidence in the document: the guide is dated 2016-2017, and it
describes *player types and winning ranges*, not a measured population median. No
free, verifiable, present-day population median for online no-limit was found;
that hole is named here rather than papered over.

### The shrinkage weight the warm-up would need

`OPPONENT_MODEL_DESIGN.md` section 4.3 blends an opponent's own counts with the
baseline:

    rate = (BASELINE * s + k) / (s + n)

where `n` is how many chances the bot has seen and `s` is `PRIOR_STRENGTH` - the
number of observed hands at which the prior and the data carry equal weight. The
design sets `s = 50` for VPIP, PFR and limp, and says in its own words that 50 is
an unmeasured starting value.

A prior that is *wrong by a fixed amount* deserves a weight that can be computed
rather than chosen. If the prior misses the truth by `d`, and the true rate is
`p`, the weight that minimises the expected squared error is

    s* = p(1-p) / d²

which is also, by construction, the number of observed hands at which the
opponent's own data starts beating the prior. Putting the gaps measured above
into it:

| Prior seeded from | Stat | Gap `d` | True-rate anchor `p` | **`s*`** |
| --- | --- | --- | --- | --- |
| IRC fixed-limit, nine-handed | VPIP | 0.257 (medians) | 0.139 | **2 hands** |
| IRC fixed-limit, nine-handed | VPIP | 0.193 (pooled) | 0.206 | **4 hands** |
| IRC fixed-limit, nine-handed | WTSD | 0.109 | 0.256 | **16 chances** |
| 2009 no-limit, wrong stake/network only | VPIP | 0.079 (pooled spread) | 0.265 | **31 hands** |
| 2009 no-limit, wrong stake/network only | VPIP | 0.087 (median spread) | 0.212 | **22 hands** |

Read the rows plainly. **An IRC-seeded baseline is worth about two to four hands
of observation** - the bot passes it inside its first orbit, so it is not worth
writing. **A stake-matched 2009 no-limit baseline is worth about 22 to 31 hands**,
so it would enter the design at `PRIOR_STRENGTH` of roughly **25, not 50** - and
that is the *optimistic* figure, because it charges the prior only for being at
the wrong stake and network and nothing at all for being seventeen years old. Any
honest era term drives it lower.

---

## 5. Recommendation

**Observe first. Do not seed `BASELINE` from either archive; leave
`OPPONENT_MODEL_DESIGN.md` section 4.3 exactly as it is.**

The reason, in one line: the best prior either archive can offer is worth fewer
than about thirty hands of watching, and the bot's Tier 0 observation mode
collects that in minutes, with no licence question, no era gap and no stake
mismatch.

**The crossover, as one number: 30 hands.** After roughly **30 observed hands of
an opponent**, that opponent's own counts beat anything the 2009 no-limit archive
can say about them; against an IRC-seeded prior the crossover is **4 hands**. At
the population level the crossover is smaller still, because the pooled baseline
pools every player at the table: about **30 player-hands**, which is four orbits
at a nine-handed table, or roughly **four minutes of folding**.

What to do with the archives instead, in priority order:

1. **Test with the IRC corpus.** It has real nicknames and 700 players with 1,000+
   hands. Point the counter, the shrinkage and the bucketing at it and check they
   reproduce sane distributions before any of it sees a live table.
2. **Replace the design's invented opportunity rates with the measured ones** in
   section 2 above, which cost nothing to adopt and fix a five-fold error in
   Table C's fold-to-continuation-bet row.
3. **Keep the 2009 no-limit corpus as the sanity check** on the bot's own pooled
   baseline once Tier 0 has logged its first few thousand hands: if the bot's own
   population and the 2009 one disagree by more than the 8-point stake spread
   measured here, something is wrong with the counting, not with the population.

If the operator overrules this and wants a seeded warm-up anyway, the safe form
is narrow: seed only `vpip` and `pfr`, only from the stake-and-table-size-matched
slice, at `PRIOR_STRENGTH = 25`, and retire it the moment
`MIN_POOL_OPPONENTS = 20` qualifying opponents exist in the bot's own database.

### Rated against the operator's five

| Test | Rating | Why |
| --- | --- | --- |
| (a) 2-9 players | **Yes** | Both corpora and both parsers report every size from 2 to 10; the no-limit corpus carries 70,685 nine-handed hands even in this sample. |
| (b) True no-limit | **Yes for corpus A, no for corpus B** | A is real-money no-limit throughout. B is fixed-limit apart from 9,447 no-limit hands. |
| (c) Exploiting specific opponents by identity | **No** | Corpus A's players are anonymised 2009 codes; corpus B's nicknames are real but the people left the internet twenty years ago. Neither can name anyone at the operator's table. Only observe-first can. |
| (d) Hours on one laptop | **Yes** | Parsing 949,193 hands took 2.3 seconds. Downloading is the cost: 21 minutes for 706 MB, and about seven hours for the whole 16 GB no-limit corpus. |
| (e) Fits a public GPL-3.0 repository | **Yes, with the corpus kept out** | Corpus A is MIT on GitHub and CC BY 4.0 on Zenodo. Corpus B states copyright with no grant, so it is read and measured and never copied in. Both parsers take a `--corpus` path; nothing but numbers is committed. |

---

## 6. Every source, and how it was checked

Each was fetched from this laptop on 2026-09-16 (2026-09-17 UTC). Where a
statement rests on a number, the number came from the fetched bytes, not from a
summary of them.

- **`github.com/uoftcprg/phh-dataset`** - GitHub API, HTTP 200. Licence endpoint
  returns `MIT`. The full file tree was fetched in one request and counted:
  **21,782 `.phhs` files, 16.31 GB, across 27 network/stake directories**. Per-file
  listings confirmed the PokerStars 25NL directory alone holds 4,379 files.
- **`zenodo.org/doi/10.5281/zenodo.10796885`** - HTTP 200, redirects to record
  `17136841`, v3, published 2025-09-16. Rights: **Creative Commons Attribution 4.0
  International**. Its description states **21,605,687 uncorrupted no-limit
  hold'em hands** scraped 1-23 July 2009 and the per-network counts used above
  (PartyPoker 8,298,718; iPoker 5,996,345; PokerStars 3,092,698; Ongame
  1,647,765; Full Tilt 1,299,503; Absolute 1,270,658).
- **`raw.githubusercontent.com/...`** - 962 `.phhs` files fetched, 706 MB. Player
  codes were checked for stability across files before any aggregation: three
  consecutive PokerStars 25NL files share **1,080 of 1,178, 1,031 of 1,178 and
  1,094 of 1,162** player codes pairwise, so a code means the same person across
  the slice and per-player totals are meaningful.
- **`poker.cs.ualberta.ca/irc_poker_database.html`** - HTTP 200, fetched and read.
  States "more than 10 million complete hands" logged 1995-2001 by Michael
  Maurer's Observer bot, "may be useful to poker programming researchers and
  hobbyists", and carries "Copyright (c) 2017 by the Computer Poker Research
  Group" with **no grant of any kind**. Nothing from it is copied into this
  repository.
- **`poker.cs.ualberta.ca/IRC/IRCdata.tgz`** - `curl -sI` returns HTTP 200,
  `Content-Length: 1017569472`, `Last-Modified: Sat, 16 Mar 2019 03:02:32 GMT`.
  547,725,312 bytes had arrived when the download was cut off for time; the
  archive is a tar of per-channel monthly files, so the twelve 1999 `holdem`
  members that had fully arrived were extracted and parsed.
- **`pokercopilot.com/poker-statistics`, `/poker-statistics/vpip-pfr`** - HTTP
  200, fetched and read. Guide dated 28 August 2017, chapter dated 5 December
  2016. Source of every modern figure quoted in section 4, verbatim.
- **Searched for and not found:** a free, verifiable, present-day (2024-2026)
  published population median for online no-limit cash. Two search engines
  returned HTTP 202 bot-checks; six candidate vendor and strategy pages
  (`upswingpoker.com`, `redchippoker.com`, `thepokerbank.com`, `888poker.com`,
  `pokerstrategy.com`, `gtowizard.com/blog`) returned HTTP 404 on the paths
  tried. This is a hole in the evidence and is treated as one: the era term in
  section 4 is argued from direction, not from a measured number.

### Reproducing the numbers

    python3 research/parse_handhq_baseline.py --corpus <scratch>/phh/files \
        --min-hands 100 --workers 8 --out research/handhq_baseline_output.txt

    python3 research/parse_irc_baseline.py --corpus <scratch>/irc/IRCdata/holdem \
        --out research/irc_baseline_output.txt

Both need only the standard library. The per-slice spread in section 4 comes from
running the first script once per slice directory with no other change.
