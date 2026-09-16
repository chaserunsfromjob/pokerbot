# Ranked experiment backlog

Each entry is a hypothesis, not a promised improvement. Record rejected ideas
as well as successes. Expected benefit and readiness are judgments to revise
from measured evidence. Research is not limited to these candidates.

| Priority | Experiment / hypothesis | Benefit / readiness | Judge it by | Main unresolved risk |
| --- | --- | --- | --- | --- |
| Done | Replace faulty OpenSpiel betting referee with PokerKit | Implemented / 73 root tests pass | Single and cumulative short all-ins, postflop translation, independent side-pot payouts at 2–9 seats | Benchmark uses fractional tied payouts; class-app integer chip rules remain separate |
| 1 | More conservative equity/pot-odds parameters improve the original policy | Screened / 5,400 hands, inconclusive | No tested variant passes the held-out +5 bb/100 gate; call-margin increases looked poor in development | Uniform opponent holdings, high-variance aggression, small sample, no future betting model |
| 2 | Position-aware preflop and preflop-action ranges improve decision quality | Implemented; fresh 28,800-hand factorial screen complete | No cell establishes gain over frozen original; position helps versus equal-sample uniform in selected card-aware cells; range effects inconclusive | Unadjusted comparisons, uncalibrated likelihoods, rare very low effective sample sizes, shared evaluator |
| 3 | Named-player shrinkage improves decisions over the exact same unadapted policy | High / simple fold counters implemented | Off / oracle / learned matched sessions; fresh seeds and learning resets | Current threshold adjustment is a heuristic, not a calibrated response solver |
| 4 | Restricted rollout search improves multiway postflop choices | River prototype implemented; 8,640-hand two-response-model screen inconclusive; 17 focused tests pass | No positive lower strength interval; rare river opportunities limit coverage; next compare calibrated/learned responses and extend to turn | Uniform holdings, wrong response models, fixed hero continuation, sampling noise; 595ms worst observed decision |
| 5 | NoRegrets yields a useful trained/search policy component | High / source candidate, adapter and checkpoint missing | Pin/build, validate native actions, train a small checkpoint, then compare 2–6 players | No distributed pretrained artifacts; 7–9 unsupported; measure memory before large training |
| 6 | Isolated dickreuter components offer a useful equity-threshold baseline | Tie accounting and engine-ranking patches pass 8 fixtures + 400 ranking comparisons; full policy bridge still missing | Local strategy configuration and exact action translation must pass before tournament entry | Original evaluator also misranks quads; GUI/service dependencies and six-player assumptions remain |
| 7 | CFR variants, NFSP or Deep CFR supply a trainable baseline | Existing external-sampling MCCFR validated on Kuhn; other algorithms and NLHE adaptation unimplemented | Three toy training seeds reach exact NashConv below .05; next requires explicit standard-NLHE state/action abstraction and a held-out pool | Toy-game convergence does not establish multiway no-limit strength |
| 8 | Population-based training reduces overfitting to one opponent pool | High / requires trainable base policy | Held-out populations outperform single-pool training at equal measured compute | Cycling, training instability, weak response learners |
| 9 | Restricted/robust opponent responses handle model error better than pure exploitation | High / research | Sparse/wrong/changing-model stress test versus nonadaptive policy | Heads-up results do not transfer automatically to multiplayer |
| 10 | Imitation from suitable public histories supplies a better starting policy | Medium / data suitability unresolved | Split by session/player; valid action labels and information-set inputs | Sparse shown cards, selective showdowns, unknown logging/usage terms |
| 11 | Another Deep CFR implementation supplies reusable training or policy components | Source audited at e754059; not installed; see TRAINED_CANDIDATES_REVIEW.md | Public-observation/action translation, real saved artifact, bounded reproducible training pilot | Six-seat encoder ceiling, no bundled checkpoint, no reported hold'em strength; runtime compatibility untested |
| 12 | AIVAT-style evaluation reduces variance without shifting expected returns | Research only; see RIVER_SEARCH.md | Independent exact small-game zero-mean checks, paired raw/adjusted results, separately frozen future protocol | Current policies expose sampled actions, not exact strategy probabilities; approximate weights can introduce bias |

## Primary starting points

- [OpenSpiel algorithm catalog](https://github.com/google-deepmind/open_spiel/blob/master/docs/algorithms.md): implementations to inspect, not ready-made strong NLHE agents.
- [NFSP](https://arxiv.org/abs/1603.01121): self-play learning in imperfect-information games.
- [Population-based strategy training / PSRO](https://arxiv.org/abs/1711.00832): learning response populations.
- [Deep CFR](https://proceedings.mlr.press/v97/brown19b.html): function approximation for counterfactual regret minimization.
- [Restricted Nash response](https://papers.nips.cc/paper_files/paper/2007/hash/6e7b33fdea3adc80ebd648fffb665bb8-Abstract.html): robust exploitation starting point; reassess multiplayer applicability.
- [NoRegrets source](https://github.com/conorarmstrong/noregrets): 2–6-player Rust implementation; public source excludes trained blueprints. Checkpoints must be trained locally or separately supplied.
- [dickreuter/Poker source](https://github.com/dickreuter/Poker): source assessment pinned to `cae3a108b6cbf22ed8ef90bc0e70f790346289a4`.
- [OpenSpiel universal-poker notes](https://github.com/google-deepmind/open_spiel/blob/master/open_spiel/games/universal_poker/README.md): ACPC integration explicitly warrants independent validation.
- [PokerKit simulation API](https://pokerkit.readthedocs.io/en/stable/simulation.html): independent candidate referee for checking the OpenSpiel short-all-in defect.

## Candidate adapter contract

`ProcessPolicy` invokes a trusted local argv without a shell, sends a sanitized
JSON observation plus separate profiles and an RNG seed, and accepts an action
and diagnostics. Amounts are cumulative whole-hand raise-to targets. Timeout,
malformed JSON and illegal actions fail the experiment rather than falling back
silently. This generic boundary is tested; native NoRegrets and dickreuter
bridges are **not implemented** and must not be represented as integrated bots.
Use OS isolation for untrusted programs: the interface alone is not a sandbox.
