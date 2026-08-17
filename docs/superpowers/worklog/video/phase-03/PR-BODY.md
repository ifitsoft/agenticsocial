# Phase 3 — Script schema: validate the beats, estimate the runtime

Splits the beat **schema** out of `plan.py`, validates the full spec §7.1
catalogue, and adds `agsoc video review` — the command an operator reads before
approving anything.

**Plan:** `docs/superpowers/plans/2026-08-17-phase-03-script-schema.md`
**Spec:** §6, §7, §11 · **Decisions:** D-068 … D-071

---

## What you can do

```bash
agsoc video review 2026-08-17 --series the-brief
```

```
the-brief/2026-08-17 · draft · 6 beats · pace 1.0

     #  act  type        hold  text                                               src
     0  01   statement    4.0  AI pricing moved in both directions on the same…   [_pasted]
     1  01   statement    4.4  Google launched Gemini 3.7 Flash at roughly half…  [_pasted]
     …

holds 25.8s × pace 1.0 = runtime 25.8s
target 120s ± 8s · OUT OF TOLERANCE (-94.2s)
```

**`review` is a report, not a gate.** It exits **0** even out of tolerance. Spec
§11 puts the gate at `approve` (Phase 7), which will consume the same
`check_runtime` and refuse. A diagnostic command that goes silent when something
is wrong is the D-018 mistake in a new place.

## What's in it

| | |
|---|---|
| `video/script.py` | the beat catalogue, per-type validation, frozen `Script`/`Beat` |
| `video/plan.py` | now a consumer — keeps pace, absolute times, frames, `script_sha256` |
| `video/cli.py` | `agsoc video review` |
| `video/series.py` | `tolerance_sec`, `register`, `name`/`byline` validated |

**Two gates, not one.** A beat type that validates but cannot yet be rendered
says so explicitly — `beat 2 (dumbbell) is a valid beat type but cannot be
rendered yet` — rather than being reported as unknown. Validation and rendering
are different questions and Phase 4 closes the second.

## ⚠️ Spec defect found and corrected

Spec §7.1 gave `jumpChart` the fields `before`/`after`/`scale`/`footnote` — a
single bar. The engine takes `jumpChart(rows, max, d0, parent)` and the episode
that **actually rendered** passes four rows:

```js
jumpChart([['FrontierCode 1.1', 34.4, 43.6, '<s>34.4</s> → 43.6'], …], 70, .5, chart)
```

**The spec's shape could not express the only `jumpChart` that exists.** Found
because the task brief pointed the implementer at the two committed episodes as
*evidence* rather than background. It followed §7.1 as written and flagged the
contradiction instead of quietly inventing a better shape.

The lesson is broader: §7.1 was written from the *design* of the beats, not from
the code that renders them. Every other row is suspect, and D-069 lists the
fields nobody could source from either spec or episode — `quote` is entirely
spec-only, since neither committed episode has one.

## Phase 5 requirements, found by running real material early

A real operator brief was pushed through the pipeline before the verifier exists.
Two defects surfaced that fixtures could never have shown, both now spec
requirements:

**§8.2.1 — comparison folding.** The source used **U+2011 NON-BREAKING HYPHEN**
(`V4‑Pro`); the beat wrote U+002D. Two of six beats were refused for quotes that
were genuinely present, and **NFKC does not fix it** — U+2011 is not a
compatibility variant. Folding applies to the *comparison only*; the corpus keeps
its bytes and `sha256` still covers the originals. It cannot weaken the check:
no digit is ever folded, and `1,400%` / `$9.32` / `9.4 trillion` remain refused
with folding on.

**§8.2.2 — claim numbers vs identifier digits.** `V4-Pro`, `Qwen3.8-Max`,
`GPT-5.6` carry digits that are not claims. The first draft of that rule —
"letters and digits means identifier" — exempted `1M` and `95B`, which would let
a beat claim `95B active` against a source saying `9B`. The unit-suffix strip
exists because the rule was run against real text before any code was written.

## D-063 arrived on schedule

Phase 2 predicted the next bypass would be a *read* of a stale value rather than
a forged write, and named this gate. `check_runtime` reads `series.target_sec`
off an object. Verified at the CLI level: changing `target_sec` in `series.toml`
between two `review` runs changes the verdict.

## Test plan

`uv run pytest` — **828 passed**, offline, no new dependencies.

Verified by hand on a real episode: `review` output readable at six beats,
`script.yaml` byte-identical after review, the duration check follows the file,
and `review` exits 0 out of tolerance.

## Note on review

**No whole-branch adversarial review ran on this phase** — merging at the
author's direction. Each task carried its own mutation testing (Task 0: 14/14,
Task 1: 26/26), and every finding above came from those. Phase 1's gate found an
approval-gate bypass and Phase 2's found the verifier trusting its own manifest,
so this is a real trade rather than a formality.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
