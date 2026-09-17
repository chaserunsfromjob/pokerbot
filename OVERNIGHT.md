# Overnight instructions, 2026-09-17

Also posted as GitHub issue #13:
https://github.com/chaserunsfromjob/pokerbot/issues/13

For the assistant working on `codex/tonight` in
`github.com/chaserunsfromjob/pokerbot`, and for Rohit reading this in the
morning. Follow it literally and in order. Two jobs tonight, then stop.

## 1. Tonight's two jobs, in order

### JOB 1 — make `codex/tonight` mergeable

The full list of what must change is GitHub issue #4 (`gh issue view 4`). It has
24 numbered items. Work them top to bottom. When item 24 is done, JOB 1 is done.

1. Read the issue: `git fetch origin` then `gh issue view 4`.
2. Items 1-8 (group A): make the operator's rule text win. Revert `CLAUDE.md`,
   `AGENTS.md` and `research/LEGACY_GUIDANCE.md` changes as those items say —
   `CLAUDE.md` goes back to the version on `main`, including its closing line,
   its "Compute budget" section, its "GitHub" section and its "Licence"
   section. Delete `research/LEGACY_GUIDANCE.md`. Move your own working
   arrangement into `AGENTS.md` and point `AGENTS.md` at `CLAUDE.md`.
3. Item 6: in `tools/check_design_numbers.py:286` restore
   `FOREFRONT_SOURCE = "CLAUDE.md"`. On `main` it is `"CLAUDE.md"`; on your
   branch it is `"research/LEGACY_GUIDANCE.md"`, which makes the check pass
   while checking nothing (item 21).
4. Items 9-13 (group B): the short-all-in reopening fix. For item 9, run the
   test suite once and use that one number in both
   `research/REOPENING_REPAIR.md` and `research/PROGRESS.md`, with the exact
   command quoted beside it. Today those files disagree: 192 against 177.
5. Items 14-17 (group C): change only what those four items name. Items 15, 16
   and 17 are the hand-picked constants — `pokerbot/responses.py:21-22`,
   `pokerbot/card_controls.py:21-25`, and the duplicated constants in
   `pokerbot/responses.py:17-19`. Do not otherwise rewrite `policies.py`,
   `ranges.py`, `responses.py`, `river_search.py` or `turn_search.py`.
6. Items 18-19 (group D): keep only the seven small summary files under
   `research/results/` that the prose actually quotes; delete the per-trial
   dumps; record the command and the seed beside every number the prose quotes.
7. Items 20-23 (group E): resolve the merge into `main` by hand. Do not let
   `tools/check_design_numbers.py` or `OPPONENT_MODEL_DESIGN.md` auto-merge.
8. Item 24: open the pull request. In the pull request body, list all 24 item
   numbers and mark each one done or not done, with one line of why for each
   not done.
9. Push. JOB 1 ends here. Do not start JOB 2 before this push succeeds.

### JOB 2 — build task T3, the scoreboard (only after JOB 1 is pushed)

T3 is described in `BUILD_PLAN.md` §4, under the heading "T3 — The
scoreboard". T1 is already being built by someone else on pull request #11,
and T2 waits on T1, so T3 is the one free task. Build it on your arena (`pokerbot/runner.py`),
on a **separate branch** with its own **draft pull request**.

Build `EVALUATION_STRATEGY.md` §3.7 Tiers 1 and 2:

1. The four calibration agents of §3.2 group A: `always_fold`, `always_call`,
   `always_raise`, `call_raise_50_50`.
2. The nine behavioural personas of §3.2 group B: `calling_station`, `nit`,
   `maniac`, `never_bluffs`, `fit_or_fold`, `tag`, `lag`, `tilter`,
   `sizing_tell`. Draw each persona's parameters from a distribution at the
   start of each session, not from one fixed point, and log the drawn values.
3. Split the personas into a development half and a held-back evaluation half;
   the held-back half is used for accept or reject only, never for tuning.
4. Paired deals, bootstrap confidence intervals, and §3.5's decision rule with
   the table-size weights (6 at 0.50; 8 and 9 together at 0.30; everything else
   0.20 split equally) written into the config and reprinted in the report.

Done when, copied from `BUILD_PLAN.md` §4 T3: *one command produces a report
giving big blinds per hundred hands with an interval for every persona at seats
2, 6, 8 and 9; `always_fold`'s measured result matches the closed-form blinds
figure; and the rule correctly rejects a bot deliberately made worse.*

## 2. What not to do tonight

- Do not edit `CLAUDE.md` or `AGENTS.md`, beyond the reverts named in items 1-4.
- Do not change the referee engine, and do not change the rule that says game
  rules and hand evaluation come from OpenSpiel `universal_poker`; if you think
  it is wrong, write the argument in the pull request body and leave the rule.
- Do not write new strategies and do not tune constants by hand; `CLAUDE.md`
  requires every opponent archetype to come from measured action frequencies.
- Do not call a language model from bot code: no model call, no network call to
  a model, no prompt anywhere in the decision path.
- Do not commit a generated result file longer than 200 lines.
- Do not do research or write a survey; research is closed and `BUILD_PLAN.md`
  is the plan.
- Do not merge anything into `main`.
- Do not delete any branch.
- When both jobs are done, stop. Do not pick a third job.

## 3. How to work so we can see you

1. Run `git fetch origin` before anything else, and `gh pr list` to see what
   others are working on.
2. JOB 1 continues on the existing `codex/tonight`. For JOB 2, cut the new
   branch from `main`, never from `codex/tonight` or any other open branch.
3. Within the first hour, push the branch (`git push -u origin <branch>`) and
   open a draft pull request (`gh pr create --draft`) titled with the job.
4. Push at least once an hour after that, not once at the end.
5. One pull request per job: one for JOB 1, a separate one for JOB 2.
6. In each pull request body, write what is done and what is not done.
7. If something blocks you, write the question in the pull request body, then
   move to the next item. Do not stop and wait.

## 4. Morning report

Paste these five lines, filled in, as a comment on each pull request:

```
JOB 1 (issue #4): items done N of 24 — PR <url>
JOB 2 (T3 scoreboard): <not started | in progress | done> — PR <url>
Tests: <exact command> — <passed/failed counts>
Blocked on: <question, or "nothing">
Not done: <items or steps left, or "nothing">
```
