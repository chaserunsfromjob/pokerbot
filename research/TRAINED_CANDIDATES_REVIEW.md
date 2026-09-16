# Additional trainable candidates — September 16, 2026

This is a source compatibility review, not a replication of external results.
No dependencies were installed, no external model executed, and no paid compute
used. Existing local tournament code remained frozen during the review.

## A newer Deep CFR hold'em implementation

[dberweger2017/deepcfr-texas-no-limit-holdem-6-players](https://github.com/dberweger2017/deepcfr-texas-no-limit-holdem-6-players)
was inspected at commit `e75405928bdcf8f80dc35b463f706b8ef45d1b3b`.
The pinned checkout is newer than the cached browser README; use pinned files
for these findings. The repository license is MIT; no code is copied here.

- Its [current-policy interface](https://github.com/dberweger2017/deepcfr-texas-no-limit-holdem-6-players/blob/e75405928bdcf8f80dc35b463f706b8ef45d1b3b/src/holdem/policy.py)
  accepts public bet candidates and maintains one model per physical seat.
  Profiles accept two to six slots. The
  [decision encoder](https://github.com/dberweger2017/deepcfr-texas-no-limit-holdem-6-players/blob/e75405928bdcf8f80dc35b463f706b8ef45d1b3b/src/holdem/encoding.py)
  fixes `SEATS = 6`; seven-to-nine-seat use would require code, shape, training
  and validation changes, not padding an existing checkpoint.
- The [training runner](https://github.com/dberweger2017/deepcfr-texas-no-limit-holdem-6-players/blob/e75405928bdcf8f80dc35b463f706b8ef45d1b3b/src/holdem/experiment.py)
  supports fixed-stack four-to-six-player scenarios, policy export and training
  recovery. These are useful designs to inspect for our eventual trainable path.
- The [historical-model documentation](https://github.com/dberweger2017/deepcfr-texas-no-limit-holdem-6-players/blob/e75405928bdcf8f80dc35b463f706b8ef45d1b3b/docs/benchmarks.md)
  places referenced checkpoints in the owner's local archive with no automatic
  download. No `.pt`, `.pth`, `.pkl` or `.safetensors` file is tracked in this
  checkout. We therefore do not have a ready checkpoint to enter in our arena.
- Its [first hold'em report](https://github.com/dberweger2017/deepcfr-texas-no-limit-holdem-6-players/blob/e75405928bdcf8f80dc35b463f706b8ef45d1b3b/docs/reports/holdem-baseline.md)
  records ten completed jobs out of twelve: one collection-limit failure and
  one unattempted job. Completed policies had negative observed returns against
  its controls; all comparisons with uniform play remained inconclusive. These
  are upstream-reported implementation checks, not evidence of a strong bot.
- [Requirements](https://github.com/dberweger2017/deepcfr-texas-no-limit-holdem-6-players/blob/e75405928bdcf8f80dc35b463f706b8ef45d1b3b/requirements.txt)
  include Torch 2.x and a pinned Rust `pokers` fork. Our Python 3.14 environment
  and PokerKit observation/action conventions need a separate compatibility
  pilot. Do not mutate a running experiment's environment to install these.

**Decision:** retain as a training/component candidate. Before integration,
verify dependencies, reconstruct its public event features from our sanitized
observations, validate exact action amounts and run bounded checkpoint
save/reload tests. Its six-seat representation and missing model remain explicit
limits. Do not spend effort on a seven-to-nine-seat extension before demonstrating
useful six-seat learning or extracting a component that helps our existing engine.

## Other training implementations

[Eric Steinberger's Deep CFR implementation](https://github.com/EricSteinberger/Deep-CFR)
has runnable small-game examples and policy export hooks, but its documented
setup specifies PyTorch 0.4.1, Docker-based logging and Linux-only official
support. It is a reference implementation requiring modernization here.
[PokerRL](https://github.com/EricSteinberger/PokerRL) describes general multiplayer
engine/agent modules while noting that some evaluation components are two-player
only. That does not establish a working nine-player Deep CFR recipe.

[RLCard's no-limit game documentation](https://rlcard.org/rlcard.games.nolimitholdem.html)
lists six abstract actions and configurable player parameters, but explicitly
describes the game version as two-player. Treat multiway support as unverified;
the presence of a player-count argument is insufficient. Its NFSP examples are
algorithm references, not a ready six-to-nine-player policy.

## Next measurable experiment

Compare a small trainable response learner or a pinned native policy component
with the frozen equity baseline through the existing arena. Require legal
observations/actions, real model artifacts, independent training seeds and
fresh evaluation. Prefer a pilot that tests a specific implementation uncertainty;
another toy-game success alone does not advance the hold'em strength milestone.
