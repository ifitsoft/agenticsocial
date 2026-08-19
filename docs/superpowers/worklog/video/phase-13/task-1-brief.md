# Task 1 Brief: one approval must actually render every format

**Branch:** `fix/render-second-format` · **Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`
**Spec:** §9 (multi-format rendering), §10 (status machine)

## The defect, reproduced against the operator's real episode

```
$ agsoc video render 2026-08-18 --series the-brief --format wide
NOT rendered — cannot move rendered -> rendering; allowed next: none (terminal).
```

And the **success message the same command printed minutes earlier**:

> `format  vertical · chosen at render time and NOT part of the approval — `
> **`one approval renders every format`**`, and the approver saw none of them`

**The command promises a capability the status machine forbids.** Spec §9's own
CLI block documents both forms:

```sh
agsoc video render 2026-08-14                  # every enabled format
agsoc video render 2026-08-14 --format wide    # one
```

Neither works after the first render. `[formats] enabled = ["vertical", "wide"]`
in `series.toml` is read by nothing but the list screen.

**This is the seventh instance of this project's overclaim pattern** (D-106,
D-110, D-112, D-118, D-121, D-123, and this) — a line asserting more than the
system does. The previous six were summary lines about verdicts; this one is a
capability claim, which is a new species and worth recording as such.

## What is actually wrong, and what is not

**D-006 is not wrong.** It cut `rendered → publishing` because that edge was
reachable but never exercised, and it made `failed` ambiguous. `rendered` having
no outgoing edge was a *consequence* of that cut, not its purpose.

**The category error is treating a per-format artifact as an episode lifecycle
state.** `rendered` describes the story: verified, approved, committed to. It
should not also mean "and exactly one file exists". Rendering the wide cut of an
already-approved, undrifted script does not change anything about the story — it
produces a second artifact from the same signed bytes.

## What to build

Make **`agsoc video render <ep> --format wide` work on an episode that is already
`rendered`**, and make the no-`--format` form render **every enabled format**
per §9 and `series.toml`'s `[formats] enabled`.

**Decide and argue the mechanism.** Two candidates, and there may be better:

1. Add `rendered → rendering` to `VIDEO_TRANSITIONS` — simple, and re-rendering
   after an engine fix becomes possible too.
2. Leave the table alone and make a second-format render not a transition at all,
   since the episode is already in its terminal state.

**Whichever you choose, the three gates must still hold in full** — status,
`approval_drift`, `stale_reason` (D-115). A second format is only safe *because*
the script and design are provably unchanged since approval. **Do not weaken the
drift check to make the re-render possible**; that inverts the whole point.

**This is the transition table that let a draft be published in v1** (D-059).
Treat a change to it with the care that history deserves: enumerate every path
that writes status and show each is still gated (Phase 7's R5), and do not
introduce a second way to reach `rendering`.

## Rules, each with its negative half

- **R1** An approved, undrifted, already-`rendered` episode can render a format it
  has not yet produced. **Negative:** a **drifted** episode still cannot render
  anything, in any format.
- **R2** `render <ep>` with no `--format` renders every format in
  `[formats] enabled`. **Negative:** a format not enabled is refused, naming it.
- **R3** Re-rendering a format that already exists is **explicit**, not silent —
  the operator learns the file will be replaced.
- **R4** No new way to reach `rendering` that skips a gate. **Negative:** every
  status write still goes through `assert_transition`.
- **R5** The success message's claims are all true after this change.
  **Negative:** if any claim is still false, **change the message, not just the
  code** — an accurate refusal beats an inaccurate promise.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | second format still refused | R1 |
| M2 | a drifted episode can now render | R1 negative — **the dangerous one** |
| M3 | a stale corpus can now render | R1 negative |
| M4 | no-`--format` renders only the default | R2 |
| M5 | a disabled format renders | R2 negative |
| M6 | an existing file is silently overwritten | R3 |
| M7 | a status write added that skips `assert_transition` | R4, D-059 |
| M8 | the message still claims something untrue | R5 |

## Ground rules

- **Commits: tests first, then implementation.** Do not squash.
- **`PYTHONDONTWRITEBYTECODE=1`, and paste the harness output** (D-118).
- **Never quote a piped exit code** (D-105).
- **A full render is ~13 minutes. No test may render a full episode** — use a
  few-second script, and mock the encode where you only need the gate's answer.
- **The operator's `workspace/` holds a real, approved, rendered episode
  (`2026-08-18`) and its mp4. Back it up, verify the backup path does not already
  exist, and do not destroy that file.** Other episodes: `2026-08-17`, `-17b`,
  `-17c` — unapproved, unedited.
- Never run `agsoc video approve` against the operator's workspace.
- No new dependencies, no network.

---

- [ ] **Step 1** — tests from the mutant table. Failing. Commit.
- [ ] **Step 2** — the mechanism. Commit.
- [ ] **Step 3** — `[formats] enabled` honoured. Commit.
- [ ] **Step 4** — mutants, plus Phase 7's R5 enumeration re-run.
- [ ] **Step 5** — **prove it on the real episode**: render `2026-08-18 --format
      wide` in a *copy* of the operator's workspace, and paste `ffprobe`
      (1920×1080). Then show a drifted episode still refused.

---

## Your report

`docs/superpowers/worklog/video/phase-13/task-1-report.md`:

1. **Your mechanism decision**, argued against the alternative.
2. **The R5 enumeration** — every status-writing path, still gated.
3. **TDD evidence**, the **mutation score with harness output**.
4. **Step 5's `ffprobe` and the drift refusal**, pasted.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **Audit every other capability claim the CLI prints.** Six overclaims were
     about verdicts; this one was about what the tool can do. Find the next one.
