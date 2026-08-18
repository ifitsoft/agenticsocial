# Phase 4 — The declarative engine renders the catalogue

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Every beat type in spec §7.1 renders from `script.yaml`, vertical, deterministically.

**Spec:** §7 (catalogue), §7.2 (chart integrity), §9 (formats)
**Roadmap:** §5 — flagged as the project's **highest-uncertainty phase**
**Branch:** `feat/video-phase-04-engine`

## What we are walking into

Phase 1.5 de-risked the *handoff* — `plan.json` works, the engine does no timing
arithmetic, and `statement` renders. What is unproven is everything else in the
catalogue. Right now:

```
validated : body custom dumbbell jumpChart kpis list quote signoff statement title
renderable: statement
```

Nine types to close, and they are not equally hard.

### Surveyed before planning, not assumed

| Type | What actually exists |
|---|---|
| `statement` | done (Phase 1.5) |
| `body`, `list`, `title`, `signoff` | no primitive needed — `E` + `rise`/`fade`/`draw`, and both committed episodes build them inline |
| `kpis` | **primitive exists** (`engine.js:107`) |
| `jumpChart` | **primitive exists** (`engine.js:122`), takes `rows, max, d0, parent` |
| `dumbbell` | **no primitive.** `2026-08-12.js` builds the AMIE chart inline from `crow`/`track`/`dot`/`merged`; the CSS exists in `scene.html:112` |
| `quote` | **no primitive and no episode uses it** — the type is spec-only (D-069) |
| `custom` | escape hatch; §7.1 also says "manual attestation required", a field nobody has named |

**A naming trap:** `engine.js:121`'s comment calls `jumpChart` "a before→after
**dumbbell**", but spec §7.1 makes them different types — `jumpChart` carries
numbers on a common scale, `dumbbell` encodes **direction only** because its
source published ratings rather than scores. One primitive, a misleading comment,
CSS for both. Do not let the comment collapse two types into one; the distinction
is a *verification* distinction, not a visual one.

## Global Constraints

- **`window.__seek(t)` stays pure.** The determinism test ships green in the same
  commit as any engine change. This is the invariant `CLAUDE.md` calls
  load-bearing and the one property this project has never had to re-fix.
- **No timing arithmetic in the engine.** Holds arrive pre-scaled; `META.pace`
  stays 1. Phase 1.5 established this and it is why the determinism test can
  police the engine at all.
- Vertical only (1080×1920). Wide is Phase 10.
- No new dependencies, Python or Node. Playwright stays pinned exactly (D-055).
- No network in the suite — `tests/conftest.py` guards sockets *and* the
  `research` seam. Do not weaken it.

## File Structure

| File | Responsibility |
|---|---|
| `engine/planbuild.js` | a builder per beat type; no arithmetic |
| `engine/engine.js` *(modify)* | a `dumbbell` primitive extracted from `2026-08-12.js` |
| `engine/determinism.test.mjs` *(modify)* | every beat type, pixel **and** page state |
| `src/agenticsocial/video/plan.py` *(modify)* | `RENDERABLE` widens; design tokens validated |

## Tasks

**Task 0 — validate what the renderer will interpolate.** `design.*` values are
unchecked today. Phase 3's Task 0 named the consequence precisely: *`accent = 5`
flows through `plan.json` into a CSS custom property, CSS silently discards the
invalid declaration, and you get a correct-looking render with wrong colours and
no error anywhere.* **A render that looks fine and is wrong is the worst failure
this product can have** — worse than a crash, because nothing tells you.
Validation belongs **before `plan.json` is written**, not at render time. Also
settles the act id-vs-label question (D-070), which gates beat validation.

**Task 1 — the text beats.** `body`, `list`, `quote`, `title`, `signoff`. Golden
frames per type. `quote` is spec-only, so its design is a judgement call that
must be flagged as one.

**Task 2 — the chart beats.** `kpis` and `jumpChart` against their existing
primitives, using the real four-row shape from `2026-08-14.js`. These are the
**strictly verifiable** types (§7.2): a beat must carry `src` and `quote`, and
every rendered number must appear in that quote. The renderer must not be able to
display a number the plan did not carry.

**Task 3 — `dumbbell` and `custom`.** Extract a `dumbbell` primitive from
`2026-08-12.js` — including the two-tone merged marker where values coincide,
which exists so a coincidence cannot hide a series. Then `custom`, and the
attestation §7.1 implies.

## Exit criteria

- [ ] Every §7.1 type renders; `RENDERABLE == set(BEAT_TYPES)`.
- [ ] `node determinism.test.mjs` green, including the plan path, for a script
      exercising every type.
- [ ] A bad `design.*` value is refused **before** `plan.json` is written.
- [ ] `node render.mjs --day 2026-08-14 --probe` still renders the committed
      episode unchanged — the hand-written path must not regress.
- [ ] `dumbbell` renders direction only, with the footnote §7.2 requires.
- [ ] Golden frames for every type, both committed episodes still byte-stable.

## Carried

`quote`, `dumbbell.caption`, `kpis` item optionality and `custom.js` are
**speculative** (D-069) — no committed episode uses them. Phase 4 is where they
are found wrong; expect it and say so rather than bending the catalogue silently.
`engine/` packaging (D-056) is required before Phase 8, not here.
