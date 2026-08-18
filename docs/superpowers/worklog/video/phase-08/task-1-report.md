# Task 1 Report: `agsoc video render`

**Phase:** 8 · **Branch:** `feat/video-phase-08-render` · **Spec:** §6, §9, §10

> **This report is reconstructed after the fact, by a different implementer.**
> The machine that built `render` slept before it could write this file. The six
> commits, the tests and the working tree survived intact; the narrative did not.
> Everything below is read off those commits, off the code as it stands, and off
> checks I ran myself today. **Section 8 lists what I could not reconstruct and
> what I chose to re-measure rather than assert.** The leader's own end-to-end
> verification is recorded in D-117 and is quoted where it is the evidence.

---

## 1. Resume versus restart: **partial renders are discarded**

Argued in `286e5d0`, and I agree with it after reading the code.

The tweet analogue resumes. `publish_variant` saves `posted_ids` after every
single tweet because **each post is irreversible and already visible to
strangers** — a re-post is a second tweet in the world, not a retry. Frames have
neither property:

* `window.__seek(t)` makes frame *n* a pure function of *t*, so re-rendering it
  produces the same bytes. There is nothing in a partial render that cannot be
  recreated.
* Nobody has seen them. They are intermediates in a temp directory.
* They are ~2.5 GB per episode. Keeping them to save minutes of a process that
  is already minutes long trades disk for very little.

So the invariant that carries over is **not** "nothing is lost" — it is the other
half, the one that actually matters: **the episode is never left in a status no
supported command can leave.**

That is implemented in two pieces, because there are two ways a render ends
early:

| how it ends | what happens |
|---|---|
| the renderer fails, ffmpeg fails, a beat throws, **Ctrl-C** | `except BaseException` → `rendering → failed`, with the reason recorded; §10's `failed → rendering` is the retry, and it asks all three questions again |
| **SIGKILL, power loss** — no handler runs | `rendering` is left on disk with no live process. `--restart` is the door: `rendering → failed`, then the normal path |

`except BaseException`, not `except Exception`, is load-bearing: Ctrl-C is the
likeliest way a fourteen-minute render ends early, and `except Exception` would
leave exactly the stuck `rendering` the whole section exists to prevent.

`--restart` takes a flag rather than being automatic because **`rendering` on
disk is indistinguishable from a render running in another terminal.** A status
that can only be escaped by hand-editing a file is a bug; a render that silently
steals another one's episode is a worse one. It answers the *status* question
only — drift and staleness are still asked, and a test pins that.

## 2. Where the MP4 goes

`<workspace>/series/<slug>/episodes/<id>/out/<format>-<w>x<h>.mp4` — for the
verification episode:

```
…/episodes/2026-08-18/out/vertical-1080x1920.mp4
```

* **Not `engine/`** (R4). That directory is a gitignored working area; a
  deliverable there is a file nobody finds and nobody cleans up.
* **Beside the episode that produced it.** An operator reading the episode a
  month later finds the video without knowing which terminal made it.
* **Named for the format, not the date**, because the date is the episode
  directory. A second format lands beside it rather than overwriting it.
* **The frames do not go here.** ~2.5 GB per episode goes to
  `tempfile.mkdtemp()` and is deleted after the encode (`d2d02b1`) — spec §5 says
  never inside `workspace/`, and a SIGKILL runs no `finally`, so the difference
  is whether the mess lands in the operator's content directory or in
  `/var/folders`.

**A stale MP4 on re-render** (the plan's open question) does not arise in the
MVP: `rendered` is terminal (D-006), so an episode renders once. The file is
overwritten only through `--restart` after a killed run, which by definition has
produced nothing. The record in `script.yaml` and the container's `comment` tag
both carry `script_file_sha256`, so a file that no longer matches its script can
be detected without trusting either one alone. **This is the weakest link in the
phase and it becomes real the moment `rendered` stops being terminal** — see §8.

**Does `render` re-run `check`? No**, and by argument rather than inheritance.
The ledger is the artifact of record and the screen a human read before signing.
A second set of verdicts computed inside `render` would be verdicts nobody
displayed, and a second producer of verdicts is the D-059 shape again. `render`
therefore *requires* a fresh ledger; it does not recompute one.

## 3. The success message

The screen as it shipped in `95d5cfe` is quoted in D-117. Here it is as it stands
at HEAD, from a real render today — the `scope` line's last sentence changed in
**Task 3**, because it used to point at `preview --probe`:

```
the-brief/2026-08-18 · rendered
      file     …/series/the-brief/episodes/2026-08-18/out/vertical-1080x1920.mp4
               0.9 MB · 6.0s · 1080x1920 · 180 frames @ 30fps
      approved Ali Abdukarim at 2026-08-18T13:19:14-05:00 — and nothing you authored has changed
               since: the beats, `pace` and series.toml's design are the ones that were signed
      scope    the approval does NOT cover what drew these frames — engine.js, planbuild.js,
               scene.html's CSS, the font this machine resolved, Chromium and ffmpeg are all outside
               the approval, and the font is the one that differs between machines. Nobody has
               looked at this video: `agsoc video probe 2026-08-18 --series the-brief` puts one
               frame per beat on disk in seconds
```

**Why it does not overclaim.** It says two true things and refuses a third:

1. *approved by a named human at a time* — established, all three checks passed.
2. *nothing you authored has changed* — established, and it enumerates what
   "authored" means so the operator does not have to guess: beats, `pace`,
   series.toml's design.
3. It never says "this is what the approver saw," because that is false. D-116
   measured the boundary: `engine.js`, `planbuild.js`, `scene.html`'s CSS, the
   resolved font, Chromium, ffmpeg. **A font substitution changes every frame
   with all three checks green.**

Then it says the thing that is easy to leave out: *nobody has looked at this
video* — and hands over the cheap way to look. That last clause is why Task 3
exists at all.

This project has overclaimed on a summary line four times (D-106, D-110, D-112,
D-113), always for the same reason: the summary is written last by someone who
already knows the answer. Two tests hold this one — one that the screen names
what is excluded, one that it does **not** say the frames were seen — plus a
third that it still says what *is* true, because refusing to overclaim by saying
nothing is its own defect.

## 4. TDD evidence

Six commits, tests first, none squashed:

| SHA | what |
|---|---|
| `dd663e3` | **test** — 691 lines, one test per mutant in the brief's table plus the pairs each needs. 33 of 39 failing; the six that passed were negative-invariant halves, vacuous until `render` existed |
| `2b5781f` | **feat** — the three-check gate and the status transitions. 9 tests still failing |
| `d2d02b1` | **feat** — the plan carries `total_frames`; frames move to a temp directory |
| `286e5d0` | **feat** — the crash path: `rendering → failed`, `--restart`, `except BaseException` |
| `edddbb9` | **test** — three mutants the first version of the file let through |
| `95d5cfe` | **fix** — `rendered` is terminal, so do not send that operator to `approve`; two label defects on the success screen |

`edddbb9` is the commit worth reading. It reports three survivors **as
survivors** before fixing them:

* **M4** — the three refusals collapsed into one framing survived the
  distinctness check, because the `why` lines come from `approval_drift` and
  `stale_reason` and were always going to differ. What collapsed was the **fix**
  line, the half an operator acts on.
* **O9** — the recorded path is absolute survived an `endswith` assertion.
* **O12** — frames left behind survived, because moving them out of `workspace/`
  made the workspace-wide check blind to the leak it was written for.

### Mutation score

**I could not find evidence that the reported 26/26 sweep was ever run** — no
harness, no log, only the number in a commit message. So I ran my own rather than
repeat a figure I did not measure. `PYTHONDONTWRITEBYTECODE=1` throughout (D-100).

**First sweep — 26 mutants, all twelve from the brief plus my own: 23 killed, 3
survived.**

| # | mutant | result |
|---|---|---|
| M1a | the early `assert_transition` is gone (`set_status` still gates) | killed |
| M1b | the status gate is gone entirely, early and authoritative | killed |
| M2 | a drifted episode renders | killed |
| M3 | a stale corpus renders | killed |
| M4a | all three refusals print one screen | killed |
| **M4b** | **the whys differ but the fix lines collapse** | **SURVIVED** |
| M5 | the three checks folded into one predicate | killed |
| M6a | a renderer crash leaves the episode `rendering` | killed |
| M6b | Ctrl-C leaves the episode `rendering` | killed |
| M7 | `failed → rendering` removed from the table | killed |
| M8 | the final status written by a second, ungated writer | killed |
| M9a | node handed timing on the command line | killed |
| **M9b** | **`render.mjs` recomputes the frame count with its own FPS** | **SURVIVED** |
| **M9c** | **`render.mjs` accepts a plan with no frame count** | **SURVIVED** |
| M10 | the MP4 written into `engine/` | killed |
| M11a | the success screen says the approver saw these frames | killed |
| M11b | the success screen refuses to say what IS true | killed |
| M12 | the test fixture is a full-length episode | killed |
| O1 | the toolchain checked after the gate is spent | killed |
| O2 | an unsupported format refused after the status moved | killed |
| O3 | frames left on disk after the encode | killed |
| O4 | the render not recorded in `script.yaml` | killed |
| O5 | the recorded path is absolute | killed |
| O6 | the episode id matched by substring | killed |
| O7 | `--restart` skips drift and staleness | killed |
| O8 | a `rendered` episode is told to run `approve` | killed |

**The three survivors, and what they mean:**

* **M4b is the same defect `edddbb9` was written to fix, one layer down.** The
  strengthened test asserted `"put the change back" in screens["drift"]` — and
  that sentence is `approval_drift`'s own wording (`approve.py:276`). It arrives
  on the **why** line whatever the fix line says. So the test was reading the
  diagnosis and calling it the remedy, and the two remedies could be made
  identical with it green. Fixed in `1cb9788`: the two labelled `fix` blocks are
  now compared **to each other**, read off the rendered screen.
* **M9b and M9c are both a substring grep.** `test_the_renderer_takes_its_frame_
  count_from_the_plan` asserted `"plan.total_frames" in src` — and the string
  appeared in three places, so deleting the *use* of it left the assertion true.
  Both are closed by **Task 2**, which removes the `--day` fallback arithmetic
  entirely and pins its absence.

**Second sweep, at HEAD after Tasks 2 and 3 — 34 mutants (the 26 above with M9b/
M9c retargeted at the new source, plus M9d and seven probe mutants): 32 killed, 2
survived; both fixed in `14ba13e`, then 34/34.** Details in the Task 2 and Task 3
reports.

### Suite wall-clock

| | tests | wall clock |
|---|---|---|
| Task 1's file alone | 42 | 1.0s |
| suite without Phase 8's three new files | 1737 | 14.4s |
| full suite at HEAD | 1809 | 17.4s |

**No test renders a full episode** (R6). Every subprocess is faked and the
fixture script is seconds long — two tests pin that directly: one asserts the
fixture's resolved runtime is seconds, one greps every `test_*.py` for the shapes
that would bypass the fake (spawning the renderer, importing Playwright,
launching Chromium). The M12 mutant — a 300-second fixture — is killed.

## 5. Step 6: the four screens, run today

Against a throwaway workspace I created at
`…/jobs/9a014c11/tmp/ws8` (verified not to exist first). **`workspace/` was not
touched**; its three real episodes are unapproved, unedited and untouched by any
of this.

**1 — status.** `in_review`, exit 1:

```
the-brief/2026-08-18 · NOT rendered — cannot move in_review -> rendering; allowed next: draft,
approved. Only an episode a human has approved renders: `agsoc video approve 2026-08-18
--series the-brief --by "Your Name"`
```

**2 — drift.** Approved, then `series.toml`'s `accent` changed. Exit 1:

```
the-brief/2026-08-18 · NOT rendered — the approval no longer describes this episode
      why      series.toml has changed: [design] accent was '#2E6BFF', now '#FF0000' — approved by
               Ali Abdukarim at 2026-08-18T13:19:14-05:00. Re-run `agsoc video check` and approve
               again, or put the change back
      fix      put the change back, or run `agsoc video check 2026-08-18 --series the-brief` and
               approve again
```

**3 — ledger.** Accent restored, one line appended to the corpus. Exit 1:

```
the-brief/2026-08-18 · NOT rendered — the check does not describe this script
      why      the corpus has changed since this check was written — re-run it
      fix      run `agsoc video check 2026-08-18 --series the-brief`, read it, then approve
```

Three different headlines, three different `why` lines, three different remedies
pointing at three different files. That is D-115 arriving on a screen.

**4 — the render.** Corpus restored to its approved bytes (sha256 re-checked
against `_manifest.json`), exit 0, quoted in §3 above. **50.2s wall clock for a
6.0-second video**, 180 frames — ~230 ms/frame plus browser start and encode.

```
$ ffprobe -v error -select_streams v:0 -show_entries stream=… out/vertical-1080x1920.mp4
codec_name=h264
width=1080
height=1920
r_frame_rate=30/1
duration=6.000000
nb_frames=180
format_name=mov,mp4,m4a,3gp,3g2,mj2
size=921451
```

and `script.yaml` reads `status: rendered` with the full render record beside the
approval it acted on.

The leader's independent verification of the same four screens, on the code as
Task 1 shipped it, is in D-117: 36.9s for a 3.5s video, `nb_frames=105`,
`duration=3.500000`, `size=518230`.

## 6. Files changed

`1b8961a..95d5cfe`, six commits:

```
engine/render.mjs                   22 +-
src/agenticsocial/models.py          6 +
src/agenticsocial/video/cli.py     136 +-
src/agenticsocial/video/render.py  243 +-
tests/test_video_render_cmd.py     751 +
```

SHAs: `dd663e3`, `2b5781f`, `d2d02b1`, `286e5d0`, `edddbb9`, `95d5cfe`.
Follow-up from this report: `1cb9788` (M4b).

## 7. Issues and concerns

### What is the worst thing that can happen mid-render?

Separating what was **tested** from what was **reasoned about**, because the
brief asked and the distinction is the point:

| failure | tested? | how |
|---|---|---|
| the renderer exits non-zero | **tested** | fake subprocess returns 1 → `failed`, reason recorded |
| ffmpeg exits non-zero | **tested** | frames rendered, encode dies → `failed` |
| **Ctrl-C** | **tested** | `KeyboardInterrupt` raised from the fake → `failed`, and it propagates |
| node or ffmpeg missing | **tested** | `which` returns `None` → refused **before** the gate is spent |
| retry after failure | **tested** | `failed → rendering` works, and still asks all three questions |
| a render killed with SIGKILL | **partly** | the *recovery* is tested by forcing `rendering` onto disk and running `--restart`. The SIGKILL itself is not tested |
| **disk full** | **reasoned only** | the write raises `OSError` inside the `try`, so it lands in `failed` like any other exception. Not exercised |
| **a beat that throws at frame 3000** | **reasoned only** | `render.mjs` collects `pageerror` and exits non-zero, so it becomes "the renderer failed". **Nothing tests a beat that throws late** rather than at load, and the two are not obviously the same path |
| `_fail_episode` itself failing | **reasoned only** | swallowed, deliberately, so the original exception survives. A disk failing under the failure handler leaves `rendering` on disk — and `--restart` is the door out |

The honest summary: **every failure mode that the status machine has to survive
is tested; every failure mode that depends on the filesystem or on Chromium's
behaviour at frame 3000 is reasoned about.**

### What makes a render non-reproducible on a second machine

This is D-116's list, and it is not hypothetical:

1. **The resolved font.** `type_family` is a CSS font stack. A machine without
   SF Pro Display renders every frame in a different face — different metrics,
   different line breaks, different everything — with all three checks green.
   **This is the one that differs between machines by default.**
2. **Chromium.** Playwright is pinned to an exact version, not a caret range,
   because `filter: blur()` rasterises differently across builds. A different
   Chromium is different bytes.
3. **ffmpeg.** Build, version and flags are outside the approval. `libx264` at
   `-preset veryfast -crf 20` on a different build is a different file.
4. **`engine.js`, `planbuild.js`, `scene.html`'s CSS.** Tracked in git, so a
   change is visible — but not covered by the approval, so a change between
   approval and render is silent.

The mitigation is not to extend the approval — it cannot reach the pixels — but
to make looking at them cheap. That is Task 3, and it now takes 1.7 seconds.

### Two smaller things

* **`ENGINE_DIR = Path(__file__).resolve().parents[3] / "engine"` is still
  wrong outside a source checkout.** D-056 measured this in Phase 1.5, called it
  **required before Phase 8**, and it has not been done: `engine/` is not
  packaged, so an installed wheel resolves this to a directory that never
  existed. Task 2 did not need it, so I did not do it. **It is the largest
  known gap in the phase** and it means `render` works from the repo and from
  nowhere else.
* **`rendered` being terminal is what makes the stale-MP4 question moot.** When
  video publishing lands and `rendered → publishing` joins the table, "the file
  on disk no longer matches the script" becomes reachable, and
  `script_file_sha256` in the container comment is the only thing that would
  catch it. Nothing checks it today.

## 8. What I could not reconstruct

* **Whether a mutation sweep was actually run for Task 1.** `edddbb9` reports
  26/26 and names three survivors it fixed, which is the shape of a real sweep —
  but no harness, script or log survives. I did not repeat the number. I ran my
  own sweep, which found three survivors including one that the very commit
  claiming 26/26 was written to prevent, so **the 26/26 figure should be read as
  unverified**.
* **The wall-clock delta as Task 1 measured it.** `286e5d0` records "1776 tests,
  17.5s — 39 added, no measurable wall-clock cost". I have no pre-Task-1 timing
  on this machine, so §4 reports a proxy: the suite with Phase 8's new test files
  excluded.
* **Whether Step 6 was completed as written.** `95d5cfe` says "Found by running
  the real thing (step 6)" and fixes something only a real run would surface, so
  at least one real render happened. The four screens were never pasted anywhere
  before D-117; the leader's run is the record for the code as it shipped, and
  §5 is my own re-run at HEAD.
* **Anything the implementer decided and did not write down.** Where a commit
  message argues a decision I have quoted it; where it does not, I have said so
  rather than inventing the reasoning.
