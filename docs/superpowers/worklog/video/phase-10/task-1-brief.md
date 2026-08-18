# Task 1 Brief: wide format — a declared context, not a stylesheet fork

**Phase:** 10 · **Branch:** `feat/video-phase-10-wide`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`
**Spec:** §9 (multi-format rendering)

The spec already decided the shape, and the first line of §9 is the whole brief:

> **A format is a declared context, not a stylesheet fork.**

```js
vertical = { w:1080, h:1920, safeTop:430, safeBottom:1560, measure:'narrow', scale:1.00 }
wide     = { w:1920, h:1080, safeTop:120, safeBottom: 960, measure:'wide',   scale:0.62 }
```

## The invariant, and it is free if you take it seriously

> **Format changes layout, never timing.** `__seek(t)` stays pure and both
> formats are frame-identical in time.

Consequences the spec spells out and you should not have to rediscover: pacing is
verified once and holds for every format, `claims.json` is format-independent,
and a probe frame at `t=42.9` is **directly comparable across formats** — which
is also your best test instrument.

**A second copy of the beat builders is how the two formats drift apart
silently, and the second copy is always the one nobody looks at.** One layout
system, two contexts.

## The risk this phase carries, stated plainly

A layout change **passes every check this project has built and can still ship
something wrong.** Verification compares text to sources. Drift compares authored
inputs. Determinism compares a frame to itself. **None of them can see a beat
whose text overflows its box at 1920×1080.**

So overflow must be made *loud*, and that is the real work here:

- A beat whose content does not fit its safe area is **refused or visibly
  marked**, in both formats.
- Prefer refusing at **plan time** if the geometry can be computed there — an
  error before a 14-minute render beats a bad frame after one.
- If it can only be detected in the page, then it must be detected in the page
  and surfaced through `render.mjs`'s `pageerror` path, which already exists.

**Silent clipping is the failure this phase exists to prevent.**

## The loose end from Phase 7 — resolve it, do not carry it

**D-116, leader-verified:** `type_family` and `type_scale` are copied into
`plan.json` and **the engine ignores them** — neither string appears anywhere in
`engine/`, where `PLAN_TOKENS` maps the six colours only. The type that is
actually drawn lives in `scene.html`'s CSS.

Two knobs an operator would reasonably believe control typography, that control
nothing — **and the approval binds them**, so they are also a false positive in
drift detection. **This is the phase that touches layout. Wire them up or delete
them, and say which.**

## Rules, each with its negative half

- **R1** One layout system, two declared contexts. **Negative:** per-format
  differences live in data (`measure`, `scale`, safe area), not in a forked
  builder.
- **R2** Format changes layout, never timing. **Negative:** `__seek(t)` stays
  pure; a probe at `t=42.9` is the same instant in both formats.
- **R3** Overflow is refused or visibly marked, **in both formats**.
  **Negative:** content that fits renders unremarked — do not cry wolf, D-040.
- **R4** `--format wide` works end to end for `render` and `probe`.
  **Negative:** `vertical` remains the default and is unchanged — **the two
  committed episodes must probe byte-identically to before.**
- **R5** The format is chosen at render time and is **outside the approval**
  (D-116). Say so where an operator reads it.
- **R6** `type_family`/`type_scale` are wired up or deleted. **Negative:**
  whichever you choose, the approval's covered set stays honest.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | a second copy of a beat builder for wide | R1 |
| M2 | timing differs between formats | R2 |
| M3 | `__seek` impure in wide | R2 |
| M4 | overflow clipped silently | R3 |
| M5 | overflow detected in vertical only | R3 |
| M6 | fitting content reported as overflow | R3 negative |
| M7 | `--format wide` renders at 1080×1920 | R4 |
| M8 | vertical output changes | R4 negative |
| M9 | render implies the format was approved | R5 |
| M10 | `type_family` left copied-but-ignored | R6 |

## Ground rules

- **Commits: tests first, then implementation.** Do not squash.
- **No pixel golden files** — Phase 4's ruling stands: they are Chromium-version
  bound and this project pins Playwright for that reason. **Assert on page text
  and geometry** (bounding boxes, overflow), which is also what catches "the
  builder silently did nothing".
- **No test renders a full episode** (~230 ms/frame). `probe` is your instrument:
  render 36.9s vs probe 5.6s vs one frame ~1.0s (D-119).
- `determinism.test.mjs` stays green **for both formats**, in the same commit as
  any engine change.
- **`PYTHONDONTWRITEBYTECODE=1`, and paste the harness output** (D-118).
- **Never quote a piped exit code** (D-105).
- **If you modify `workspace/`, back it up first**, verify the path does not
  already exist, and restore it. Three real episodes, unapproved and unedited.
- No new dependencies, no network.

---

- [ ] **Step 1** — tests from the mutant table. Failing. Commit.
- [ ] **Step 2** — the format as a declared context. Commit.
- [ ] **Step 3** — overflow detection. Commit.
- [ ] **Step 4** — `--format` through `render` and `probe`; the `type_*`
      resolution. Commit.
- [ ] **Step 5** — mutants plus your own sweep.
- [ ] **Step 6 — look at it.** Probe the same episode in both formats at the same
      `t`, and **paste the page text of each**. Then render a short episode wide
      and give me `ffprobe`: resolution, duration, frame count. **A frame nobody
      looked at is the exact failure mode this phase is about.**

---

## Your report

`docs/superpowers/worklog/video/phase-10/task-1-report.md`:

1. **How overflow is detected**, and whether it is plan-time or page-time.
2. **Your `type_family`/`type_scale` decision**, argued.
3. **TDD evidence**, the **mutation score with harness output**.
4. **Step 6's two page texts and the `ffprobe`**, pasted.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **Does one script legitimately produce both formats?** A 9:16 headline may
     simply not work at 16:9. If some beats need per-format text, that is a
     schema change — say so rather than quietly making one.
   - **What can still be visually wrong with every check green?** Be specific.
     This phase is the one where "the tests pass" is not sufficient.
