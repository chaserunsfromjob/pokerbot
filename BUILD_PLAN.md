# Build plan: the reconciliation of the surveys

The surveys are done. This file turns them into one ordered build. Where a
question is already answered it cites the file and section that answers it;
where nothing answers it, it is in "Decisions still yours" and waits for you.

The bar it is built to, in your words: *"we dont need perfection here, just
something that we know is beating real players"*, and *"beating real players by
a lot, 2-9 players, exploitative play. i dont care how you do it. just get it
done."*

## Where we are, as of 17 September 2026

Stages 1, 2 and 3 below are built, reviewed, and landed on `main`: the branch
everything else is cut from, so they are what the project *is* rather than what
it plans.

**Stage 1, the table, is done.** The suite prints a grid — one row for each
table size from two seats to nine, one column for each of the seven statements
that have to hold about every hand the table deals — and every square reads
PASS, bar one. A side pot needs a third player to exist at all, so at two seats
that check cannot be made; that square reads NOT RUN, which is never counted as
a pass.

**Stage 2, the scoreboard, is done.** Its first full run is kept, in full, at
`research/results/stage2_search_vs_personas.txt`. The verdict is ACCEPT against
the version that simply calls every bet. Of the thirteen opponents, the bot
beats seven of them and loses to two, counting a result only where its
ninety-five percent range is clear of zero: the player who waits all night for
a premium hand, and the tight, aggressive one of the two competent players.
Against the remaining four the result is too close to call; one of those, the
player with a bet-size tell, is behind at every seat count but inside the
range. The caveat the README states still stands: those
opponents are caricatures who put money in far more freely than people do, so
the size of that win is a statement about them and not about the bot.

**Stage 3, the notebook, is done.** It watches every hand and counts what each
named player does, and it changes nothing at all about how the bot plays. When
it landed the suite ran 339 tests passing and one skipped; today it is 355 and
one.

**What comes next, in this order.** The baseline (Stage 4), then the bot that
plays the person (Stage 5). That order is yours. Both orders were laid out for
you on 17 September 2026 and the other one was recommended, and you said:
*"i think it should be done the other way."* The stages below are numbered to
match.

**Also landed, beside the stages.** `RESOURCES_DICKREUTER.md`, the check you
asked for on the screen-reading poker project; and a correction to the speed
benchmark so it builds its table with the same forced bets the real table uses
(pull request #23, merged 17 September 2026).

**Waiting on your classmate, then on you.** D1, Rohit's practice arena, is
his move first; the call is still yours once his branch is clean. Issue #4
lists twenty-four required changes: the first seventeen are on the code and
the rules, the other seven are result files and merge mechanics. None of them
has come back yet.

## 1. In plain words: what the bot will be, and how we will know

**What it will be.** A program that sits in one seat at a hold'em table of two
to nine people and, every time it is its turn, works out what to do *right
then*, for that hand only. It thinks at the table rather than memorising a book
of answers before sitting down. The thinking is this: imagine the rest of the
hand thousands of times over — deal out the cards nobody has seen, have
everybody play on, see who ends up with the money — and take the move that came
out best on average. In ten seconds it can imagine over a hundred thousand
finishes. That is the whole bot.

**Where the winning comes from.** Imagining the rest of the hand needs a guess
about how the *other people* will play it. Guess that everyone plays like a
sensible stranger and you get a solid, dull bot. Guess using what each person at
that table has actually been doing — this one pays to see almost every flop,
that one folds the moment anyone bets at him — and the same machinery starts
taking money off those specific people, because it is now imagining the hand the
way they will really play it. That is what "exploitative" means, and it is the
part that answers your bar. The bot's notebook on each player records only *what
they did* — how often they put money in, raised, folded to a bet — never a hunch
and never their cards.

**What it will not be.** No program that writes text by predicting the next
word — a *language model* — is anywhere near the bot when it acts: plain
arithmetic runs, the same table and the same dice give the same answer every
time, and a reviewer can read the code line by line. An assistant writes that
code; no assistant *is* the decision. Nor does the bot judge poker hands for
itself: who won, what beats what and what is legal all come from a real tested
engine we call. Both are `CLAUDE.md`'s forefront rule.

**How we will know it beats real players.** Three things, in order, none of them
an opinion formed while watching it play.

1. **The table is honest before any score is believed.** Chips conserved, when
   two people run out of chips for different amounts, each is paid only out of
   the money actually matched against them — the *side pot* — and replaying a
   session from the same starting number for the shuffle, its *seed*, deals the
   identical hands. A strength number off a table that mis-pays a pot is a
   fiction: `EVALUATION_STRATEGY.md` §4.5's seven invariants.
2. **It beats a league of bad players, with an error bar.** Opponents that each
   embody one real human mistake — calls everything, only bets real hands,
   tilts after a big loss — over hundreds of thousands of hands at six seats,
   at eight and nine, and heads-up. The score is how much it wins per hundred
   hands, counted in the forced bet one player must post before any cards come
   out — the *big blind* — and always printed with a range around it, because
   poker is noisy enough that a bare number means nothing, and half the
   opponents are held back from tuning so we cannot fool ourselves (§3.2,
   §3.5).
3. **It beats an outside bot we did not write.** Slumbot is free, live and
   answers over the internet today. Two-handed only, so it checks one seat count
   and no more — but nobody here can rig it (`RESOURCES_BOTS.md` §5).

## 2. The stages, in order

Sizes are hours of agent work, not calendar days.

### Stage 1 — A table we trust, and a bot that plays complete hands on it

**What it is.** OpenSpiel `universal_poker` wired for two to nine seats with the
bet menu `{fold, call, half pot, pot, all-in}`, the seven invariants running as
tests, and on top of it the first real bot: depth-limited search — look ahead to
the end of the betting round, then finish the hand thousands of times using four
fixed ways of playing on — with the equity-versus-pot-odds rule beside it as a
cheap check. Its opponents this week are the arena's simple players (D1).
**What settles it.** Engine: `ENGINE_ALTERNATIVES.md` :121, OpenSpiel
unconditionally, five and a half times faster than the next working engine. Bet
menu: `ACTION_TRANSLATION.md` §7 — `fchpa` as shipped, randomized
pseudo-harmonic translation, `A = 0` below the smallest bet. Decision layer:
`DECISION_LAYER_SEARCH.md` :637 — option 3's search first, equity rule as a
floor, and **not** IS-MCTS, which crashes the process at three or more players
(:322). Invariants and order: `EVALUATION_STRATEGY.md` §4.5, §3.7 Tier 0. Your
words on that decision-layer choice, 17 September 2026, after the case for
thinking at the table was set out against both a memorised book of answers and
the engine's own tree search: *"okay if you think that is best then that is what
we will go with."* And, the same day, on what order the work comes in: *"we
just keep building the thinking process first and then we will get to the
actual interfacing later."* That is why sitting at a real table is Stage 7 and
not sooner.
**Done when, and how big.** I1–I7 pass at every seat count 2 to 9, and any count
that will not deal is recorded NOT RUN, never passed; the bot plays 1,000
complete hands at six seats against those simple players with zero invariant
failures, inside 250 ms a decision, beating a random-playing baseline with a 95%
interval that excludes zero. 14–20 hours, buildable this week.

### Stage 2 — The scoreboard: the persona league and the decision rule

**What it is.** Four calibration agents with known right answers, nine
behavioural personas each built around one human mistake, paired deals so two
versions meet the same cards, bootstrap confidence intervals, and a rule fixed
in advance for what counts as an improvement. Half the personas are held back
for accept/reject only; Slumbot is called from here.
**What settles it.** `EVALUATION_STRATEGY.md` §3.2 (the persona set; randomise
parameters per session, hold half back), §3.5 (the decision rule, and the
table-size weights 0.50 / 0.30 / 0.20 that implement your ordering — mostly
six-handed, then eight and nine as one band; the ordering is yours, the three
numbers are that document's design choice and stay revisable), §3.7 Tiers 1 and
2 with "stop at Tier 2 if time runs out". `RESOURCES_BOTS.md` §5 for Slumbot.
**Done when, and how big.** one command prints big blinds per hundred hands with
an interval for every persona at seats 2, 6, 8 and 9; `always_fold`'s result
matches the closed-form blinds figure, which proves the accounting; and the rule
rejects a deliberately-worse bot. 12–18 hours.

### Stage 3 — The notebook: watching and counting

**What it is.** The opponent model with no strategy change at all: record every
action of every named player, count the opportunities, shrink each rate towards
the population average so nine hands do not look like a read, and print a profile
with a confidence beside each number and a bucket label.
**What settles it.** `OPPONENT_MODEL_DESIGN.md` §4.2 (the stat table), §4.3
(the update `rate = (BASELINE·s + k)/(s + n)`), §4.4 (buckets and exploit
flags), §4.5 Tier 0 with its worked report, and §7 Q2 — the identifier is the
player's name and the per-table fallback is dropped. Where `BASELINE` comes
from is settled by `OPPONENT_BASELINE.md` §5: observe first, seed from no
archive, and leave §4.3 and `s = 50` exactly as they are — the best prior
either archive offers is worth fewer than about thirty observed hands of an
opponent, which Tier 0 collects in minutes; use the IRC corpus only as a test
fixture for the counter, and replace the design's invented opportunity rates
with §2's measured ones, which fixes a five-fold error in Table C's
fold-to-continuation-bet row. Seat count enters as a context value, not a new
table, and both split thresholds are per band: `TABLE_SIZE_AND_SIZING_NOTES.md`
R1–R4, R8. Counting logic is ported, never imported:
`RESOURCES_EXPLOITATION.md` Recommendation item 2.
**Done when, and how big.** `pokerbot profile <name>` reproduces §4.5's worked
example number for number from its counts, fixtures cover §4.7's edge cases, and
a test asserts no stat reads a hole card or a board card. 12–18 hours.

### Stage 4 — The baseline: sound play before play that hunts

**What it is.** A way of playing that assumes nothing whatever about the people
in the other seats. It is what the bot falls back on against strangers, and it
is also the way it assumes a stranger will play the rest of a hand out when it
imagines that hand finishing. What it aims at is play that nobody can take money
off in the long run, however they adjust to it; poker calls that *game theory
optimal* play, or *equilibrium* play. Your words for why the bot should have it
at all, 17 September 2026: *"can we give the bot a foundation of game theory
optimal play? they should be exploiting for sure and that should be the
priority, but game theory optimal play should be the baseline."*

**Before the flop first, and the honest limit.** Play that truly cannot be
beaten by anybody, at a table of six to nine people playing no-limit hold'em,
cannot be worked out on this laptop, and not on any machine we could rent
either: nobody has computed one and it is not close. Saying otherwise would be the one kind of
lie this plan cannot afford. What *is* reachable is a rough, sampled
approximation. The program plays itself millions of times and, at every point,
keeps a running tally of how much better off it would have been had it made each
move it did not make, then drifts towards the moves it most regrets passing up.
That method is called regret minimisation — in full, *counterfactual regret
minimisation* — and the cheap sampled form of it we would use is *external
sampling*. Run over the first round of betting only, on the five-move menu the
table already offers (fold, call, half the pot, the pot, all of the chips, which
the code calls `fchpa`), it does give a defensible answer for every seat count
from two to nine, because that first round is small enough to reach. That
first-round answer is what this stage builds, for all eight seat counts.

The rounds after the flop get a coarser answer: strategies solved offline, one
per kind of opponent, against a full table. That is the baseline's second half,
and it is sized once the first-round half is on disk. You have already agreed to
that shape and to what it costs: *"that actually sounds pretty good if you can
do those 3 steps well enough. i agree that we cant have perfection postflop, but
as long as it is somewhat similar to theory and that is the goal, then that is
all i can ask for."* The three steps are these: the before-the-flop ranges for
two to nine seats from our own solver; the coarse after-the-flop solves; and
departing from both when the notebook is confident enough about a particular
person to justify it, which is Stage 5.

**Checking the answer against a paid solver.** A handful of commercial websites
have already solved a great many poker spots and will show you the answer to one
if you type the spot in. You hold the top plan on one of them, GTO Wizard's NLH
Cash Ultra, monthly; it is the top tier, the one that carries nine-player solving before
the flop and three-player solving after it, and nine-player solving exists
before the flop only (`RESOURCES_SOLVERS.md` entry 17). There is no published way
for a program to ask that site for a strategy: its one published interface,
what a programmer calls an *API*, only lets a program play hands against the
site's own AI, never read a strategy back. So a check is always a person typing
a spot into a browser and reading the answer back. Your words, giving standing permission for that:
*"take control of my computer, go into my browser and do so, you have free
reign."* It stays a reference and never becomes a part of the bot: nothing is
copied out of it into the bot's own tables, which `CLAUDE.md`'s forefront rule
would forbid in any case. On how much to check, your standing instruction:
*"if there is ever any spot that you are unsure about, i would really like you
to go into my browser and manually check the spot. this should help you in your
task to build a baseline, and even just checking a small number of hands (could
be anything from 10 to 1000) will really help you get a feel for that baseline
so please go into my gto frequently to check hands that the bot is playing and
keep training it."* And, on whether those figures were a ceiling: *"10 to 1000
isnt a restriction of any kind, feel free to use it as much as you want. i want
our solver to be as good as we can."* So there is no cap on how many spots are
checked.

**The measurement that turns "somewhat similar to theory" into a number.** One
command samples decisions the bot actually faced in a scoreboard or arena run —
the seat count, who sat where, the stacks, the action so far, the board, its own
two cards, the move it chose, and how often its search wanted each move on the
menu — and prints each one in a form that can be typed straight into the
reference site. The reference's own action and frequencies for that spot are
written down, one file per batch, under `research/results/theory_agreement/`.
A summary then reports how often the two agree, with a range around that figure
because a handful of spots proves nothing, kept separate for before and after
the flop. Where they disagree is what this stage tunes against. Nothing travels
the other way.

**What settles it.** `DECISION_LAYER_BLUEPRINT.md` recommends external-sampling
regret minimisation as the solving method, and is equally clear about what is
missing — "the method is the easy part": the scheme for grouping similar hands
together, without which no solve of this size finishes, is not built yet.
`RESOURCES_SOLVERS.md` entry 17 is what rules the paid site out as the baseline
itself and in as a reference. The bet menu is `ACTION_TRANSLATION.md` §7, the
same menu the table already deals on. `OPPONENT_MODEL_DESIGN.md` §4.5 Tier 1
requires any per-bucket solve to face the seat count the bot will actually play,
which is why the second half is not one solve but several.

**Done when, and how big.** A solved before-the-flop strategy for every seat
count 2 to 9 sits on disk with a written record of exactly what produced it; the
search uses it as its own play in that round and as the default way a stranger
plays on; the scoreboard is re-run and its result set beside the Stage 2 run
under Stage 2's rule; and a first batch of reference checks is recorded with an
agreement rate and a range. Not sized here: the sizing waits on the
hand-grouping scheme being scoped, and whatever it turns out to be, the solve
has to finish in hours on one laptop, which is `CLAUDE.md`'s compute budget and
not negotiable.

### Stage 5 — The bot that plays the person

**What it is.** The notebook wired into the search: inside every imagined finish
of the hand, each seat plays the way *that seat* has been measured to play
rather than the way a generic stranger would. The stranger it departs from is
now Stage 4's baseline rather than a hand-set style, so this stage measures one
thing only: what knowing the person is worth on top of sound play. This is the
stage meant to produce the "by a lot".
**What settles it.** `ENGINE_ALTERNATIVES.md` "Hook A — the rollout policy, per
seat" (:969 onward): the cheaper, better-specified hook, one weighted draw per
node, the one to build first. `DECISION_LAYER_SEARCH.md` option 4 — it costs
nothing measurable at the table (3,651 play-outs against 4,404 at three
players). Policy inputs are `OPPONENT_MODEL_DESIGN.md` §4.2's measured action
frequencies alone — never a hand-written archetype, never hand strength
(`CLAUDE.md`). How far a read may move play: §5.2's deviation cap, made a
function of seat count by `TABLE_SIZE_AND_SIZING_NOTES.md` R13. Why bluffing
more is the wrong exploit multiway: `OPPONENT_MODEL_DESIGN.md` §2.4.
**Done when, and how big.** against the held-back half of the league, model-on
beats model-off at six seats by an interval excluding zero under Stage 2's rule,
and model-on loses to no persona that model-off beat. 16–22 hours.

### Stage 6 — Refinements, each kept only if it measures better

**What it is.** Candidates run one at a time through Stage 2's rule and dropped
if they do not pay: a third bet size near 0.75 pot on the flop; hole-card
resampling, which `ENGINE_ALTERNATIVES.md` Hook B says has no range machinery
yet. The per-bucket strategies solved offline against a full table, which used
to be listed here, are no longer a candidate: they are the second half of Stage
4's baseline and are built there.
**What settles it.** `ACTION_TRANSLATION.md` §7 names the 0.75-pot rung first
and prices its absence at 1,465 mbb/hand.
**Done when, and how big.** each candidate is merged with its measured gain
recorded, or rejected with its measured non-gain recorded — nothing kept on
plausibility. 8–14 hours per candidate.

### Stage 7 — Sitting at a real table

**What it is.** Getting a real table's state into the bot and its action back
out, then the first live sessions at small stakes with the notebook filling up.
D2 below is now answered, so this has a shape: you play on an app on your phone,
the phone's picture is mirrored onto this Mac in a tall phone-shaped column down
the right-hand side of the screen, and the bot reads that column. So what gets
built is a program that looks at a fixed rectangle of the Mac's own display and
works out from the picture what the table is doing — a *screen reader*. Not the
site's network traffic, not a plug-in inside the app: the picture on the glass.
**What settles it.** D2, answered by you on 17 September 2026 and recorded in
section 3 below. `CLAUDE.md` names `dickreuter/Poker` as the reference for
reading a table off a screen, and `RESOURCES_DICKREUTER.md` is the check of what
that project actually gives us. Two things are still yours to name before this
can be built: which app you play on, and how the phone's picture gets onto the
Mac. Until the reader can read that exact layout, typing the hand in by hand
stays the bridge, which is the console described under D2 — slow, unusable at
speed, and it works on any app there has ever been.
**Done when, and how big.** a hundred real hands are captured off that column,
replayed through the engine, and the replay agrees with what actually happened.
25–40 hours for the reader, on the old estimate for screen capture, plus
whatever the app's particular layout costs; about 10 hours for the typed-in
bridge, which can be built at any time and does not wait on the app's name.

### Stage 8 — One thing you can install and double-click

**What it is.** The end of the road, in your words on 17 September 2026:
*"at the end of all this i would like the project to be a downloadable software.
i am a human and not a computer so i would like there to be a physical like bot
folder ... i want this to be a downloadable software that i can install on my
computer and then it will play for me basically."* Concretely: one Mac
application — an icon you double-click, not a command you type — that carries
everything inside it, so that installing it installs the lot. Inside are the
`pokerbot` package, the poker engine it deals on, the solved baseline from Stage
4, the notebook and its stored counts, and Stage 7's screen reader. It opens a
small window that shows what it is seeing on that mirrored column and what it
just did, so you can watch it work and stop it.
**What settles it.** Nothing yet; this is a build, not a decision, and the
decisions it depends on are Stage 7's. `CLAUDE.md`'s licence section governs
what may be shipped inside it: the vendored engine is under the GNU General
Public License version 3, and anything built on or combined with it carries the
same terms with its source published.
**Done when, and how big.** you double-click it on your own Mac, with nothing
else installed first, and it plays a hand. Sized after Stage 7, and not started
before the reader exists — an application wrapped around a bot that cannot see
the table has nothing to wrap.

## 3. Decisions still yours

One still open and one now answered; everything else above is settled by a
cited document.

### D1 — Do we take your classmate's practice arena and his betting-rules fix?

**Recommendation: take the arena as the practice ground, take the rules fix, but
do not let his engine become the referee without changing the rule first.** He
has built a runner that plays whole hands at six to nine seats with simple
opponents already in it, and a genuine fix to a betting rule both engines got
wrong; Stage 1 is a week faster with it. The catch is one line: his fix makes
PokerKit the referee for rules and payouts, and `CLAUDE.md` says rules and hand
evaluation come from OpenSpiel. `ENGINE_ALTERNATIVES.md` §"What to do with
PokerKit" proposes PokerKit for *checking our work, not playing*, and routes the
call here, to you. So: take the code, keep OpenSpiel refereeing, and use PokerKit
the way `treys` is used — a checker that never touches a live decision.

**The alternatives.** Take it whole, PokerKit refereeing and all — faster still,
but you would be amending the one rule everything else answers to. Or build our
own runner from scratch — no rule question, about a day, and it throws away a
working fix to a rule bug we would otherwise have to find ourselves. Either way
a reviewer wants seventeen other changes on his branch first, none about the
arena itself; a merge chore, not a decision.

### D2 — How does the bot see a real table? — **ANSWERED, 17 September 2026**

**Your answer, in your words:** *"i plan to play on an app on my phone which
will be screen mirrored to this computer. so you will capture my computer
screen. the screen mirror will be on the right side of my screen in a phone
shaped column. you will be playing from there."*

**What that settles.** The bot reads a picture, not a network. It watches one
fixed rectangle of this Mac's own display — the tall, phone-shaped column down
the right-hand side where your phone's screen is being mirrored — and works out
from what is drawn there whose turn it is, what the cards are, what the stacks
are and what everybody has done. Reading the app's own network traffic, which
was the other live option and is far more reliable where it works, is off the
table: the traffic is the phone's, not this computer's, and what arrives here is
only a picture of it. `CLAUDE.md` names `dickreuter/Poker` as the reference for
that kind of reading and `RESOURCES_DICKREUTER.md` is the check of it. This is
Stage 7, and it is sized there.

**Still to come from you, and it does not block anything before Stage 7.** Which
app you play on, and how the picture gets from the phone to the Mac. A reader is
written against one exact layout; it cannot be written against an unnamed one.

**The bridge in the meantime stays what it always was.** A small console where
you type in the seats, the stacks, the cards and each action, about ten hours of
work, usable on any app that has ever existed and far too slow to keep up at a
real table. It exists to get real hands and a real notebook while the reader is
built, and it is thrown away when the reader works.

## 4. The first three tasks, as they were dispatched

These three built Stages 1, 2 and 3, and all three have landed; the section is
kept as the record of what was asked for and what "done" was agreed to mean
before the work started, which is the only way a later claim of success can be
checked. The next task to dispatch is not here: it is Stage 4, the baseline.

**T1 — The table we trust.** Build the OpenSpiel `universal_poker` adapter for
two to nine seats with the `{fold, call, half pot, pot, all-in}` menu as
`ENGINE_ALTERNATIVES.md` :121 and `ACTION_TRANSLATION.md` §7 settle them, and
write invariants I1–I7 from `EVALUATION_STRATEGY.md` §4.5 as tests that abort a
run rather than report a failure, including the side-pot test that builds an
unequal all-in and checks who is paid what. *Done when:* the suite is green,
every seat count 2 to 9 either passes every invariant or is recorded NOT RUN
with a reason, and the same seed plus the same commit replays byte-identical
hand records.

**T2 — The first bot.** Build the depth-limited search of
`DECISION_LAYER_SEARCH.md` :637 — search to the end of the current betting round
over the engine's own tree, finish the hand at the depth limit with four
hand-set continuation strategies, return the best action inside 250 ms — and
beside it the equity-versus-pot-odds rule on the engine's own Monte Carlo equity
calculator, as a logged check rather than as the decision. Not IS-MCTS: it
crashes the process above two players (same file, :322). *Done
when:* the bot plays 1,000 complete hands at six seats against the arena's
existing simple players with zero invariant failures, no decision over 250 ms,
and a win rate against a random-playing baseline whose 95% confidence interval
excludes zero. If D1 is unanswered when T2 starts, stand up three trivial
opponents — always-fold, always-call, uniform-random — and run the same
measurement against those instead; the arena only saves the day it would take
to write them.

*Settled while building it.* The search stops after a fixed number of finished
hands per candidate move rather than when the clock runs out, so the same seed
always gives the same move: a search that ran to the clock would do more work
on a quiet laptop than on a busy one and could answer differently for the same
hand, which no result could be reproduced from. The 250 ms budget stays as the
ceiling this task requires and is never reached — over the recorded thousand
hands a decision took 34 ms at the median and 82 ms at its slowest, and no
search was ended by the clock (`pokerbot/search.py`:59).

**T3 — The scoreboard.** Build `EVALUATION_STRATEGY.md` §3.7 Tiers 1 and 2: the
four calibration agents, the nine behavioural personas of §3.2 with parameters
drawn per session and the set split into a development half and a held-back
evaluation half, paired deals, bootstrap confidence intervals, and §3.5's
decision rule with the table-size weights that implement your ordering (6 at
0.50, 8 and 9 together at 0.30, the rest at 0.20) fixed in the config and
reprinted. *Done when:* one command produces a report giving big blinds per
hundred hands with an interval for every persona at seats 2, 6, 8 and 9;
`always_fold`'s measured result matches the closed-form blinds figure; and the
rule correctly rejects a bot deliberately made worse.
