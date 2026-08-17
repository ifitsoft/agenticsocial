# Task 2 Brief: Runtime, the duration check, and `agsoc video review`

**Phase:** 3 · **Branch:** `feat/video-phase-03-script-schema` · **Follows:** `429871e`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

Closes Phase 3. This is the command an operator reads **before approving
anything**.

## Step 0 first: the catalogue encodes a shape that cannot exist

Task 1 discovered — and I verified — that spec §7.1's `jumpChart` fields describe
a single bar, while `engine.js` takes `jumpChart(rows, max, d0, parent)` and the
episode that actually rendered passes **four rows** of
`[label, from, to, shown]`. The spec is now corrected (D-068); `script.py` still
encodes the wrong shape.

**Fix it before anything writes a script against it.** In `script.py`'s
catalogue, `jumpChart` requires `rows` (a non-empty list of mappings, each with a
string `label` and numeric `before`/`after`; `shown` optional string) plus
`scale` (a positive number) and `footnote` (a string). Keep `src`/`quote`
required — §7.2 is unchanged.

Own commit, with tests that use the real four-row shape from
`engine/content/2026-08-14.js`.

## What `review` is, and is not

**It is a report, not a gate.** Spec §11 puts the gate at `approve` (Phase 7).
`review` shows the operator what they are about to approve and **exits 0 even
when the runtime is out of tolerance** — a diagnostic command that refuses to
speak when something is wrong is the D-018 mistake in a new place.

Phase 7's `approve` will consume the same `check_runtime` and *refuse*. This task
builds the check and displays it; it does not enforce it.

## Rules, each with its negative half

- **R1** Total runtime is `sum(hold) * pace`. **Negative:** per-beat `hold` in
  the review display is the **unscaled** authored value, so an operator editing
  the script sees the number they typed.
- **R2** The runtime is in tolerance when `abs(total - target_sec) <=
  tolerance_sec`. **Negative:** `tolerance_sec: 0` demands exactness and is
  legitimate; the boundary is inclusive.
- **R3** `review` reports beats, holds, total, target, tolerance, and verdict.
  **Negative:** it exits **0** whether in tolerance or out — it is a report.
- **R4** `review` names beats that validate but cannot yet render.
  **Negative:** it does not treat them as errors.
- **R5** `review` never writes. **Negative:** not `script.yaml`, not `plan.json`,
  not a derived `pace`.
- **R6 (D-063)** The check follows the **file**, not a cached object.

## D-063 arrives here, and I want it argued rather than assumed

Phase 2 predicted this:

> The next bypass probably won't be a forged field. It'll be a Phase 3 gate that
> reads `episode.status` or a stale `series.target_sec` instead of re-reading
> disk — and `frozen=True` is completely inert against that.

`check_runtime(script, series)` reads `series.target_sec` off an object. Today the
CLI loads fresh on every invocation, so staleness cannot bite — **which is
exactly the argument that preceded all four write-shaped bypasses.**

Write the stale-object test at the CLI level: change `series.toml` between two
`review` invocations and assert the second reflects the file. Then, in your
report, answer honestly: **is "callers load fresh" a sufficient guarantee, or
does `check_runtime` need to re-read like `disk_status` does?** Phase 7 builds
its refusal on this, so a wrong answer here is a gate defect later.

## The mutants this task must kill

**Include falsy values.** Two tasks running, mutants survived because every bad
value I chose was truthy.

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | total computed without `pace` | R1 |
| M2 | review displays scaled holds | R1 negative |
| M3 | tolerance uses `<` instead of `<=` | R2 negative |
| M4 | `within` hardcoded `True` | R2 |
| M5 | `tolerance_sec: 0` treated as "no limit" | R2 negative |
| M6 | `review` exits 1 when out of tolerance | R3 negative |
| M7 | review omits unrenderable beats | R4 |
| M8 | review treats an unrenderable beat as an error | R4 negative |
| M9 | review writes `plan.json` as a side effect | R5 |
| M10 | `check_runtime` caches the series across calls | R6 |

## Ground rules

- **Three commits:** Step 0 (jumpChart), then tests, then implementation.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 23 defects across five phases.
- Do not add dependencies. No network. Never stage anything under `docs/`.
- **Report the mutation score.**

## Interfaces

```python
@dataclass(frozen=True)
class RuntimeCheck:
    total_sec: float
    target_sec: int
    tolerance_sec: int
    within: bool
    delta: float          # total - target, signed

def check_runtime(script: Script, series: Series) -> RuntimeCheck
```

CLI: `agsoc video review <episode> [--series S]`.

Output should let an operator see, at a glance, what they are approving —
something like:

```
the-brief/2026-08-17 · draft · 12 beats

   #  act    type        hold  text
   0  01     statement    3.5  Google shipped its main agentic model…
   1         kpis         4.6  $0.75 per 1M input tokens  [src: venturebeat]
   2  02     dumbbell     4.0  (cannot render yet)
   …

runtime 118.4s · target 120s ± 8s · within tolerance
2 beats cannot be rendered yet: dumbbell (1), quote (1)
```

Exact formatting is yours; the information is not optional.

---

- [ ] **Steps**

1. Step 0 — jumpChart catalogue + tests, own commit.
2. Tests for R1–R6 and the mutant table, own commit.
3. Implementation, own commit.
4. Kill all ten mutants plus your own sweep, at least three falsy-value.
5. A real end-to-end: build a workspace, write a twelve-beat script including one
   unrenderable type, run `agsoc video review`, paste the output.

---

## Your report

`docs/superpowers/worklog/video/phase-03/task-2-report.md`:

1. **What I implemented.**
2. **TDD evidence** and the **mutation score**.
3. **All ten mutants** plus your own sweep.
4. **Step 5's real run**, pasted.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **The D-063 question above.** Argue it; do not agree with me.
   - Is `review` readable with twelve beats, or does it need paging/truncation?
     You are the first to see real output.
   - Anything `review` should show that an operator would need before approving
     and currently cannot see.
