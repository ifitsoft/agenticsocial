# Task 2 Report: retire the hand-written path

**Phase:** 8 · **Branch:** `feat/video-phase-08-render`
**Commits:** `e60df85` (tests, red) · `adf7a1f` (implementation + docs)

## The split, stated

| | verdict |
|---|---|
| `render.mjs --day <date>` | **retired.** The flag is gone; the renderer takes `--plan` and nothing else, and exits 2 with a message naming `agsoc video render` if given no plan |
| `render.mjs --pace`, the `FPS = 30` constant, `Math.round(total * FPS)` | **gone with it.** They existed only to serve the day path |
| `content/2026-08-12.js`, `content/2026-08-14.js` | **kept, and kept exercised.** Regression fixtures |
| `scene.html?day=<date>` | **kept.** The browser's loader — the scrubbing surface and the fixture loader |
| `determinism.test.mjs`'s `day path` case | **kept, green** |

**Why the flag had to go and the files did not.** The flag was a second route
from an episode to an MP4, and it was the route that passed neither `check` nor
`approve` — nothing it produced had been verified against a corpus or signed by
a human. That is the two-paths-to-one-answer shape Phase 7 spent three tasks
eliminating (D-113, D-059), rebuilt in Node. The *files* are not a route; they
are two complete episodes exercising every builder and both chart forms, and
they are the only realistic input the determinism invariant has. They load
through `scene.html?day=…`, which is the **browser's** loader, not the
renderer's — which is exactly why the flag could be removed without costing the
invariant its input.

The distinction I want a future reader to keep: **"retired" means "no longer the
way to render a video", not "deleted".** Two tests pin that half explicitly, so
the next person who greps for `--day`, finds nothing, and concludes the content
files are dead code will get a failure instead.

## Two things that fell out of it

* **`Math.round(total * FPS)` disappeared.** It was the `--day` fallback for a
  question `plan.json` already answers (D-007), and the two disagree at the
  rounding boundary — which reaches a viewer as a video that stops one frame
  early. This also closes **M9b and M9c**, the two mutants that survived Task
  1's sweep: the old test asserted `"plan.total_frames" in src`, and the string
  appeared in three places, so deleting the *use* left the assertion true. There
  is now no arithmetic in the file to disagree with, and the test asserts the
  absence of `* FPS`, `const FPS` and `Math.round(total` on the source with
  comments stripped.
* **The refusals moved ahead of the browser launch.** A missing plan and a plan
  without an integer `total_frames` are both readable from the file; spending a
  Chromium startup to discover them is how a check becomes a thing operators
  skip.

A bare `node render.mjs` used to default the date to today and render whatever
was lying in `content/`. **Refused, not defaulted** — "rendered something" is
the failure mode that does not look like one.

## Making the supported path obvious

* **`engine/README.md`** now opens on the `agsoc` pipeline —
  `new → ingest → storyboard → check → approve → render → probe` — states that
  `agsoc video render` is how a video gets made and that nothing in the
  directory is a shortcut around it, and says plainly that running `render.mjs`
  by hand is for debugging the renderer. **The hand-typed ffmpeg recipe is
  gone**: it was a copy-pasteable way to make a video that no gate had seen. A
  "what retired, and what did not" section states the split for a reader who
  arrives via `git log`.
* **`CLAUDE.md`** gains the same paragraph, plus the fix the brief asked for:
  the tracked-file list was missing **`determinism.test.mjs`, `network.test.mjs`
  and `coverage.test.mjs`** — including the determinism test the same section
  calls load-bearing — and also `planbuild.js`. All four are listed now, with a
  note that the node tests are **not** part of `uv run pytest` and are run by
  hand.

## Evidence

Tests first (`e60df85`): 9 tests, 6 failing — the flag, the refusal, the
arithmetic, the guard ordering, the README and CLAUDE.md. The 3 that passed were
the "what stays" half, which was already true and is now pinned.

```
$ node determinism.test.mjs   → deterministic          (exit 0)
$ node network.test.mjs       → no request escapes...  (exit 0)
$ node coverage.test.mjs      → cannot be talked past  (exit 0)
$ uv run pytest -q            → 1788 passed in 15.41s
```

**And it renders.** The end-to-end run in the Task 1 report §5 was executed
against this code, not against Task 1's: 180 frames, 50.2s, a playable
1080×1920 h264 file. The plan path is the only path now, and it works.

Mutation: `M9b`, `M9c` and a new `M9d` ("renders again without being given a
plan") all killed — `M9d` after `14ba13e`, having survived the first version of
the test because the header comment explaining the retirement contains the
string `agsoc video render` that the assertion was looking for.

## Carried, not done

**D-056 — `engine/` is not in the wheel.** `ENGINE_DIR` is still
`Path(__file__).resolve().parents[3] / "engine"`, and `pyproject.toml` still
ships only `src/agenticsocial`. D-056 called this **required before Phase 8**.
The phase plan says it "belongs here if Task 2 needs it" — Task 2 did not need
it, and doing it means moving a tracked Node subproject and editing packaging,
which is not a change to make inside a task about retiring a flag. **It remains
the largest known gap: `render` works from a source checkout and from nowhere
else.**
