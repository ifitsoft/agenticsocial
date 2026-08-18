# Task 0 Brief: Validate what the renderer interpolates

**Phase:** 4 · **Branch:** `feat/video-phase-04-engine`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

Gates the rest of the phase. Two items, both deferred with reasons that expire
the moment the engine renders more than one beat type.

## Why now

**A render that looks fine and is wrong is the worst failure this product can
have** — worse than a crash, because nothing tells you. Phase 3's Task 0 named
the exact mechanism:

> `accent = 5` flows through `plan.json` into a CSS custom property, CSS silently
> discards the invalid declaration, and you get a correct-looking render with
> wrong colours and no error anywhere. Phase 4 must validate it **before writing
> `plan.json`**, not at render time.

`design.*` is unvalidated today: `accent = 5`, `accent = "blue"`, `accent = true`
all load and all reach the stage. Six of eight tokens become CSS custom
properties in `planbuild.js`.

**And the act id-vs-label question (D-070) gates beat validation.** Task 1
declined to enforce `warm_acts` because the join column is ambiguous:

> `2026-08-12.js` has `warmActs:['03 — Agents']` — that is the act **label**,
> while `series.toml` would join on **id** (`"03"`). Enforcing a rule whose key
> is ambiguous turns a soft problem into a hard failure on the wrong side.

Phase 4 is the phase that decides, because it is the phase that consumes it.

## The decision you are being asked to make, not merely implement

**Beats and `warm_acts` reference acts by `id`.** Rationale: an id is stable
under rewording, a label is display text an operator will edit; joining on
display text means renaming an act silently unwires every beat pointing at it.
The committed episode uses labels only because `content/*.js` had no `series.toml`
to join against — it was passing the whole string because there was nothing else.

`planbuild.js` therefore resolves `beat.act` → the act's `label` for display,
falling back to the raw value when no act with that id is declared. **Falling
back rather than failing** is deliberate: a script written before its series
declared acts must still render, and spec §6 marks act `beats` counts advisory.

If you disagree, say so in the report **before** implementing — this is the last
cheap moment.

## Rules, each with its negative half

- **R1** Every `design.*` value that becomes a CSS custom property must be a
  valid CSS colour. **Negative:** `type_family` and `type_scale` are **not**
  colours and must not be colour-checked.
- **R2** Validation happens in Python, before `plan.json` is written.
  **Negative:** not in `planbuild.js` — by then the operator has waited for a
  render.
- **R3** A beat's `act` is an act **id**. **Negative:** an undeclared id is *not*
  an error; it renders as the raw string.
- **R4** `warm_acts` entries are act ids. **Negative:** an id that matches no
  declared act is a **warning**, not a refusal (D-070 — the soft problem stays
  soft).

## The mutants this task must kill

Include falsy values — three tasks running, mutants survived because every bad
value I chose was truthy.

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | colour check dropped | R1 |
| M2 | `accent = 5` accepted (int) | R1 |
| M3 | `accent = ""` accepted (falsy) | R1 |
| M4 | `accent = "blue"` accepted (named colours are not in our palette format) | R1 |
| M5 | `type_family` colour-checked | R1 negative |
| M6 | validation moved to render time | R2 |
| M7 | undeclared act id raises | R3 negative |
| M8 | `warm_acts` mismatch raises | R4 negative |
| M9 | `warm_acts` mismatch silently ignored, no warning | R4 |

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 23 defects across five phases.
- Do not add dependencies. No network. Never stage anything under `docs/`.
- **Report the mutation score.**

## Colour format

The palette in `series.toml` and both committed episodes uses `#RRGGBB` only.
Accept `#RGB` and `#RRGGBB`, case-insensitive. **Reject named colours**
(`"blue"`), `rgb()` and anything else — not because they are invalid CSS, but
because the scaffold writes one format and a second silently-accepted format is
how a palette drifts. Say so in the error.

---

- [ ] **Step 1: Tests** — `tests/test_video_series.py` and
      `tests/test_video_plan.py`, each with a `precondition:` line.

Cover: each of the six colour tokens rejecting `5`, `""`, `true`, `"blue"`,
`"#12345"`, `[]`; `#fff` and `#FFFFFF` accepted; `type_family`/`type_scale`
accepting any string; validation raising from `write_plan` **before** the file
appears on disk; a beat naming an undeclared act rendering rather than raising;
`warm_acts` naming an undeclared id producing a warning and still loading.

- [ ] **Step 2: Implement** in `series.py` (the colour check, since that is where
      `design` is read) and `plan.py` (act resolution into the plan).

The plan gains a resolved act label per beat so `planbuild.js` does no lookup:

```python
        "act": act_id,
        "act_label": label_for(act_id),   # falls back to act_id
```

- [ ] **Step 3: Run everything, then commit.**

- [ ] **Step 4: Kill all nine mutants**, then your own sweep.

- [ ] **Step 5: Prove the failure mode is closed.** Set `accent = 5` in a real
      workspace, run `agsoc video preview`, and paste what happens. It must fail
      **before** any frame is rendered, naming the field.

---

## Your report

`docs/superpowers/worklog/video/phase-04/task-0-report.md`:

1. **What I changed.**
2. **TDD evidence** and the **mutation score**.
3. **All nine mutants** plus your own sweep.
4. **Step 5's real run**, pasted.
5. **Files changed**, both commit SHAs.
6. **Issues or concerns**, including:
   - **Do you agree beats should reference acts by id?** Argue it. If labels are
     right, this is the last cheap moment to say so.
   - `planbuild.js` maps six of eight design tokens to CSS variables.
     `type_family` and `type_scale` are dropped silently — Phase 1.5 flagged that
     and nothing has changed. Should Phase 4 wire them, or drop them from
     `series.toml`? Dropping a documented knob is also an answer.
   - Anything else the renderer will interpolate that nothing validates.
