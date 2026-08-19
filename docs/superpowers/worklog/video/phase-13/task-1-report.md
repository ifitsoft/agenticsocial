# Task 1 Report: one approval renders every format

**Phase:** 13 · **Branch:** `fix/render-second-format` · **Spec:** §9, §10
**Baseline:** 2027 tests · **At HEAD:** 2053 tests, **18/19 mutants killed**

---

## 1. The mechanism, and the argument against the alternative

**Chosen: add `rendered → rendering` to `VIDEO_TRANSITIONS`.** One edge. Nothing
else in either table moves.

The brief's framing is right and I did not find a better one. **D-006 is not
wrong.** It cut `rendered → publishing` because that edge was reachable, never
exercised, and made `failed` ambiguous — with `failed → rendering` as the only
recovery edge, a *publish* failure could only be recovered by re-rendering an
artifact already on disk. `rendered` having no outgoing edge **at all** was the
consequence of that cut, not its purpose, and the consequence is what broke §9.

The category error is the one the brief names: **a per-format artifact was being
modelled as an episode lifecycle state.** `rendered` describes the story —
verified, approved, committed to. It should not also mean "and exactly one file
exists". Rendering the wide cut of an approved, undrifted script produces a
second artifact from the same signed bytes; it changes nothing about the story,
which is exactly why the only edge out of `rendered` comes straight back to it.

### Why not "leave the table alone; a second format is not a transition"

Three reasons, in increasing order of how much they cost.

**It rebuilds D-059's shape.** The alternative has to decide *whether to run the
status gate* by reading the current status: `if already rendered, skip the
transition`. D-059 is precisely a gate that consulted a status to decide whether
to check the status, and the bypass laundered itself through the gap. The
project's own standing rule — one function reads the authority and performs the
write it gates, with nothing in between (D-072) — is not compatible with a
caller-side branch that decides the gate does not apply today.

**It throws away every property the transition buys.** A 13-minute second-format
render that is killed leaves `rendered` on disk with no evidence it ever
started: `--restart` has nothing to restart, a render running in another
terminal is undetectable, and `_fail_episode` cannot record anything because
`rendered → failed` is not an edge either. The `rendering` window is not
bureaucracy; it is the only reason a killed render is recoverable.

**It is measurable, and it was measured.** The alternative is mutant **M7b** in
the sweep — implemented for real, not caricatured — and the suite kills it, on
`test_a_second_format_still_passes_through_rendering`: a crash mid-way must
leave `failed`, which is reachable only from `rendering`.

### What actually protects the 18 MB file

Not the status machine — it never did. `--restart` and a `failed` retry both
walk around a status, and `preview` (see §6.3) walks around it entirely. The
guarantee is now stated where it belongs:

> **a format whose file is already in `out/` is never re-rendered without
> `--replace`**, and every screen says which files that applies to.

So `render <ep>` on the operator's episode renders the missing wide cut, keeps
the vertical one, and names it. `render <ep> --format vertical` refuses and
names `--replace`. A run with nothing left to do **refuses** rather than
printing a green heading over two files it did not make.

### Three things deliberately NOT done

- **No per-format record archive.** `script.yaml`'s `render:` key keeps the
  meaning it has always had — *the most recent render attempt*, success or
  failure (a failure has always overwritten a success there). Adding a
  `renders:` map would be a second answer to a question nothing asks, and the
  per-format audit trail already exists in a better place: ffmpeg writes
  `script_file_sha256` into each MP4's `comment` tag, so every file can be
  matched back to the script it was made from without `script.yaml` at all.
  **Consequence worth stating:** after a two-format run, `render.file` names the
  last format rendered. See §6.4 for the one place that reads it.
- **`assert_transition` was not touched, and neither were the drift or ledger
  checks.** No check was weakened, softened, or made conditional on status. The
  two mutants that do exactly that (M2b, M3b — "skip drift/staleness once the
  episode is rendered") are both killed.
- **No new way to reach `rendering`.** See §2.

---

## 2. R5 enumeration — every status-writing path, re-run

Enumerated from the AST of everything under `src/`, not by grep, and now pinned
by `test_only_two_functions_write_a_status_key` so it stays enumerated.

### Writers of a `status` key

| # | function | table | what gates it |
|---|---|---|---|
| 1 | `video/episode.py::set_status` | `VIDEO_TRANSITIONS` | re-reads the status **from disk** and calls `assert_transition(current, target, VIDEO_TRANSITIONS)` in the same function that performs the write, with nothing in between; accepts no caller-supplied current value |
| 2 | `workspace.py::Workspace.set_status` | `ALLOWED_TRANSITIONS` | `assert_transition(self.disk_status(v), target)` — same shape |
| 3 | `workspace.py::Workspace.save_variant` | — | writes `self.disk_status(v).value`: it **cannot move** a status, it can only re-write the one already there. This is the D-059 fix itself |

There is no fourth. `script.yaml` in particular is written by exactly two
functions in the whole codebase — `episode.py:150` (creation) and
`episode.py:303` (`set_status`) — and **`render.py` contains no `atomic_write`,
no `write_text`, and no `meta["status"]`**, which a test asserts directly.

### Creation paths (write a status, but move nothing)

| function | value | why it needs no gate |
|---|---|---|
| `video/episode.py::create_episode` | `draft` | writes into a directory it claimed with `mkdir(parents=True)`; `FileExistsError` if it lost the race, so the file provably did not exist |
| `workspace.py::create_variant` | `draft` | `if path.exists(): raise` before the write |

`draft` is the initial state in both tables; there is no prior status to move
from.

### Every call site of writer #1

| call site | transition | gated by |
|---|---|---|
| `video/approve.py::approve_episode` | `in_review → approved` | takes identifiers, loads `series.toml` and `script.yaml` itself (D-072); refuses on open claims and on a stale/absent ledger first |
| `video/render.py::render_episode` (restart) | `rendering → failed` | `--restart` only; answers the STATUS question only — drift and staleness are still asked afterwards |
| `video/render.py::render_episode` | `→ rendering` | after all three checks; the authoritative assertion is inside `set_status` |
| `video/render.py::render_episode` | `rendering → rendered` | after the encode |
| `video/render.py::_fail_episode` | `rendering → failed` | the `except BaseException` path |

### Every call site of writer #2 (text pipeline, untouched)

`cli.py::approve` → `approved`; `x/publish.py::publish_variant` → `publishing`,
`failed`, `published`.

### What this task changed

**Zero new status writers. Zero new call sites.** `render.py` had four
`set_status(` calls before this task and has four after. The loop over formats
sits **inside** one `rendering` window: one `set_status(RENDERING)` before it and
one `set_status(RENDERED)` after it, regardless of how many formats render.
`rendering → rendering` is not an edge and is never attempted.

The only change to either table is `VIDEO_TRANSITIONS[RENDERED]`, from `set()` to
`{RENDERING}`. `test_video_transitions_table_is_exact` pins the whole table,
`test_no_video_state_reaches_publishing` still guards D-006, and
`test_failed_has_exactly_one_recovery_edge` still guards the recovery story.

---

## 3. TDD evidence and the mutation score

### The commits, in order

| SHA | what |
|---|---|
| `4d05291` | **tests only**, 22 failing — the mutant table |
| `dc8de82` | the mechanism: `rendered → rendering`, `--replace`, the exists-check |
| `cc17c96` | `[formats] enabled` honoured |
| `61fd47d` | tests for the three mutants the first sweep left alive |

Verified failing before the implementation, unpiped:

```
$ PYTHONDONTWRITEBYTECODE=1 uv run pytest -q
22 failed, 2029 passed, 6 warnings in 23.64s
```

At `61fd47d`:

```
$ PYTHONDONTWRITEBYTECODE=1 uv run pytest -q
2053 passed, 6 warnings in 26.47s
```

**No test renders a full episode.** Every subprocess in the render tests is
faked and the fixture script is ~6 s; `test_the_render_fixture_is_seconds_not_minutes`
and `test_no_test_launches_the_real_toolchain` pin that, and the whole suite runs
in ~26 s.

### The harness

`PYTHONDONTWRITEBYTECODE=1` throughout (D-100: with a 20 s suite, consecutive
mutants land inside one mtime second and CPython reuses a stale `.pyc`, so the
harness tests the *unmutated* module). Exit codes are read off
`subprocess.CompletedProcess.returncode`, never off a pipe (D-105).

### Sweep output, pasted

```
KILLED   M1  second format still refused
           1 failed, 1164 passed, 2 warnings in 20.58s
KILLED   M2a drift check deleted
           1 failed, 1146 passed, 2 warnings in 20.82s
KILLED   M2b drift skipped once rendered (the tempting one)
           1 failed, 1186 passed, 2 warnings in 22.22s
KILLED   M3a ledger check deleted
           1 failed, 1148 passed, 2 warnings in 23.27s
KILLED   M3b ledger skipped once rendered
           1 failed, 1188 passed, 2 warnings in 25.98s
KILLED   M4  no --format renders only the default
           1 failed, 1191 passed, 2 warnings in 27.27s
KILLED   M5  a disabled format renders anyway
           1 failed, 1193 passed, 2 warnings in 28.05s
KILLED   M6a an existing file is silently overwritten
           1 failed, 1164 passed, 2 warnings in 27.15s
KILLED   M6b an existing file is silently SKIPPED (no screen line)
           1 failed, 1198 passed, 2 warnings in 29.70s
KILLED   M6c --replace is not reported
           1 failed, 1197 passed, 2 warnings in 31.21s
KILLED   M7a set_status stops asserting the transition
           1 failed, 186 passed in 5.26s
KILLED   M7b a second format is not a transition at all (the rejected mechanism)
           1 failed, 1185 passed, 2 warnings in 58.50s
SURVIVED M7c ...and its closing write
           2053 passed, 6 warnings in 83.77s (0:01:23)
KILLED   M8a the help stops saying what no --format does
           1 failed, 1208 passed, 2 warnings in 71.86s (0:01:11)
KILLED   M8b the format line drops the every-format claim
           1 failed, 1206 passed, 2 warnings in 18.92s
KILLED   M9  output_path uses the wrong geometry
           1 failed, 817 passed, 1 warning in 9.36s
KILLED   M10 the exists-check runs BEFORE the three gates
           1 failed, 1209 passed, 2 warnings in 17.98s
KILLED   M11 the failure record names the format ASKED FOR, not the one that died
           1 failed, 1210 passed, 2 warnings in 21.48s
KILLED   M12 the run ends RENDERED even with nothing to render
           1 failed, 1164 passed, 2 warnings in 19.83s

score: 18/19 killed, 1 survived
```

**The survivor is equivalent by construction, and I am claiming that rather than
hiding it.** M7c guards the closing write with `if episode.status is not
Status.RENDERED:`. At that point `episode` is whatever
`set_status(episode, Status.RENDERING)` returned, and `set_status` returns
`replace(episode, status=target)` — so the guard is always true and the mutant is
the unmutated program. It only had meaning combined with M7b, which is killed.
A survivor that measures nothing is worse than no mutant; it is listed so the
19 adds up.

### The first sweep scored 14/18, and the three real survivors are the finding

| survivor | why every existing test missed it |
|---|---|
| **M10** exists-check hoisted above the three gates | every drift test asks for a format that is *not* on disk, so `todo` is non-empty and the reordered check never fires. The case it breaks is the operator's own: everything rendered, then an edit — and the mutant answers "already rendered", which reads as *and nothing else is wrong* |
| **M11** failure record names `targets[0]` | in a one-format run the two strings are identical. Killing it needed a fake that fails only the **second** encode; `FakeRun(fail_on=...)` fails every call and cannot express it |
| **M8a** `--format` help reverts to "output format" | the test searched the whole `--help` screen, and the command **docstring** above the options box also says "every enabled format" — so the option's own help could say anything. **This is D-118 arriving again**: an assertion matching a string produced by a different part of the output than the one it claims to check. It now reads the `--format` option line and nothing else |

### And one that was never failable at all

Every `assert "--force" not in result.output` in `test_video_render_cmd.py` —
guarding the gate's CLI surface since Phase 8 — **could not fail.** Rich renders
a flag as `ESC[1;36m-ESC[0mESC[1;36m-forceESC[0m`, so the literal `--force`
never appears in the output. Measured, not assumed: a real `--force` flag was
added to `video render` and

- the old assertion **passed**;
- the new ANSI-stripping one **failed**.

Both flag tests now go through `help_text()`, which strips ANSI and squashes
whitespace.

---

## 4. Step 5 — proved on a copy of the operator's real episode

### The backup, before anything else

```
$ shasum -a 256 <backup>/…/2026-08-18/out/vertical-1080x1920.mp4
eff44093eb5c7fbe33666b71a20eeaeeae6184fbda935687cff5b483cf762e1c  …
$ shasum -a 256 workspace/…/2026-08-18/out/vertical-1080x1920.mp4
eff44093eb5c7fbe33666b71a20eeaeeae6184fbda935687cff5b483cf762e1c  …
```

Backup path checked to not exist before the copy. All work below is against a
**second** copy (`proof-workspace`). `agsoc video approve` was never run against
the operator's workspace, and `2026-08-17`, `-17b`, `-17c` were not touched.

### 4.1 The drifted episode is still refused — on the real episode

A copy of the operator's episode, still `rendered`, still approved by name, with
**one beat's text edited** in the beats document:

```
$ agsoc video render 2026-08-18 --series the-brief --format wide
the-brief/2026-08-18 · NOT rendered — the approval no longer describes this episode
      why      the beats document has changed: the approval covers sha256
               712b03fb34c860f7ff7acabdd5dc9f5518bd0408e568a4b8ff7d1ae3c54d2b8c, the file on disk is
               sha256 7143859a09b6189fbff6c4fb1d7efe789cd550a2c475b6586e7dbaebf8958f4b — approved by
               Ali Abdukarim at 2026-08-18T22:27:09-05:00. Re-run `agsoc video check` and approve
               again, or put the change back
      fix      put the change back, or run `agsoc video check 2026-08-18 --series the-brief` and
               approve again
```

Exit 1. Status on disk after: `rendered`, unmoved. `out/` after: `plan-vertical.json`
and `vertical-1080x1920.mp4` — **no `plan-wide.json` was even written**, so the
refusal landed before the renderer was reached. This is M2 on real data, and it
is the one that had to hold.

### 4.2 The other two refusals, also on the operator's episode

```
$ agsoc video render 2026-08-18 --series the-brief --format vertical
the-brief/2026-08-18 · NOT rendered — already rendered: out/vertical-1080x1920.mp4
      fix      nothing was rendered and nothing was replaced. The three checks all passed — this is
               only about the file(s) above. `agsoc video render 2026-08-18 --series the-brief
               --replace` re-renders and overwrites them; add `--format F` to replace one
```

The 18 MB file is named, `--replace` is named, and the screen says which of the
four possible problems this is not.

```
$ agsoc video render 2026-08-18 --series the-brief --format wide   # after enabled = ["vertical"]
the-brief/2026-08-18 · NOT rendered — the-brief does not render 'wide' —
series.toml's `[formats] enabled` lists: vertical. Add it there, or render one of those
```

Status unmoved in both cases.

### 4.3 The wide render of the operator's episode reaches the renderer — and the renderer cannot finish it

**This is the part of Step 5 I could not deliver as asked, and the reason is not
in this task's code.**

`agsoc video render 2026-08-18 --series the-brief --format wide`, on a copy of
the operator's workspace, now gets **past all three gates and the new edge** —
`out/plan-wide.json` is written, the episode moves to `rendering`, and the
renderer starts. It then dies, **three times out of three**, after 12-26
minutes:

```
$ agsoc video render 2026-08-18 --series the-brief --format wide
the-brief/2026-08-18 · NOT rendered — the renderer failed (exit 1):
      '  - fonts loaded'
    ],
    name: 'TimeoutError'
  }

  Node.js v25.5.0
```

Exit 1, and the episode is left `failed` with the reason recorded — **which is
the crash path of the new edge working correctly on the real episode**, and it
is the strongest single piece of evidence that a second format is a real
transition rather than a side door. It also proves the file guarantee: after
three failed wide renders, the vertical MP4 is byte-identical to the operator's,
`eff44093eb5c7fbe33666b71a20eeaeeae6184fbda935687cff5b483cf762e1c`.

Attempt 1 overlapped the mutation sweep, so CPU contention was the obvious
explanation. It is not the explanation: attempts 2 and 3 ran with the machine
otherwise idle and failed the same way. Frame-rate samples from attempt 3, taken
a minute apart against the temp frame directory:

```
02:03:05  124 frames
02:04:05  292      (168/min)
02:05:05  370      ( 78/min)
02:06:05  442      ( 72/min)
02:07:20  534      ( 73/min)
```

For comparison, the operator's own **vertical** render of this same episode
sustained ~225 frames/min for its whole 16 minutes (22:59 plan → 23:15 MP4,
3599 frames). **Wide starts at a comparable rate, drops to a third of it, and
eventually stalls past Playwright's 30 s action timeout.** Same pixel count, same
plan, same machine, same output volume.

`render.py::_run` keeps only the last six lines of stderr, so the CLI screen
above is the tail of a much more specific error. Run directly, the renderer says
exactly what happened:

```
119.95s · 3599 frames @ 30fps · wide 1920x1080
  4%  (150/3599)  eta 1390s
  8%  (300/3599)  eta 1379s
 13%  (450/3599)  eta 1583s
 17%  (600/3599)  eta 1699s

page.screenshot: Timeout 30000ms exceeded.
Call log:
  - taking page screenshot
  - waiting for fonts to load...
  - fonts loaded

    at shoot (…/engine/render.mjs:121:14)
    at async …/engine/render.mjs:154:5 {
  name: 'TimeoutError'
}
```

**A single `page.screenshot` exceeded 30 seconds**, at roughly frame 708 of 3599
— about `t=23.5s` into the episode — after the renderer's own ETA had climbed
1390 → 1699 s over the preceding 600 frames. The fonts had loaded; it is the
rasterisation that stalled. `engine.js` re-inserts the scene node on every seek
(deliberately — `render.mjs`'s comment says it is what keeps a frame a pure
function of `t`), which is a full re-raster per frame, and something about the
wide stage makes that cost grow until it exceeds Playwright's default action
timeout.

That is an **engine defect in the wide format** — Phase 10's territory, not the
status machine's — and it means §9's "one script legitimately renders as two" is
still not true end-to-end for a 120 s episode, for a reason no amount of work on
`VIDEO_TRANSITIONS` can reach.

**I did not soften any message in response to this.** The CLI's claim is about
what the *approval* covers — "one approval renders every format" — and that is
now true: the same approval, unmodified, produced two artifacts in §4.4 below. A
renderer that is too slow for one of them is a different sentence, and the honest
place for it is a defect report, not a hedge on a screen that would then be
wrong for every episode short enough to render.

### 4.4 The pipeline, end to end, on real node and real ffmpeg

Since the operator's 120 s episode cannot complete a wide render on this machine,
the geometry proof is a **short episode through the same commands** — a
throwaway workspace of my own (never the operator's), ingested, checked,
approved, rendered:

```
$ agsoc video render 2026-08-20 --series the-brief          # no --format
the-brief/2026-08-20 · rendered 2 formats
      file     …/episodes/2026-08-20/out/vertical-1080x1920.mp4
               0.9 MB · 6.0s · 1080x1920 · 180 frames @ 30fps
      file     …/episodes/2026-08-20/out/wide-1920x1080.mp4
               0.7 MB · 6.0s · 1920x1080 · 180 frames @ 30fps
      format   vertical · 1080x1920 and wide · 1920x1080 · chosen at render time and NOT part of the
               approval — one approval renders every format, and the approver saw none of them
      approved Phase 13 Task 1 proof at 2026-08-19T02:24:11-05:00 — and nothing you authored has
               changed since: the beats, `pace` and series.toml's design are the ones that were
               signed
      scope    the approval does NOT cover what drew these frames — engine.js, planbuild.js,
               scene.html's CSS, the font this machine resolved, Chromium and ffmpeg are all outside
               the approval, and the font is the one that differs between machines…
```

**`ffprobe`, both files:**

```
=== vertical-1080x1920.mp4
width=1080
height=1920
r_frame_rate=30/1
nb_frames=180
duration=6.000000
size=858086
TAG:comment=script_file_sha256=604aae937861451e28a1d1d2d0ac51e702cdeddc0b20f9eb69adcb1cfcf34589
=== wide-1920x1080.mp4
width=1920
height=1080
r_frame_rate=30/1
nb_frames=180
duration=6.000000
size=684480
TAG:comment=script_file_sha256=604aae937861451e28a1d1d2d0ac51e702cdeddc0b20f9eb69adcb1cfcf34589
```

**1920×1080, and the two files carry the same `script_file_sha256`** — one
approval, two artifacts, from bytes that are provably the ones that were signed.
Identical frame counts and durations are §9's other invariant showing up in the
container: format changes layout, never timing.

### 4.5 The three follow-up behaviours, on those real artifacts

```
$ agsoc video render 2026-08-20 --series the-brief
the-brief/2026-08-20 · NOT rendered — already rendered: out/vertical-1080x1920.mp4, out/wide-1920x1080.mp4
      fix      nothing was rendered and nothing was replaced. The three checks all passed …
```
`UNPIPED_EXIT=1` — measured unpiped (D-105).

```
$ agsoc video render 2026-08-20 --series the-brief --format wide --replace
the-brief/2026-08-20 · rendered 1 format
      file     …/out/wide-1920x1080.mp4
               0.7 MB · 6.0s · 1920x1080 · 180 frames @ 30fps
      replaced wide-1920x1080.mp4 — the file that was there is gone
```

And the shape the operator's episode is actually in — one format on disk, one
missing:

```
$ rm out/wide-1920x1080.mp4 && agsoc video render 2026-08-20 --series the-brief
the-brief/2026-08-20 · rendered 1 format
      file     …/out/wide-1920x1080.mp4
      kept     vertical-1080x1920.mp4 was already in out/ and was NOT re-rendered — `--replace` re-
               renders it

vertical sha before=94371881a3ca9e67 after=94371881a3ca9e67
```

The 18 MB file an operator would have lost is the one that is provably
untouched in every one of these runs.

---

## 5. Files changed

| file | change |
|---|---|
| `src/agenticsocial/models.py` | `VIDEO_TRANSITIONS[RENDERED]`: `set()` → `{RENDERING}`, with the reasoning and D-006's boundary |
| `src/agenticsocial/video/render.py` | `output_path()`; `RenderRun`; `render_episode` takes `fmt=None` and `replace=`, reads `series.formats`, renders a list, refuses `exists` |
| `src/agenticsocial/video/cli.py` | `--format` defaults to every enabled format; `--replace`; the `rendered`-is-terminal message removed; `kept`/`replaced` lines; `_format_line` takes many formats; success screen loops |
| `tests/test_video_render_cmd.py` | 26 new tests; `test_rendered_is_terminal` replaced; the two vacuous flag assertions repaired |
| `tests/test_video_status.py` | the `rendered` terminal test replaced; the exact-table pin updated |
| `tests/test_video_format.py` | the monkeypatched `render_episode` returns a `RenderRun` |
| `docs/…/specs/2026-08-15-…-video-mvp-design.md` | §9 and §10 updated — the diagram, the terminal paragraph, and the CLI block |

**Commits:** `4d05291`, `dc8de82`, `cc17c96`, `61fd47d`.

---

## 6. Issues and concerns

### 6.1 The audit: every capability claim the CLI prints

The previous six overclaims were about **verdicts**. This one was about **what
the tool can do**, which is a different species and needs a different method: a
verdict claim is checked by re-deriving the verdict, a capability claim is
checked by *running the thing it promises*. So the audit enumerated every
`agsoc …` command named inside a printed string (25 of them, read off the AST of
`cli.py`, `console.py`, `render.py`, `approve.py`, `verify.py`, `coverage.py`,
`plan.py`, `series.py`, `episode.py`) and every printed sentence containing
`every`, `always`, `never`, `cannot`, `is the only`, `nothing`.

Every command a screen names exists. The claims that survive scrutiny:
`console`'s "it writes nothing and it cannot approve" (D-129 pinned it),
`probe`'s "nothing moved", `--restart`'s "a partial render is discarded, not
resumed", `judge`'s "it makes no judgement". The `render` screen's
"one approval renders every format" is now true, and
`test_the_success_screens_promise_is_executable` **reads the claim off the screen
and then performs it**, which is the only version of that assertion the defect
would have failed.

### 6.2 The wide format cannot render a full episode — §9 is still not true end to end

Stated here as well as in §4.3 because it is the largest open item this task
found and it is **not** in this task's code: the wide render of the operator's
120 s episode degrades from ~168 frames/min to ~72 and then stalls past
Playwright's timeout, three times out of three, on an idle machine, while
vertical sustains ~225 frames/min for the same episode on the same machine. The
precise failure is `page.screenshot: Timeout 30000ms exceeded` in
`render.mjs::shoot`, at ~frame 708 of 3599, with the renderer's own ETA climbing
1390 → 1699 s beforehand. The CLI now permits every format §9 documents; the
engine can currently deliver the short ones. That belongs to whoever owns
Phase 10.

Two things would make it visible sooner if it is not fixed: `_run` keeps only six
lines of stderr, which hid `page.screenshot: Timeout` behind a bare
`TimeoutError`; and the renderer's per-150-frame ETA is the one signal that
predicted the failure and it never reaches the operator, because `_run` captures
stdout instead of streaming it.

### 6.3 The next overclaim, and it is worse than this one: `agsoc video preview`

**`preview` is an ungated second route to the exact file `render` gates.** D-119
retired `render.mjs --day` for being "a second way to render is a second way past
the gate". The Node-side route is gone; **the Python-side one is still here.**

Measured, on a throwaway workspace with the toolchain faked:

```
status before : draft
preview wrote : out/vertical-1080x1920.mp4
render's path : out/vertical-1080x1920.mp4
same file     : True
status after  : draft
```

A `draft` episode — never checked, never approved, no ledger — produced an MP4 at
the byte-identical path an approved render writes to, and the file an operator
uploads is indistinguishable from a gated one on disk. Its docstring says
"WITHOUT the gate. Changes no status", which is true and is not the problem: the
problem is the *path*. This is D-113 and D-059's shape, in the language the
retirement notice was written in.

It also collides with this task: a `preview` artifact now makes `render` report
"already rendered", which is a true statement about a file and a false
impression about an approval.

**Recommended, and deliberately not done here** (it is a decision, not a
follow-up): either retire `preview` the way `--day` was retired, or send it to a
path that cannot be confused with a deliverable — `probe/preview-<fmt>.mp4` —
and say on its screen that the file is not the episode's render. I did not fold
it into this task because it changes what an existing command does, and because
a change to the one remaining ungated MP4 route deserves its own tests rather
than a footnote in mine.

### 6.4 `coverage add` records one video, and an episode now has two

`coverage.episode_entry` writes `entry["video"] = render_record(episode)["file"]`,
and `render` is the most recent attempt — so after `render <ep>` the series
ledger names the **wide** file while the vertical cut is the one normally posted.
Nothing on screen claims otherwise (the `video` field is not printed), so this is
a data-accuracy issue rather than a seventh overclaim, but it is new as of this
task and it will read wrong to whoever opens `coverage.json` next. The clean fix
is for the entry to record every artifact or none.

### 6.5 `probe` ignores `[formats] enabled`

`agsoc video probe <ep> --format wide` draws frames for a format `render` will
refuse if the series has not enabled it. That is arguably correct — probing is
ungated on purpose (D-120), and looking at a format before enabling it is a
reasonable thing to want — but the two commands now answer differently about the
same word, and nothing says so.

### 6.6 A failed second format costs the episode its `rendered` status

If the wide cut fails after the vertical one succeeded, the episode is `failed`
even though a good MP4 is on disk, and `coverage add` (which requires `rendered`)
refuses until the operator retries. The retry is cheap — it skips the format that
already exists — and "the last thing this episode did was fail" is the honest
reading, but it is a behaviour change worth knowing about. `test_that_failure_recovers_without_re_rendering_the_first_format`
pins the recovery.

### 6.7 `agsoc init` is the one command that ignores `$AGSOC_WORKSPACE`

Found the hard way, by running it: `init` takes a positional `path` defaulting to
`Path("workspace")` and never consults `Workspace.locate()`. So an operator with
`AGSOC_WORKSPACE` set scaffolds one workspace and then addresses a **different**
one with every other command in the tool, and nothing says so.

**Disclosure:** that is how I ran a write-capable command against the operator's
`workspace/` — `agsoc init` with `AGSOC_WORKSPACE` exported to a scratch path.
`Workspace.init` is idempotent (`mkdir(exist_ok=True)`, and it writes `voice.md`
and `config.toml` only if absent), both files were already there, and I verified
afterwards: `voice.md` and `config.toml` still dated 14 July, the episode still
`rendered`, the MP4 still
`eff44093eb5c7fbe33666b71a20eeaeeae6184fbda935687cff5b483cf762e1c`. Nothing was
written. It should still not have been possible to do by accident, and the reason
it was is a genuine inconsistency in the CLI.

### 6.8 The spec was edited

§9 and §10 both asserted things that are no longer true (`rendered   (terminal in
MVP)` in the diagram, "**`rendered` is terminal for the MVP**" in the prose).
Leaving them would have been the overclaim pattern in the spec instead of the
CLI. The D-006 paragraph is kept in full and its cut is restated as still in
force; what is added is the sentence that was missing — that `rendered` having
no outgoing edge at all was that cut's *consequence*.
