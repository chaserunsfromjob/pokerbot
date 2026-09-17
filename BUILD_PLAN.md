# Build plan: the reconciliation of the surveys

The surveys are done. This file turns them into one ordered build. Where a
question is already answered it cites the file and section that answers it;
where nothing answers it, it is in "Decisions still yours" and waits for you.

The bar it is built to, in your words: *"we dont need perfection here, just
something that we know is beating real players"*, and *"beating real players by
a lot, 2-9 players, exploitative play. i dont care how you do it. just get it
done."*

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

**What it will not be.** No language model is anywhere near the bot when it
acts: plain arithmetic runs, the same table and the same dice give the same
answer every time, and a reviewer can read the code line by line. An assistant
writes that code; no assistant *is* the decision. Nor does the bot judge poker
hands for itself: who won, what beats what and what is legal all come from a
real tested engine we call. Both are `CLAUDE.md`'s forefront rule.

**How we will know it beats real players.** Three things, in order, none of them
an opinion formed while watching it play.

1. **The table is honest before any score is believed.** Chips conserved, side
   pots to the right people, the same seed replaying identically. A strength
   number off a table that mis-pays a pot is a fiction: `EVALUATION_STRATEGY.md`
   §4.5's seven invariants.
2. **It beats a league of bad players, with an error bar.** Opponents that each
   embody one real human mistake — calls everything, only bets real hands, tilts
   after a big loss — over hundreds of thousands of hands at six seats, at eight
   and nine, and heads-up. The score is big blinds per hundred hands *with a
   range around it*, because poker is noisy enough that a bare number means
   nothing, and half the opponents are held back from tuning so we cannot fool
   ourselves (§3.2, §3.5).
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
`DECISION_LAYER_SEARCH.md` :594 — option 3's search first, equity rule as a
floor, and **not** IS-MCTS, which crashes the process at three or more players
(:285). Invariants and order: `EVALUATION_STRATEGY.md` §4.5, §3.7 Tier 0.
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
parameters per session, hold half back), §3.5 (the decision rule and your own
table-size weights — 6 seats 0.50, 8 and 9 together 0.30, the rest 0.20), §3.7
Tiers 1 and 2 with "stop at Tier 2 if time runs out". `RESOURCES_BOTS.md` §5 for
Slumbot.
**Done when, and how big.** one command prints big blinds per hundred hands with
an interval for every persona at seats 2, 6, 8 and 9; `always_fold`'s result
matches the closed-form blinds figure, which proves the accounting; and the rule
rejects a deliberately-worse bot. 12–18 hours.

### Stage 3 — The notebook: watching and counting

**What it is.** The opponent model with no strategy change at all: record every
action of every named player, count the opportunities, shrink each rate towards
the population average so nine hands do not look like a read, and print a profile
with a confidence beside each number and a bucket label.
**What settles it.** `OPPONENT_MODEL_DESIGN.md` §4.2 (the stat table), §4.3 (the
update `rate = (BASELINE·s + k)/(s + n)`), §4.4 (buckets and exploit flags),
§4.5 Tier 0 with its worked report, and §7 Q2 — the identifier is the player's
name and the per-table fallback is dropped. Seat count enters as a context
value, not a new table, and both split thresholds are per band:
`TABLE_SIZE_AND_SIZING_NOTES.md` R1–R4, R8. Counting logic is ported, never
imported: `RESOURCES_EXPLOITATION.md` Recommendation item 2.
**Done when, and how big.** `pokerbot profile <name>` reproduces §4.5's worked
example number for number from its counts, fixtures cover §4.7's edge cases, and
a test asserts no stat reads a hole card or a board card. 12–18 hours.

### Stage 4 — The bot that plays the person

**What it is.** The notebook wired into the search: inside every imagined finish
of the hand, each seat plays the way *that seat* has been measured to play
rather than the way a generic stranger would. This is the stage meant to produce
the "by a lot".
**What settles it.** `ENGINE_ALTERNATIVES.md` "Hook A — the rollout policy, per
seat" (:953 onward): the cheaper, better-specified hook, one weighted draw per
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

### Stage 5 — Refinements, each kept only if it measures better

**What it is.** Candidates run one at a time through Stage 2's rule and dropped
if they do not pay: a third bet size near 0.75 pot on the flop; per-bucket
strategies solved offline against a full table of archetype opponents; hole-card
resampling, which `ENGINE_ALTERNATIVES.md` Hook B says has no range machinery
yet.
**What settles it.** `ACTION_TRANSLATION.md` §7 names the 0.75-pot rung first
and prices its absence at 1,465 mbb/hand; `OPPONENT_MODEL_DESIGN.md` §4.5 Tier 1
requires a per-bucket solve to face the seat count the bot will play.
**Done when, and how big.** each candidate is merged with its measured gain
recorded, or rejected with its measured non-gain recorded — nothing kept on
plausibility. 8–14 hours per candidate.

### Stage 6 — Sitting at a real table

**What it is.** Getting a real table's state into the bot and its action back
out, then the first live sessions at small stakes with the notebook filling up.
**What settles it.** Nothing on `main` — this is D3, and it waits on you naming
where you play; `RESOURCES_EXPLOITATION.md` Recommendation, "What stays open",
says buy nothing until it is answered, and `CLAUDE.md` names `dickreuter/Poker`
as the capture reference if screen capture wins.
**Done when, and how big.** a hundred real hands are captured, replayed through
the engine, and the replay agrees with what happened. Unsizable until D3 is
answered: about 10 hours if hand-entry, 25–40 if screen capture.

## 3. Decisions still yours

Three; everything else above is settled by a cited document.

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

### D2 — Where do the first numbers about how people play come from?

**Recommendation: seed from the public archive of real hands now, and retire it
the moment the bot's own notebook is big enough.** The model must know what an
*ordinary* player's rates look like before it can tell you someone is unusual.
The archive — 21.6 million real-money no-limit hands, players anonymised,
repository MIT-licensed, data reusable with credit — gives those numbers free
this week, the parser is already written (`research/parse_handhq_baseline.py`),
and it replaces guessed split thresholds with measured ones.
`RESOURCES_EXPLOITATION.md` Recommendation item 1 leads with it and says the call
is yours, not the survey's.

**The alternatives.** Watch first: the bot sits at a real table, folds every hand
and records for a few hundred hands before it plays — `OPPONENT_MODEL_DESIGN.md`
§7 Q1's own recommendation, unimpeachable, and it cannot start until D3 is
answered. Or both, which I expect anyway.

### D3 — How does the bot see a real table?

**Recommendation: for the first real sessions, you type the table in, and we
build the reader afterwards.** A small console where you enter seats, stacks,
cards and each action costs about ten hours, works on any site or app, and gets
us real hands and a real notebook while the reader is built. It is slow and
unusable at speed; that is its whole cost.

**The alternatives.** Read the screen with a recogniser, the way
`dickreuter/Poker` does and `CLAUDE.md` names as our reference — the general
answer, the expensive one, and it breaks whenever a site changes layout. Or, if
you play on a phone-style app, read the app's own network traffic the way
`pokerchase-hud` does: far more reliable where it works, and nowhere else. **We
cannot choose until you say where you play**, and no survey answers it.

## 4. The first three tasks to dispatch

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
`DECISION_LAYER_SEARCH.md` :594 — search to the end of the current betting round
over the engine's own tree, finish the hand at the depth limit with four
hand-set continuation strategies, return the best action inside 250 ms — and
beside it the equity-versus-pot-odds rule on the engine's own Monte Carlo equity
calculator, as a logged check rather than as the decision. Not IS-MCTS: it
crashes the process above two players (same file, :285). *Done
when:* the bot plays 1,000 complete hands at six seats against the arena's
existing simple players with zero invariant failures, no decision over 250 ms,
and a win rate against a random-playing baseline whose 95% confidence interval
excludes zero.

**T3 — The scoreboard.** Build `EVALUATION_STRATEGY.md` §3.7 Tiers 1 and 2: the
four calibration agents, the nine behavioural personas of §3.2 with parameters
drawn per session and the set split into a development half and a held-back
evaluation half, paired deals, bootstrap confidence intervals, and §3.5's
decision rule with your table-size weights (6 at 0.50, 8 and 9 together at 0.30,
the rest at 0.20) fixed in the config and reprinted. *Done
when:* one command produces a report giving big blinds per hundred hands with an
interval for every persona at seats 2, 6, 8 and 9; `always_fold`'s measured
result matches the closed-form blinds figure; and the rule correctly rejects a
bot deliberately made worse.
