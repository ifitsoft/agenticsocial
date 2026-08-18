# Task 1 Brief: `agsoc video render`

**Phase:** 8 · **Branch:** `feat/video-phase-08-render`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`
**Spec:** §6, §9, §10

Everything upstream produces a verified, approved `script.yaml`. **Nothing turns
it into a file you can watch through the supported path.** This task does.

## The gate is three checks, and they stay separate

D-115. An operator must be told *which* thing moved:

1. `assert_transition(APPROVED → RENDERING)` — status.
2. `approval_drift(episode)` — did the authored inputs change?
3. `stale_reason(episode)` — did the corpus change under the ledger?

**Folding these into one predicate rebuilds the shape that published a draft in
v1** (D-059, D-113): two paths to one answer, one of them ungated. Phase 7 spent
three tasks eliminating it. Do not reintroduce it for tidiness.

## The claim this command must not make

D-116, measured, and it is narrower than it sounds:

> The approval covers **everything the operator authors, and nothing the renderer
> is.** Unbound: `engine.js`, `planbuild.js`, `scene.html`'s CSS, **the resolved
> font — the one thing that differs between machines** — Chromium/Playwright, the
> ffmpeg binary and its flags, and the chosen format.

So `render` may say *"approved, and nothing you authored has changed"*. It may
**not** say or imply *"this is what the approver saw"* — a font substitution
changes every frame with all three checks green.

This project has now caught itself overclaiming four times (D-106, D-110, D-112,
D-113). **The summary line is where it happens, every time**, because it is
written last by someone who already knows the answer. Write this one deliberately.

## The invariant, in its video form

`x/publish.py::publish_variant` saves `posted_ids` after **every single tweet**,
so an interruption can never double-post. The render analogue: **a crash mid-run
must leave a state the operator can recover from**, not `rendering` forever.

§10 gives you the edges: `rendering → failed`, `failed → rendering` as the retry.
Use them. **A status that can only be escaped by hand-editing a file on disk is a
bug**, and this is exactly the state machine where that happens.

Decide and argue: is a partial render resumable, or discarded and restarted? The
tweet analogue resumes because each post is irreversible; frames are not, which
may make the honest answer different.

## Rules, each with its negative half

- **R1** Only an `approved`, undrifted episode with a current ledger renders.
  **Negative:** each of the three failures is named **distinguishably** — an
  operator can tell status from drift from staleness.
- **R2** A crash leaves a recoverable state. **Negative:** a successful render
  ends `rendered`, and `rendered` is terminal (D-006).
- **R3** Timing arithmetic stays in Python; Node consumes `plan.json` (D-007).
  **Negative:** `__seek(t)` purity holds and `determinism.test.mjs` stays green.
- **R4** The MP4 lands somewhere stated and findable, **not** in `engine/`, which
  is a gitignored working area.
- **R5** `render` does not claim the pixels were approved.
- **R6** **No test renders a full episode.** ~230 ms/frame means a 120 s episode
  is ~14 minutes. Use a few-second script and report the suite's wall-clock cost.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | an unapproved episode renders | R1 |
| M2 | a drifted episode renders | R1 |
| M3 | a stale corpus renders | R1 |
| M4 | the three failures collapse into one message | R1 negative |
| M5 | the three checks folded into one predicate | D-113 |
| M6 | status left `rendering` after a crash | R2 |
| M7 | `failed → rendering` retry impossible | R2 |
| M8 | status written without `assert_transition` | D-059 |
| M9 | timing arithmetic moved into Node | R3 |
| M10 | MP4 written into `engine/` | R4 |
| M11 | success message implies the frames were approved | R5 |
| M12 | a test renders a full episode | R6 |

## Ground rules

- **Commits: tests first, then implementation.** Do not squash.
- **`PYTHONDONTWRITEBYTECODE=1`** in any mutation sweep (D-100).
- **Never quote a piped exit code** (D-105).
- `CliRunner` has swallowed a crash here (D-035): assert exit code **and** output
  **and** `result.exception`.
- **Run `render`/`approve` only against a throwaway workspace you create.** Never
  against `workspace/` — three real operator episodes live there, they must stay
  unapproved, unedited and passing `check`. **Verify your backup path does not
  already exist**; a nested backup has confused one implementer already.
- All workspace writes via `workspace.atomic_write`.
- No new dependencies, no network.
- **Report the mutation score** and the suite's wall-clock delta.

---

- [ ] **Step 1** — tests from the mutant table. Failing. Commit.
- [ ] **Step 2** — the gate and the status transitions. Commit.
- [ ] **Step 3** — plan → node → ffmpeg, and the output location. Commit.
- [ ] **Step 4** — the crash path. Commit.
- [ ] **Step 5** — mutants plus your own sweep.
- [ ] **Step 6 — render something and watch it.** Build a short episode in a
      throwaway workspace, approve it, render it, and **report the file: path,
      size, duration, resolution from `ffprobe`.** Then show the three refusals.
      **Paste all four screens.**

---

## Your report

`docs/superpowers/worklog/video/phase-08/task-1-report.md`:

1. **Your resume-versus-restart decision**, argued.
2. **Where the MP4 goes**, and why there.
3. **The exact success message**, and why it does not overclaim.
4. **TDD evidence**, the **mutation score**, all twelve mutants plus your sweep.
5. **Step 6's four screens and the `ffprobe` output**, pasted.
6. **Files changed**, all commit SHAs.
7. **Issues or concerns**, including:
   - **What is the worst thing that can happen mid-render?** Disk full, node
     killed, ffmpeg missing, a beat that throws at frame 3000. Say which of these
     you actually tested rather than reasoned about.
   - Anything that makes a render non-reproducible on a second machine.
