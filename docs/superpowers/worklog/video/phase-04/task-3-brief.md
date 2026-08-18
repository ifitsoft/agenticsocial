# Task 3 Brief: `dumbbell`, `custom`, and the beat that runs out of time

**Phase:** 4 · **Branch:** `feat/video-phase-04-engine` · **Follows:** `7cd5f11`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

Closes Phase 4. Three things, and the first is a live defect that ships a false
number.

## Step 0: a beat that runs out of time ends on a figure nobody authored

Leader-verified against the real renderer, sampling the last frame `render.mjs`
captures:

```
hold 2.0s -> last rendered frame: $0.75 in  $3.75 out  40% cheaper
hold 3.0s -> last rendered frame: $0.75 in  $3.75 out  50% cheaper
```

**At a 2-second hold the video's final frame reads 40% for an authored 50%.**
R2 is defeated not by rounding but by running out of time — the mid-count value
*becomes* the terminal value.

Your predecessor predicted it and gave the reason mid-count frames are otherwise
fine (D-083): a mid-count value is **unstable, bounded and derived**. All three
properties fail the moment the count cannot finish.

**Fix in the renderer**, which is the only layer that knows both the animation
constants and the hold. A beat whose count-up cannot complete within its hold is
**refused**, the way an uncited chart is refused. Compute the requirement from
the same constants the animation uses — do not hardcode a number that can drift
from them.

The error must name the beat, the hold it has, and the hold it needs.

## `dumbbell` — there is no primitive, and the missing property is the point

`2026-08-12.js` builds the AMIE chart inline from `crow`/`track`/`dot`/`merged`.
`scene.html:112` has the CSS. Extract a primitive from that episode, preserving
the two things that make the type exist:

1. **Direction only, no numeric axis.** Spec §7.2: this type exists *because a
   source published ratings rather than scores*. It must not render numbers.
   `engine.js:121`'s comment calling `jumpChart` "a before→after dumbbell" is
   misleading — they are different types and the difference is a verification
   difference, not a visual one.
2. **Where two values coincide, one two-tone marker** — not two dots stacked.
   The episode's own comment says why: *"no gap: one two-tone marker rather than
   two dots stacked invisibly"*. Stacking hides a series, and a chart that
   silently omits a series is worse than one that refuses to draw.

`footnote` is **required** — §7.2 says a dumbbell must say it encodes direction
only.

## `custom` — executed, and therefore attested

`custom.js` is arbitrary JavaScript that will be **executed in the page**. Two
consequences:

**Determinism.** `Date.now()`, `Math.random()` and `performance.now()` inside a
custom beat break `__seek(t)` purity — the one invariant this project has never
had to re-fix. `script.py` rejects a `js` string containing them.

**Be honest about what that is: a lint, not a sandbox.** It catches the accident,
not the adversary — `window['Ma'+'th'].random()` walks straight past it. Say so
in the error and in the docstring. The same framing as D-062: the guard raises
the floor, it is not a boundary.

**Attestation.** §7.1 says custom beats need "manual attestation" and names no
field. Define it: `custom` requires **`attest`**, a non-empty string in which the
author states what the beat displays and takes responsibility for it. No
mechanical check can verify arbitrary rendering output, so the honest substitute
is a signed sentence that appears in `agsoc video review` — a claim a person made
on the record, not a check nobody ran.

## Rules, each with its negative half

- **R1** A beat whose count cannot finish inside its hold is refused.
  **Negative:** a beat with no count-up is unaffected however short it is.
- **R2** `dumbbell` renders no numbers. **Negative:** its `footnote` is required
  and *does* render, because that is where the "direction only" caveat lives.
- **R3** Coincident values draw one merged marker. **Negative:** distinct values
  draw two separate dots.
- **R4** `custom.js` runs. **Negative:** a `js` string containing an obvious
  non-determinism source is refused **at validation**, before any render.
- **R5** `custom` requires a non-empty `attest`. **Negative:** no other type
  does.
- **R6** `__seek(t)` stays pure with a custom beat present.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | count-fits-hold check dropped | R1 |
| M2 | check applied to beats with no count | R1 negative |
| M3 | requirement hardcoded rather than derived from the animation constants | R1 |
| M4 | `dumbbell` renders row values as text | R2 |
| M5 | `dumbbell.footnote` optional | R2 negative |
| M6 | coincident values draw two stacked dots | R3 |
| M7 | distinct values merged | R3 negative |
| M8 | `Date.now()` accepted in `js` | R4 |
| M9 | the lint also rejects a harmless identifier containing "random" | R4 negative |
| M10 | `attest` optional or allowed empty | R5 |
| M11 | `attest` required on other types | R5 negative |

## Ground rules

- **Four commits:** Step 0, `dumbbell`, `custom`, determinism extension.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 23 defects across five phases.
- Include falsy values: `0` is a legitimate dumbbell value.
- No new dependencies. No new CSS without flagging it.
- `node render.mjs --day 2026-08-14 --probe` must still render the committed
  episode; `2026-08-12` contains the real dumbbell, so **probe that day too**.
- `determinism.test.mjs` covers every type including `custom`, and stays green.
- **`RENDERABLE == set(BEAT_TYPES)` when you are done** — that is Phase 4's exit
  criterion.
- **Report the mutation score.**

---

- [ ] **Step 5 — render every type at once.** One script with all ten, rendered
      through `agsoc video preview`. Paste the page text per beat, and confirm
      the dumbbell shows no digits.

---

## Your report

`docs/superpowers/worklog/video/phase-04/task-3-report.md`:

1. **What I implemented**, and which `dumbbell`/`custom` decisions were mine
   rather than sourced from the episode or the spec.
2. **TDD evidence** and the **mutation score**.
3. **All eleven mutants** plus your own sweep.
4. **Step 5's page text**, all ten types.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - Is the count-fits-hold requirement computed correctly for `jumpChart` as
     well as `kpis`? They stagger differently.
   - `custom` executes author JS in the page. Beyond determinism, what else can
     it do that nothing prevents — reach the network, read `window`, mutate other
     beats' DOM? Say what is actually true rather than what is comfortable.
   - Anything blocking `RENDERABLE == set(BEAT_TYPES)`.
