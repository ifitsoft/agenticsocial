# Phase 9 — The adversarial pass

**Goal:** Every claim that survives pass 1 is attacked by an agent that is trying
to refute it, and the gate becomes two-pass.

**Spec:** §8.3 (pass 2), §8.1 (the record), §8.4 (the gate), §13 (`verify` skill)
**Roadmap:** §5 · **Branch:** `feat/video-phase-09-adversarial`
**Depends on:** 5 — merged.

## The architecture is forced, and that is a good sign

CLAUDE.md: *the CLI contains no LLM calls — `research.py` fetches and formats, it
never summarizes.* Pass 2 is irreducibly a judgement pass.

So the split is the same one the project has used since Phase 1: **the agent
judges, the CLI stores and gates.**

- `skills/verify/SKILL.md` orchestrates one refuter per claim.
- The CLI provides the plumbing: which claims need pass 2, and a gated way to
  record a verdict into `claims.json`.
- **`approve` refuses on `unsupported` and `refuted`** — §8.4 already lists them,
  and `classify()` already fails closed on verdicts it does not know (D-113), so
  today a Phase 9 verdict lands as `open`. **That is the correct starting state**
  and it means the gate is safe before this phase exists.

## What pass 1 structurally cannot catch (§8.3)

Pass 1 compares numbers to bytes. It cannot see:

- right number, **wrong subject** — the 3.7 Pro price attached to 3.7 Flash
- a **stale date** presented as current
- **correlation** in the source stated as **causation** in the beat
- a quote that is **verbatim but torn from a qualifying context**
- an entity that appears in the corpus but **not in this relationship**

**And D-107, which this phase inherits:** a beat that spells its figures in words
(`"ninety-five billion"` against a source saying "nine billion") passes pass 1
with **zero atoms**. §8.2.2 is a rule about digits, end to end. Pass 2 reads
meaning, so this is where it closes — the last route by which a figure reaches
the screen with nothing having checked it.

## The design constraints that make this pass worth anything

Straight from §8.3, and each is load-bearing:

- **Each refuter sees only the claim text and the corpus file.** Never the brief,
  never the draft rationale, never the other claims. **This is the blind-review
  principle the project has now proved twice** (D-111: the second blind runner
  found what the first could not, because it had different context). A refuter
  that can see why the author wrote the beat will find the author's reasoning
  persuasive.
- **It is prompted to refute, not to assess.** Asking "is this supported?"
  produces agreement; asking "show me this is wrong" produces evidence.
- **It defaults to `unsupported` under uncertainty.** Fail closed — the shape
  D-106 and D-113 were both violations of.
- **`residual_risk` is recorded even on `supported`**, and surfaces in review.
  §8.3 says it is often the most useful output of the whole pass, and I believe
  it: "the source does not state an effective date" is exactly what a human
  should see before signing.

## Global constraints

- **No LLM calls in the CLI.** The skill orchestrates; the CLI records.
- **No network in tests.** `conftest` guards sockets *and* the `research` seam
  (D-067 — you cannot guard a boundary you do not own).
- One `classify()` (D-113). Pass 2 verdicts extend it; they do not fork it.
- `claims.json` is written through `workspace.atomic_write`.
- A pass-2 verdict is **bound to the claim it judged** — if the script changes,
  the verdict is as stale as the ledger (D-114's drift logic already exists).

## Tasks

**Task 1 — the record and the gate.** `adversarial` per §8.1
(`verdict`, `attempted_refutation`, `residual_risk`), a gated way to write it,
`classify()` extended, `approve` refusing on `unsupported`/`refuted`, and
`review` surfacing `residual_risk`.

**Task 2 — `skills/verify/SKILL.md`.** One refuter per claim, blind, prompted to
refute, defaulting to `unsupported`. Same house style as `storyboard`.

**Task 3 — the blind acceptance run.** Phase 6's method, which found what
inspection did not: a fresh agent follows the skill on a real episode, and
**every guess it makes is a defect in the skill.** Include at least one beat that
is wrong in a way pass 1 cannot see — a word-spelled figure (D-107), or a real
number attached to the wrong subject. **If pass 2 does not catch a planted error,
the phase has not shipped.**

## Open questions to decide, not default

- **Cost.** One subagent per claim, ~24 claims an episode. Is that acceptable per
  render, and does the skill batch, sample, or run them all? §8.3 says one refuter
  per claim for MVP; say what that costs before defending it.
- **Determinism.** Pass 1 is re-runnable in a year and gives the same answer.
  Pass 2 is not. **Say so plainly in the ledger** — a `checked_at` on a
  non-deterministic verdict means something weaker than on a mechanical one.
- **What invalidates a pass-2 verdict?** A changed script certainly. A changed
  corpus? A better model? There is no honest answer that does not involve an
  expiry, and pretending otherwise is how a stale `supported` gets signed.

## Exit criteria

- [ ] A planted wrong-subject claim is **refuted**, and named.
- [ ] A word-spelled figure that pass 1 misses (D-107) is caught.
- [ ] `approve` refuses on `unsupported` and `refuted`, distinguishably.
- [ ] `residual_risk` surfaces in `review` even for `supported` claims.
- [ ] Refuters are blind: no brief, no rationale, no sibling claims.
- [ ] No LLM call in the CLI; no network in tests.
- [ ] The ledger says plainly that pass 2 is not reproducible.

## Carried

D-056 (`engine/` unpackaged, D-120) still open. `type_family`/`type_scale` reach
no pixel (D-116) → Phase 10.
