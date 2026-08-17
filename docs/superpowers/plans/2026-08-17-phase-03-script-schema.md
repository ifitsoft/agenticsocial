# Phase 3 — Script schema: validate the beats, estimate the runtime

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** A `script.yaml` the storyboard skill can be held to — every beat type validated, every duration accounted for, and `agsoc video review` showing an operator what they are about to approve.

**Spec:** §7 (beat schema and catalogue), §6 (`target_sec`/`tolerance_sec`), §11
**Roadmap:** `docs/superpowers/plans/2026-08-16-video-mvp-roadmap.md` §5
**Branch:** `feat/video-phase-03-script-schema`

## What already exists, and what this phase changes

Phase 1.5 built `plan.py`, which parses the beats document, validates **one** beat
type, resolves timing and emits `plan.json`. That was correct for a vertical
slice and is the wrong shape to grow into.

Phase 3 splits it:

- **`script.py`** owns the *schema* — what a beat is, per type, and whether a
  given `script.yaml` conforms. It knows nothing about frames, formats or JSON.
- **`plan.py`** keeps the *resolution* — pace, absolute times, frame numbers,
  design tokens, the Node handoff. It consumes a validated script.

The split matters because Phase 5 verifies **claims**, and a claim is anchored to
a beat's `src` and `quote`. The verifier needs to walk beats as data without
caring how they will be rendered.

## Scope of the beat catalogue

Spec §7.1 lists ten types. **This phase validates all of them; Phase 4 renders
them.** That is a deliberate split and it has a real risk: defining a schema for
a consumer that does not exist is how speculative design gets locked in.

Two things keep it honest:

1. Every type's fields come from **spec §7.1 and the two committed episodes**
   (`engine/content/2026-08-12.js`, `2026-08-14.js`), which are real scripts that
   really rendered. A field no committed episode uses and the spec does not name
   does not go in.
2. `plan.py`'s `SUPPORTED_BEATS` stays the gate on what can actually be
   *rendered*. Validation accepting `dumbbell` while rendering refuses it is the
   correct state until Phase 4 — and the error must say so plainly, not "unknown
   beat type".

## Global Constraints

- Python ≥3.11. **No new dependencies.**
- **No network in any test** — `tests/conftest.py` blocks sockets *and* the
  `research` seam. Do not weaken it.
- `script.yaml` is never rewritten by this phase. Beats are read; document 2's
  bytes are load-bearing for `script_sha256` (D-026).
- Validation errors name the beat **index and type**, because a script with
  twelve beats and a message saying "text is required" is unusable.

## File Structure

| File | Responsibility |
|---|---|
| `src/agenticsocial/video/script.py` | beat-type registry, per-type validation, `Script`/`Beat` |
| `src/agenticsocial/video/plan.py` *(modify)* | consume a validated `Script`; keep resolution |
| `src/agenticsocial/video/cli.py` *(modify)* | `agsoc video review` |
| `tests/test_video_script.py`, `tests/test_video_review.py` | |

## Tasks

**Task 0 — carried debt.** D-025's unvalidated `series.toml` fields
(`tolerance_sec` accepts `"eight"` and `-99` one line below strictly-validated
`target_sec`; `register` accepts anything though Phase 4 branches on it), and
D-042's two separate `64` constants. Both become load-bearing this phase:
**`tolerance_sec` is a gate input the moment runtime estimation exists.**

**Task 1 — `script.py`.** The beat-type registry and per-type validation for the
full §7.1 catalogue, plus `Script`/`Beat` as frozen dataclasses (D-062: a
snapshot that mutates lies about its file). `plan.py` becomes a consumer.

**Task 2 — runtime estimation, the duration gate, and `agsoc video review`.**
Total runtime against `target_sec ± tolerance_sec`, per-beat breakdown, and the
review output an operator reads before approving.

## The duration gate needs a stale-object test — D-063

The Task 0d implementer predicted where the next bypass comes from:

> The next bypass probably won't be a forged field. It'll be a Phase 3 gate that
> reads `episode.status` or a stale `series.target_sec` instead of re-reading
> disk — and `frozen=True` is completely inert against that.

**This is that gate.** `abs(total - target_sec) > tolerance_sec` reads a value
off a `Series` object. Every gate in this phase ships with a test that loads an
object, changes the file underneath it, and asserts the gate follows the file.
Four bypasses of the write-shaped version have already cost this project four
tasks; this is the read-shaped version arriving on schedule.

## Exit criteria

- [ ] Every §7.1 beat type validates, with errors naming the beat index and type.
- [ ] A beat type that validates but cannot yet render says so explicitly.
- [ ] `agsoc video review` shows beats, per-beat holds, total runtime, and
      whether it is inside `target_sec ± tolerance_sec`.
- [ ] The duration gate follows the file, proven by a stale-object test.
- [ ] `script.yaml` is byte-identical after any command in this phase.
- [ ] No network; suite stays near 2s.

## Carried, not blocking

`%YAML`/BOM/missing-leading-`---` script robustness (D-040) lands here if it
touches `_split`; otherwise Phase 4. `engine/` packaging (D-056) is required
before Phase 8. `video/render.py`'s subprocess seam is unguarded in tests
(D-067) — Phase 8.
