# Phase 8 — The render pipeline

**Goal:** `agsoc video render <ep>` produces a vertical MP4 from an approved,
undrifted episode — and refuses everything else.

**Spec:** §6 (pipeline), §9 (rendering), §10 (status machine)
**Roadmap:** §5 · **Branch:** `feat/video-phase-08-render`
**Depends on:** 4 (engine), 7 (approve gate) — both merged.

## The sentence this phase makes true

Everything upstream produces a *verified, approved* `script.yaml`. Nothing turns
it into a file you can watch through the supported path. Phase 1.5 proved the
plumbing with a hand-written script; **this phase makes it the product.**

## What this phase must not overclaim

D-116 states the scope of an approval exactly, and it is narrower than it sounds:

> **The approval covers everything the operator authors, and nothing the renderer
> is.**
>
> *Bound:* beats bytes, `pace`, palette, series name, byline, act labels.
> *Unbound:* `engine.js`, `planbuild.js`, `scene.html`'s CSS, **the resolved
> font — the one thing that differs between machines** — Chromium/Playwright,
> the ffmpeg binary and its flags, and the chosen `--format`.

`render` may say "this episode was approved and has not drifted". It may **not**
imply the output is what the approver saw, because a font substitution or an
engine edit changes the pixels with every check green. **Say the true thing.**

## The gate is three checks, not one

D-115, and they stay distinguishable so an operator is told *which* thing moved:

1. `assert_transition(APPROVED → RENDERING)` — status.
2. `approval_drift(episode)` — did the authored inputs change?
3. `stale_reason(episode)` — did the corpus change under the ledger?

Folding them into one predicate rebuilds the second-path shape D-113 eliminated.

## Global constraints

- **Only the CLI moves status** (CLAUDE.md). `approved → rendering → rendered`,
  and `rendering → failed` with `failed → rendering` as the retry edge (§10).
  `rendered` is terminal in the MVP (D-006).
- **`window.__seek(t)` purity is non-negotiable.** The determinism test ships
  green in the same commit as any engine change.
- **Rendering is slow** — roughly 230 ms/frame, so a 120 s episode is ~14 minutes
  and `page.screenshot()` dominates. **No test may render a full episode.** Use a
  few-second script, and say in the report what the suite's wall-clock cost is.
- Python resolves all timing into `plan.json`; Node does zero arithmetic (D-007).
- No new dependencies. No network.

## Tasks

**Task 1 — `agsoc video render`.** The three-check gate, the status transitions
including the failure path, plan → node → ffmpeg, and the output landing
somewhere stated. **A crash mid-render must leave a recoverable state**, not
`rendering` forever — that is the video analogue of the `posted_ids` invariant.

**Task 2 — retire the hand-written path.** `render.mjs --day <date>` reads
`content/*.js`. Those two episodes are the engine's only real regression
fixtures and **must keep working as tests**; what retires is their status as *the
way to render a video*. Decide the split and state it, and make the supported
path obvious to someone reading the README.

**Task 3 — `agsoc video probe`.** §6 lists it: one frame per beat, or one frame
at `--at T`. Cheap given Task 1, and it is how an operator inspects without
waiting 14 minutes. It is also the honest answer to the D-116 gap: **if you want
to know what the frame looks like, look at the frame.**

## Open questions to decide, not default

- **Where does the MP4 go, and what is it called?** It must not land in
  `engine/` (gitignored working area) and must be findable a month later.
- **What happens to a stale MP4** when an episode is re-rendered after an edit?
  A file on disk that no longer matches the script is the same class of problem as
  a stale ledger.
- **Does `render` re-run `check`?** Phase 7 decided `approve` requires a fresh
  ledger rather than recomputing. The same argument probably applies; make it
  explicitly rather than by inheritance.

## Exit criteria

- [ ] An unapproved episode cannot render, naming the reason.
- [ ] A drifted episode cannot render, naming **which** input moved.
- [ ] An episode with a stale corpus cannot render, distinguishably.
- [ ] An approved, undrifted episode renders a playable vertical MP4.
- [ ] A crash mid-render leaves a state the operator can recover from.
- [ ] `agsoc video probe` returns frames without a full render.
- [ ] Determinism stays green; no test renders a full episode.
- [ ] `render`'s own output does not claim the pixels were approved.

## Carried

D-107 (word-spelled figures) → Phase 9. `type_family`/`type_scale` reach no pixel
(D-116) → Phase 10, which is the next phase to touch layout. `engine/` packaging
(D-056) belongs here if Task 2 needs it.
