# Why language models play poker badly

Research note, September 2026, so the forefront rule in `CLAUDE.md` can point at
named, measured failures rather than a general suspicion. The decision it serves: an
AI assistant may **write** the code that makes poker decisions, but no model may
**make** a live decision. Every source was opened and read; the list of what was
opened, and when, is at the end.

## 1. In plain words

A large language model is a program that has read an enormous amount of writing and,
given some text, predicts what comes next. That is the whole of what it does. Asked
a poker question it produces the words that tend to follow such a question in what
it has read, which is why it sounds like a poker player: it has read poker players.
Sounding like one and playing like one are different jobs. A poker decision is a
number - how often to raise this hand, from this seat, against these opponents - and
the model is not computing that number, it is recalling the shape of an answer. On
PokerBench, an 11,000-spot test built with trained poker players, the best model
chose the right action in about two thirds of spots and the right bet size in about
half.

The mistakes are not noise that more data would average away: they repeat, and an
opponent farms them. The models play one fixed style instead of mixing - a model
that reraises only with aces, kings and ace-king can be folded to for free. They get
arithmetic wrong, give different answers to the same hand written two ways, and
invent cards. They take seconds and real money per decision where a purpose-built
bot takes hundredths of a second and nothing. And in the one published head-to-head
against a game-theory solver, on the smallest poker game anybody studies, the best
language-model agent on record still lost. The model's job here is to write and
check the code around the engine, not to sit in the seat.

## 2. The failure modes

**1. It loses the head-to-head against a solver.** *The mistake:* treating the model
as a substitute for search, which measurement does not support.
*Evidence:* Suspicion-Agent (Guo, Yang, Yoo, Lin, Iwasawa, Matsuo, 2023/COLM 2024,
https://arxiv.org/abs/2309.17277) ran GPT-4 against four bots at Leduc Hold'em, a
6-card toy poker: over 100 games it beat NFSP (+142 chips), DQN (+45) and DMC (+24)
and **lost to CFR+ (-22 chips)**, the only solver in the set. In GTBench (Duan et
al., 2024, https://arxiv.org/abs/2402.12348) every LLM agent facing a Monte Carlo
tree search opponent in the complete, deterministic games scored **-1** normalised
relative advantage - "can barely win even a single match" of 50 - though in the
probabilistic games, poker among them, the gap narrowed to near zero.
*For our code:* never place a model where the engine's search would otherwise run.

**2. Arithmetic breaks exactly where poker needs it.** *The mistake:* pot odds,
equity and stack-to-pot ratios computed in prose come out wrong while still reading
as confident.
*Evidence:* GSM-Symbolic (Mirzadeh, Alizadeh, Shahrokhi, Tuzel, Bengio, Farajtabar,
2024, https://arxiv.org/abs/2410.05229) found every model's accuracy falls when
**only the numbers change** and drops **up to 65%** when one irrelevant clause is
added. Suspicion-Agent reports that on averaging win rates over an opponent's
holdings, "GPT-4 struggles to consistently generate accurate mathematical equations
and results."
*For our code:* take every equity, pot-odds and sizing number from tested engine or
combinatorics code.

**3. It cannot hold a mixed strategy.** *The mistake:* correct poker raises a hand
some fraction of the time; models give one answer and repeat it, which is a pure,
readable strategy.
*Evidence:* Van Koevering and Kleinberg (2024, https://arxiv.org/abs/2406.00092)
found GPT-4 and Llama 3 "exhibit and exacerbate nearly every human bias we test" in
generating random sequences. PokerBench shows it in poker: GPT-4 reraised only with
AA, KK and AKs, "an exploitable leak: if opponents know GPT-4 is never raising with
weak hands, they will easily fold to GPT-4's raise."
*For our code:* draw every frequency from the engine's strategy with a seeded
generator we own; never ask a model to pick "sometimes".

**4. The baseline style is wrong and stays wrong.** *The mistake:* models settle
into a fixed over-tight or over-loose style and do not correct it, even when told to
play optimally.
*Evidence:* Gupta (2023, https://arxiv.org/abs/2308.12466) found ChatGPT plays "like
a nit", engaging only premium hands and folding a majority, while GPT-4 plays "like a
maniac", raising **90% of hands from the Button when asked to be GTO**. PokerBench
saw the same split live: GPT-4 open-raised 15.3% of hands where the fine-tuned model
open-raised 27.3%.
*For our code:* aggression and fold frequencies belong to the loaded engine
strategy, never to a prompt or a model's temperament.

**5. It hallucinates cards and board reads.** *The mistake:* the model states a
card, pot size or hand rank that is not in the game state it was given.
*Evidence:* Suspicion-Agent reports that with simple instructions "LLMs can produce
outputs that are either meaningful and rigorous or less rigorous and even invalid",
needing hand-built templates to suppress it. PokerBench dropped the smaller Llama-2
models entirely: they "are unable to follow poker instructions."
*For our code:* read board texture, hand rank and pot state from the engine,
ground-truthed against `treys` in tests; never parse generated text into state.

**6. Range tracking decays as the hand gets longer.** *The mistake:* the model loses
what happened on earlier streets, which is exactly where an opponent's range was
narrowed.
*Evidence:* Liu, Lin, Hewitt, Paranjape, Bevilacqua, Petroni and Liang (2023,
https://arxiv.org/abs/2307.03172) showed accuracy is highest at a context's start
and end and "significantly degrades" in the middle, even in long-context models.
Suspicion-Agent reports "a rapid decline in the quality of the model's output as the
length of these prompts increases."
*For our code:* ranges are the engine's to assign and carry; never reconstruct one
from a transcript.

**7. No memory of an opponent across hands.** *The mistake:* each call starts blank,
so a model knows a player only by being re-fed the history, which runs into failures
6 and 9.
*Evidence:* Suspicion-Agent's opponent modelling works only by pasting prior
gameplay into the prompt, and the authors fused planning and evaluation into one
call to stay in budget, "which results in a quite long sequence generation, leading
to the performance decline."
*For our code:* opponent history lives in our own database as counts and rates, per
`OPPONENT_MODEL_DESIGN.md`; a prompt is never the store of record.

**8. The same spot gets different answers.** *The mistake:* wording, order and
formatting change the decision while the poker situation is identical.
*Evidence:* Sclar, Choi, Tsvetkov and Suhr (2023, https://arxiv.org/abs/2310.11324)
measured differences of **up to 76 accuracy points** from prompt formatting alone on
Llama-2-13B; Pezeshkpour and Hruschka (2023, https://arxiv.org/abs/2308.11483)
measured **13% to 75%** gaps from reordering options. Gupta found the poker version:
`A4s` versus `4As`, the same hand written the other way round, gave "completely
different decision matrices", folding premium hands like AQs.
*For our code:* decisions take a structured game state, not text; a test must assert
identical states return identical actions.

**9. Seconds and dollars per decision.** *The mistake:* a model in the decision path
is too slow for a live table and too expensive to measure over the sample sizes
poker needs.
*Evidence:* PokerGPT (Huang, Cao, Wen, Zhou, Zhang, 2024,
https://arxiv.org/abs/2401.06781) reports **5.4 seconds** per decision against
AlphaHoldem's **0.017 seconds**, about 300 times slower, rising linearly with player
count. Suspicion-Agent reports "the cost per game reaches nearly one dollar" and
"several minutes to complete a single game of Leduc Hold'em."
*For our code:* the decision path must run tens of thousands of hands offline on
this laptop, which rules out any model call per action, local or networked.

## What stays out of the decision code

- Never call a language model to choose an action; take the action from our own decision code and the engine's solver (CFR+ beat both GPT-4 and GPT-3.5 agents at Leduc Hold'em, the one head-to-head on record).
- Never compute pot odds, equity, or a stack-to-pot ratio in generated prose; take every such number from engine or combinatorics code covered by a test.
- Never ask a model to act "sometimes" or "at random"; draw every mixed-strategy frequency from the engine's strategy using a seeded generator we own.
- Never let a prompt, a persona, or a temperature setting govern aggression or fold frequency; those belong to the loaded engine strategy alone.
- Never parse generated text back into game state; read board texture, hand rank, and pot state from the engine, ground-truthed against `treys` in tests only.
- Never rebuild an opponent's range from a transcript or a conversation; range assignment stays with the engine for the whole hand.
- Never keep opponent history in a prompt; store observed actions and rates in our own database, which is the only store of record.
- Never let wording or field order change a decision; decisions take a structured game state, and a test must assert identical states return identical actions.
- Never put any model call in the per-action path, local or networked: a local 1.3B model took 5.4 s per decision, and the decision path must run tens of thousands of hands offline on one laptop.

## Sources visited

All opened on **2026-09-16** at `arxiv.org/abs/<id>`, plus the full PDF wherever a
number above is quoted from the body: 2501.08328 (PokerBench, Zhuang, Gupta, Yang,
Rahane, Li, Anumanchipalli, 2025), 2309.17277 (Suspicion-Agent, Guo et al., COLM
2024), 2401.06781 (PokerGPT, Huang et al., 2024), 2308.12466 (Gupta, 2023),
2410.05229 (GSM-Symbolic, Mirzadeh et al., 2024), 2402.12348 (GTBench, Duan et al.,
2024), 2310.11324 (Sclar et al., 2023), 2308.11483 (Pezeshkpour and Hruschka, 2023),
2307.03172 (Liu et al., 2023), 2406.00092 (Van Koevering and Kleinberg, 2024).
"Husky Hold'em" returned nothing on arXiv and is not cited, because it could not be
opened.
