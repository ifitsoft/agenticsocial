# Phase 6 — The `storyboard` skill

**Goal:** An agent turns a brief and a corpus into a `script.yaml` that passes
`agsoc video check` **without an override**, and stops at `in_review`.

**Spec:** §13 (skills), §6 (the pipeline), §7 (beat catalogue), §8 (verification)
**Roadmap:** §5 · **Branch:** `feat/video-phase-06-storyboard`
**Depends on:** 2 (ingest), 3 (schema), 5 (verifier) — all merged.

## What makes this phase different, and how it gets tested

**The deliverable is prose.** There is no function to unit-test. A skill that
reads beautifully and produces a failing `script.yaml` is worthless, and a skill
nobody can follow is indistinguishable from one that is wrong.

So the acceptance test is behavioural, and it is the whole phase:

> **A fresh agent, with no context from this project, follows the skill against
> the operator's real brief and produces a `script.yaml` that passes
> `agsoc video check` with zero overrides and zero human repair.**

Two rules make that test honest, both learned the hard way in Phases 4 and 5:

1. **The agent that writes the skill does not run the acceptance test.** An
   author testing their own instructions supplies the missing steps from memory
   without noticing — the same reason blind review found what 21/21 mutation
   coverage could not.
2. **The runner reports what it had to guess.** Every guess is a defect in the
   skill, not in the runner. That list is the phase's real output.

## The insight this phase rests on

Phases 3, 4 and 5 built a system with **specific, discoverable traps** — each one
found by running real content, each one now enforced by a refusal:

| The trap | What it refuses | Where it came from |
|---|---|---|
| A number that rounds for display | `round(value, decimals) != value` | D-083 |
| A count-up that cannot finish in its hold | too-short beat ends on a false figure | D-087 |
| `dumbbell` used where numbers exist | it renders no digits, by design | D-086 |
| `custom` without `attest` | executed content needs a signed sentence | D-088 |
| `shown` outside `<s>`/entities | it was arbitrary JS | D-093, D-094 |
| A figure absent from its `quote` | the whole point of Phase 5 | D-099 |
| An unparseable figure | now checked, no longer exempt | D-106 |
| A row value outside `[0, scale]` | refused, not clipped | Phase 4 |

**An author who does not know these will hit them one at a time, and the
refusals will read as the tool being broken.** The skill's job is to front-load
them so the first draft passes. That is the difference between a gate and an
obstacle course.

## Global constraints

- **The skill never runs `agsoc video approve`, `render`, or `post`.** Work ends
  at `status: in_review`. That rule is in CLAUDE.md and in `fanout`; it is the
  project's spine.
- **Never invent a figure.** If a source publishes direction rather than
  magnitude, `dumbbell` with its required footnote is the honest form (§7.2).
- **Every asserting beat carries `src` and a verbatim `quote`**, and every figure
  the beat displays appears in that quote.
- Match the house style of `skills/fanout/SKILL.md`: frontmatter, **Hard rules**,
  then **Workflow**. Same voice — short, imperative, no hedging.
- **No new Python** unless the acceptance run proves a gap. If it does, that gap
  is a finding worth more than the code.

## Tasks

**Task 1 — write the skill.** `skills/storyboard/SKILL.md`. Brief + corpus +
`series.toml` + `voice.md` → `script.yaml`. Front-load the trap table above as
*positive instructions*, not a list of errors to avoid — "write the figure the
way the source writes it" beats "do not round".

**Task 2 — the blind acceptance run.** A fresh agent, no project context, real
brief, real corpus. It follows the skill and nothing else. Output: a
`script.yaml`, the `check` result, and **a list of everything it had to guess or
look up.**

**Task 3 — close what Task 2 found**, and re-run blind with a *different* fresh
agent. Two clean runs by two agents, or the skill is not done.

## Open questions to decide, not default

- **Coverage.** §13 says the skill must always run `agsoc coverage check`. That
  command does not exist — coverage lives in `engine/coverage.mjs` until Phase
  11. Decide what the skill says today such that it does not need rewriting when
  the command lands.
- **Beat counts.** `series.toml`'s `[structure]` acts are advisory targets
  (§ spec 232), and runtime tolerance is ±8s against a 120s target. An author
  needs a concrete rule of thumb for how many beats and what holds, or every
  first draft lands OUT OF TOLERANCE.
- **What the skill says about `custom`.** It is the one type that executes, and
  D-088's answer is a human sentence. The skill should discourage it, not
  document it as a convenience.

## Exit criteria

- [ ] Two blind runs by two different fresh agents each produce a `script.yaml`
      that passes `agsoc video check`, exit 0, **zero overrides**.
- [ ] Runtime lands inside `target_sec ± tolerance_sec` without hand-tuning.
- [ ] Neither run needed a fact not in the skill, the brief, or the corpus.
- [ ] The skill never suggests `approve`, `render`, or `post`.
- [ ] `agsoc video review` shows every beat cited, with quotes visible.

## Carried, not blocking

D-107 (figures spelled in words are unchecked) is Phase 9. Coverage relocation is
Phase 11. If the acceptance runs surface a Python gap, record it — Phase 7 and 8
are the next places to fix one.
