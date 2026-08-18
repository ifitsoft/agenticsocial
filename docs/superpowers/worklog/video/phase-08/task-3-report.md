# Task 3 Report: `agsoc video probe`

**Phase:** 8 · **Branch:** `feat/video-phase-08-render`
**Commits:** `f2cce58` (tests, red) · `c72f83b` (implementation) ·
`b953788` + `a57ebd5` (a defect found by running it) · `14ba13e` (a survivor)

## The decision: its own command, and the flag goes

Three options were on the table — a new command, an alias for
`preview --probe`, or amending the spec to say the flag is enough. **Its own
command**, and `preview` loses `--probe`.

The argument is about what the thing is *for*. `render`'s success screen tells
the operator that the approval stops short of the pixels (D-116) and that
**nobody has looked at this video** — and then pointed them at a flag on the
command that takes fourteen minutes. One dropped flag and you get the render you
were trying not to wait for. A cheap operation reachable only as a modifier of
the expensive one is not cheap in the way that matters.

An alias would keep both doors open, which is two things to keep identical and
two places to look — a small instance of the shape D-113 removed. Amending the
spec would have been writing down the weaker thing because it was already there;
§6 already said `agsoc video probe <ep> [--at T] [--format F]`, and the spec was
right. **No spec amendment was needed.**

`preview` keeps its job: the whole video, ungated, no status. There is now one
way to get frames on disk.

## It is ungated, and that is the point

A probe reads the script, writes no status, and works at **any** status —
`draft`, `in_review`, `approved`, `rendered`. Probing is how an operator decides
whether to approve; requiring approval to inspect inverts the workflow. And
`rendered` being terminal (D-006) is a statement about transitions, not about
whether you may look at the thing.

It renders the same `plan.json` `render` would, via the same `write_plan`,
because a probe drawn from anywhere else would be reporting on a different
render.

## What it costs, measured

Same episode, same machine, same day:

| | frames | wall clock |
|---|---|---|
| `agsoc video render` | 180 | **50.2s** |
| `agsoc video probe` | 3 (one per beat) | **1.7s** |
| `agsoc video probe --at 3.5` | 1 | **1.0s** |

For a real 120-second episode the render is ~14 minutes and the probe is still
seconds — it scales with beats, not with frames. **That ratio is the answer to
D-116's gap.** Nothing can make an approval cover the pixels; what it can do is
make looking at them cost a second.

```
$ agsoc video probe 2026-08-18 --series the-brief --at 3.5
the-brief/2026-08-18 · 1 frame(s)
      at       …/episodes/2026-08-18/probe/at-3.5.png
      note     nothing moved — a probe reads the script and draws frames. What you are looking at is
               this machine's fonts and this machine's Chromium, which is exactly the part no
               approval covers
```

I opened `at-3.5.png`. It is the beat, in the series' typeface, on the series'
surface colour, with the date chip and the `_pasted` source tag — a real frame,
at 1080×1920.

## Details worth the words

* **Frames land in `<episode>/probe/`.** Spec §5 put it beside `out/`, and
  `create_episode` has created that directory since Phase 1 — **nothing had ever
  written to it**, while `preview --probe` wrote to `out/probe`. `out/` is the
  deliverable; a probe is a working note about it.
* **Python clears the last probe before the new one.** Stale frames beside fresh
  ones are the stale-ledger problem in PNG form: an operator cannot tell which
  describes the script they are reading. `render.mjs` clears its own `--probe`
  directory, but only that one and only in that mode, and a guarantee that lives
  in a subprocess is not one Python can state.
* **`--at 90` on a six-second episode is refused, naming the runtime.** Python
  resolved the runtime, so the check is free — and the frame it would otherwise
  shoot is a black rectangle, which reads as a broken renderer rather than as a
  number typed past the end.
* **ffmpeg is not required.** A probe never encodes; demanding it would refuse a
  working command over a tool it does not run.
* **`render.mjs --at` now honours `--out`.** It wrote into `engine/probe`, a
  gitignored working area. That directory currently holds 25 orphaned PNGs from
  a session on 17 August — the leak, on disk, in the repo.
* `render`'s success screen points at `agsoc video probe`, and a test reads the
  command list off typer's own registry rather than a literal, so registering
  the command and quoting it stay one fact. A screen naming a command that does
  not exist reads as a working suggestion right up until it is typed.

## A defect found by running it

`--at 90` refused correctly **and deleted the previous probe's frames on its way
out** — the clearing ran ahead of the range check. Found by running the real
command against the throwaway workspace, not by reading the code; the unit tests
were green.

The whole value of `--at` is that typing a number and looking is cheap. A
refusal that costs you the frames you were looking at makes it expensive in
exactly the way the command exists to avoid. Fixed as a rule rather than as a
special case — **every refusal now happens before anything is removed** — with
the failing test committed first (`b953788`, `a57ebd5`).

## Evidence

Tests first (`f2cce58`): 19 tests, 16 failing. The 3 that passed were the
negative-invariant halves — no status moved, no script rewritten, nothing in
`engine/` — vacuous until the command existed. 21 tests at HEAD.

```
$ uv run pytest -q            → 1809 passed in 17.35s
$ node determinism.test.mjs   → exit 0
$ node network.test.mjs       → exit 0
$ node coverage.test.mjs      → exit 0
```

**Mutation sweep, 34 mutants at HEAD** (Task 1's 26 with M9b/M9c retargeted,
plus M9d and seven probe mutants), `PYTHONDONTWRITEBYTECODE=1` throughout:
**32 killed, 2 survived, both fixed in `14ba13e`, then 34/34.** The probe
mutants:

| # | mutant | result |
|---|---|---|
| P1 | frames land in `out/` instead of `probe/` | killed |
| P2 | the previous probe's frames are left beside the new ones | killed |
| P3 | a refused probe deletes the frames it was not going to replace | killed |
| **P4** | **a probe demands the ffmpeg it never runs** | **SURVIVED** → killed |
| P5 | `--at` writes its frame into `engine/probe` | killed |
| P6 | a probe is gated on approval like a render | killed |
| P7 | the success screen points at a command that does not exist | killed |

**P4 survived** because every assertion about "a probe does not encode" was
about what *ran*, never about what was *required*. The fix is the positive half:
an operator with no ffmpeg installed can still look at the frames.

## Exit criteria this closes

* `agsoc video probe` returns frames without a full render — **1.7s vs 50.2s**,
  measured.
* `render`'s output does not claim the pixels were approved, **and now points at
  a command that exists** for the operator who wants to check.
