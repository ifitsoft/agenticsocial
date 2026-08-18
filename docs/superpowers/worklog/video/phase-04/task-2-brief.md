# Task 2 Brief: The chart beats — `kpis` and `jumpChart`

**Phase:** 4 · **Branch:** `feat/video-phase-04-engine` · **Follows:** `9830fc5`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

These are the **strictly verifiable** types (spec §7.2). Everything else in this
phase is presentation; these two carry figures a viewer will believe.

## Step 0: widen the vocabulary by one token (own commit)

Adopted as D-080 on your predecessor's count of 49 committed scenes: `<em>` and
`warm-t` are *"a second emphasis that speaks in colour rather than weight, used
exactly where each episode pivots"*, and nothing covers them.

Add `*accent*` → `<em>` to the prose converter, alongside `**bold**`. Same
escape-then-convert order. Not `<br>`, not `warm-t`.

Two tests: `*accent*` produces an `<em>`, and `**bold** and *accent*` in one
string produce one of each with the connective intact — the greedy-regex failure
your predecessor found in `**…**` applies here too.

## The rule this task exists to enforce

Spec §7.2: *"there is no path to rendering a number that isn't in a source."*

The schema already requires `src` and `quote` on both types. **That is not
sufficient**, because the renderer can *manufacture* a number the plan never
carried. The obvious way:

```
value: 0.756, decimals: 1   →   the frame shows  $0.8
```

`0.8` is in no source, in no quote, and in no plan. Phase 5 would verify `0.756`
against the quote, pass, and ship a video showing a number nobody checked.
**Display rounding is a number-inventing machine** and it is already reachable —
`engine.js:97`'s `count()` takes `decimals`.

**R2 below is the fix, and it is the heart of this task.**

## What exists

- `kpis(items, d0, tone)` — `engine.js:107`. `2026-08-14.js` calls it with
  `[[0.75,'per 1M input tokens','',2,'$'], …]` → `[value, label, suffix, decimals, prefix]`.
- `jumpChart(rows, max, d0, parent)` — `engine.js:122`. Rows are
  `[label, from, to, shown]`; `2026-08-14.js` passes four rows and `max = 70`.
- `count(el, d0, dur, to, suffix, decimals, prefix)` — `engine.js:97`, the
  eased count-up both rely on.

Read all three before writing. **Do not add CSS** without flagging it.

## Rules, each with its negative half

- **R1** `kpis` and `jumpChart` render only when the beat carries `src` and
  `quote`. **Negative:** `title`/`signoff` still require neither.
- **R2** **Every number the frame displays is a number the plan carried.**
  **Negative:** `prefix`, `suffix` and thousands separators are presentation and
  may be added freely — they change how a value *reads*, not what it *is*.
  Concretely: refuse the beat when `round(value, decimals) != value`. If an
  author wants `0.8` on screen, the script says `0.8`, because the script is what
  gets verified.
- **R3** `jumpChart.shown` is the one field rendered as HTML. **Negative:** every
  label, footnote and caption in both charts is text.
- **R4** A row value outside `[0, scale]` is **refused**, not clipped.
  **Negative:** a value exactly equal to `scale` is fine.
- **R5** `__seek(t)` stays pure and the engine does no timing arithmetic.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | `kpis` renders without `src`/`quote` | R1 |
| M2 | `title` made to require `src`/`quote` | R1 negative |
| M3 | **`round(value, decimals) != value` accepted** | R2 |
| M4 | prefix/suffix refused as "invented" | R2 negative |
| M5 | `shown` escaped like prose | R3 negative |
| M6 | a `kpis` label rendered via `innerHTML` | R3 |
| M7 | a row value above `scale` clipped silently | R4 |
| M8 | a row value equal to `scale` refused | R4 negative |
| M9 | rows rendered in a different order than authored | — |
| M10 | `footnote` dropped | R3 |
| M11 | `META.pace` set from the plan | R5 |

M3 and M4 are a matched pair and easy to get backwards: **rounding invents a
number; a currency symbol does not.**

## Ground rules

- **Four commits:** Step 0, tests, builders, determinism extension.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 23 defects across five phases.
- **Include falsy values** in wrong-type tests: `0` is a legitimate KPI value and
  a legitimate `before`, so a truthiness check is a live bug here, not a
  hypothetical.
- No new dependencies. No network in the Python suite.
- `node render.mjs --day 2026-08-14 --probe` must still render the committed
  episode — it contains the real jumpChart, so this is a direct regression test.
- Extend `determinism.test.mjs` with both types; **no pixel golden files**.
- **Report the mutation score.**

---

- [ ] **Step 5 — a real render, and look at it.** Build a script with a `kpis`
      beat using the real `$0.75 / $3.75` figures and a `jumpChart` with the real
      four rows from `2026-08-14.js`. Render, then **paste the page text of a
      probe frame from each**. I want to see the numbers that actually reached
      the screen, not a hash.

---

## Your report

`docs/superpowers/worklog/video/phase-04/task-2-report.md`:

1. **What I implemented.**
2. **TDD evidence** and the **mutation score**.
3. **All eleven mutants** plus your own sweep.
4. **Step 5's page text**, pasted for both chart types.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **Is R2 sufficient?** Find another route by which the frame can show a
     number the plan did not carry — a count-up mid-animation, a percentage
     derived from the scale, an axis label, a computed delta. `__seek(t)`
     samples *mid-count*, so a frame at t=1.2 may show a number no one authored.
     That is either fine or it is the whole problem; argue which.
   - `kpis` takes a 5-tuple positionally. The schema names fields. Is the
     mapping unambiguous, and what happens when a field is absent?
   - Anything a chart can display that Phase 5 has no way to verify.
