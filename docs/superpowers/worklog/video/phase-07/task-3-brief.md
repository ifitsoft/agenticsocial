# Task 3 Brief: an approval must cover what the frame will look like

**Phase:** 7 · **Branch:** `feat/video-phase-07-approve` · **Follows:** Task 2
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

Task 2 closed the `scale` case: an edit that shifts every bar while every claim
still verifies. Its report then named a bigger one, and I verified it.

## The hole

`series.toml`'s `[design]` block goes straight into `plan.json`
(`plan.py:268` — `"design": dict(series.design)`) and repaints every frame.
**`approve.py` never mentions it.**

So: approve an episode, change `accent` or `type_scale` in `series.toml`, render
— and you have shipped something the approver never saw, with a **valid
approval** and **no drift**.

This is strictly worse than the `scale` case Task 2 closed:

- `scale` affects one beat; `design` affects **every frame of every episode in
  the series**.
- `scale` lives in the file the digest covers; `design` lives in a **different
  file the approval does not read at all**.
- A design change is *routine* — it is the knob an operator is most likely to
  turn between approving and rendering, because it feels cosmetic.

§10's rule is *"`render` refuses if the script has changed since approval"*. The
spirit is that **an approval covers what the approver saw**, and the frame is
what they saw.

## What to build

Extend the approval record to cover the design inputs that reach `plan.json`, and
extend `approval_drift` to name a design change the way it already names a script
change.

**Decide the scope and argue it.** Not everything in `series.toml` reaches the
frame — `cadence` is advisory, `target_sec` changes pacing but is already visible
in `review`. **Cover what `plan.py` actually copies into the plan**, derived from
the code rather than from a list you write by hand, so a new design key is
covered the day it is added. Task 1's `COLLECTORS`-by-checker-identity pattern
and Phase 5's planbuild⇄claims tie are the precedents.

Keep the shapes Phase 7 already settled:

- **One `classify()`.** Do not add a verdict path.
- **`approval_drift` reads the file, not the object it was handed**, and fails
  closed on anything it cannot answer.
- **Drift deliberately does not ask `corpus_sha`'s question** — that is
  `stale_reason`'s, and folding them together rebuilds the second-path shape.
  A design digest is a *third* question; keep it distinguishable in the output,
  so an operator is told **which** thing moved.

## Rules, each with its negative half

- **R1** A change to a design value that reaches the plan is detected after
  approval and **named**. **Negative:** changing an advisory field that never
  reaches a frame does not cry drift.
- **R2** The covered set is derived from what `plan.py` copies. **Negative:** a
  new design key added tomorrow is covered without anyone remembering to add it —
  and if that cannot be guaranteed, the failure is a **loud refusal**, not a
  silent gap (D-096).
- **R3** Script drift, design drift and a stale corpus are **three
  distinguishable answers**. **Negative:** none of them silently subsumes another.
- **R4** Re-approving after an intentional design change is possible.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | design change undetected | R1 |
| M2 | any `series.toml` edit cries drift | R1 negative |
| M3 | covered keys hardcoded, new key silently uncovered | R2 |
| M4 | new key uncovered **and silent** rather than refused | R2 negative |
| M5 | design drift reported as script drift | R3 |
| M6 | design drift swallows the stale-corpus answer | R3 negative |
| M7 | a design change permanently blocks re-approval | R4 |
| M8 | drift check reads the passed object rather than the file | Task 1's rule |

## Ground rules

- **Commits: tests first, then implementation.** Do not squash.
- **`PYTHONDONTWRITEBYTECODE=1`** in any mutation sweep (D-100).
- **Never quote a piped exit code** (D-105).
- **Run `approve` only against a throwaway workspace you create**, and **verify
  your backup is not nested inside an older backup** — that has now bitten one
  implementer. `workspace/` holds three real operator episodes; leave all three
  passing `check`, unapproved and unedited.
- All workspace writes via `workspace.atomic_write`.
- No new dependencies, no network, no LLM.
- **Report the mutation score.**

---

- [ ] **Step 1** — a failing test: approve, change `accent`, drift is named.
- [ ] **Step 2** — the coverage set, derived from `plan.py`. Commit.
- [ ] **Step 3** — mutants plus your own sweep.
- [ ] **Step 4** — end to end in a throwaway workspace: approve clean, change
      `accent`, show the refusal; re-approve; show it clears. **Paste all three.**

---

## Your report

`docs/superpowers/worklog/video/phase-07/task-3-report.md`:

1. **The scope you covered**, and what you deliberately left out.
2. **How a new design key stays covered**, and what happens if it cannot be.
3. **TDD evidence**, the **mutation score**, all eight mutants plus your sweep.
4. **Step 4's screens**, pasted.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **What can still change between approval and render without being named?**
     Be exhaustive: fonts, the engine's own source, `scene.html`'s CSS, ffmpeg
     flags, the format. **An approval that covers the script but not the renderer
     is a partial guarantee, and Phase 8 needs to know exactly which part.**
