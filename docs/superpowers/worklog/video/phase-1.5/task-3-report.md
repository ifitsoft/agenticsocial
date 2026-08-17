# Task 3 Report: `agsoc video preview`

**Branch:** `feat/video-phase-1.5-vertical-slice`

| Commit | Subject |
|---|---|
| `fe91ea2` | build: pin playwright exactly so renders are reproducible |
| `db61487` | test: specify agsoc video preview and its subprocess error surface |
| `803845b` | feat: add agsoc video preview |

Full suite after Step 4: **372 passed in 0.99s**. No test invokes Playwright or
ffmpeg.

---

## 1. What I implemented

**Step 0 — pinned Chromium.** `engine/package.json` now declares
`"playwright": "1.62.1"` exactly; `npm install --package-lock-only` propagated it
to `package-lock.json` (`"playwright": "1.62.1"` at line 12). Added the
**Reproducibility** section to `engine/README.md`, placed after the render
workflow and before Pacing. `node determinism.test.mjs` green on the pinned
version:

```
  ok   day path t=3.7  a9fc6922636a a9fc6922636a
  ok   day path t=3.7  chrome text stable from every predecessor
  ok   day path t=42.9  7494bbeaa15d 7494bbeaa15d
  ok   day path t=42.9  chrome text stable from every predecessor
deterministic
```

**Step 3/4 — the command.** New `src/agenticsocial/video/render.py`
(`RenderError`, `ENGINE_DIR`, `TOOLS`, `_require_tools`, `_run`, `preview`) and
a `video preview` command in `src/agenticsocial/video/cli.py`. Implemented as
the brief's code block specifies, with three deviations, all flagged below.

### Deviation 1 — `import json` moved to module scope

The brief's code block puts `import json` in the middle of `preview()`.
Behaviourally identical; moved to the top with the other imports.

### Deviation 2 (a real brief defect) — `--probe` and `--out`

**The brief's test and the brief's implementation contradict each other, and the
prose is a third story.** Concretely:

- Prose: "`--probe` stops after one frame per beat, leaving PNGs in `out/probe/`".
- Implementation block: invokes `node render.mjs --plan <p> --probe` with **no
  `--out`**, then returns `episode.out_dir / "probe"`.
- `engine/render.mjs` (which the brief describes second-hand) ignores `outDir`
  in probe mode entirely — `const dir = join(HERE, 'probe')`. So probe frames go
  to `engine/probe`, and the returned path is a directory that is never created.
- The test block's `FakeRun` does `cmd.index("--out")` on **every** `node` call,
  so the brief's own implementation cannot pass the brief's own test.

Observed as a hard failure on the first GREEN attempt:

```
FAILED tests/test_video_render.py::test_probe_stops_before_ffmpeg
  - ValueError: '--out' is not in list
1 failed, 371 passed in 1.08s
```

Resolution — the only one that satisfies the test, the returned path and the
prose simultaneously: `preview` passes `--out <episode.out_dir/probe>` in probe
mode, and `render.mjs` honours `outDir` in probe mode
(`const dir = outDir || join(HERE, 'probe')`). This does not touch `window.__seek`,
and `node determinism.test.mjs` was re-run green afterwards. It also fixes a real
bug the brief did not mention: with probes written unconditionally to
`engine/probe`, probing two episodes in a row silently overwrote the first one's
frames.

### Deviation 3 — the brief's Step 5 ffprobe command is wrong

```
ffprobe -v error -show_entries format=duration,tags=comment -of default=nw=1 <mp4>
```

`-show_entries` treats `tags=comment` as a second *section* selector, not a
sub-selector of `format`, so it silently prints only `duration=` and **no
comment tag** — which reads exactly like the metadata failing to land. It did
land. The correct form is `format=duration:format_tags=comment`. Both outputs
are pasted in §3.

---

## 2. TDD evidence

### RED (piped to `/tmp/step2-red.txt`, `/tmp/step2-red-cli.txt`)

`tests/test_video_render.py` — collection error, the module does not exist:

```
collected 29 items / 1 error
tests/test_video_render.py:6: in <module>
    from agenticsocial.video import render as R
E   ImportError: cannot import name 'render' from 'agenticsocial.video'
ERROR tests/test_video_render.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.13s
```

`tests/test_video_cli.py` alone (so the collection error does not mask it) —
the two new tests fail, the 27 existing ones still pass:

```
E       ModuleNotFoundError: No module named 'agenticsocial.video.render'
tests/test_video_cli.py:311: ModuleNotFoundError
FAILED tests/test_video_cli.py::test_video_preview_reports_the_output_path
FAILED tests/test_video_cli.py::test_video_preview_render_failure_is_a_clean_error
2 failed, 27 passed in 0.46s
```

### GREEN

First attempt: `1 failed, 371 passed in 1.08s` (the `--probe`/`--out` defect
above). After the fix, and again as the final state of the branch:

```
============================= 372 passed in 0.99s ==============================
```

---

## 3. Step 5 — the real end-to-end run

Real Playwright, real ffmpeg, no stubs.

```
$ rm -rf /tmp/t3 && export AGSOC_WORKSPACE=/tmp/t3/workspace
$ uv run agsoc init /tmp/t3/workspace
workspace ready at /tmp/t3/workspace/
next: edit voice.md (your voice profile) and config.toml (X client_id)

$ uv run agsoc series new the-brief --name "The Brief"
created series the-brief at /tmp/t3/workspace/series/the-brief/
next: edit /tmp/t3/workspace/series/the-brief/series.toml (palette, byline, acts, runtime)

$ uv run agsoc video new 2026-08-14 --series the-brief
created episode the-brief/2026-08-14 at /tmp/t3/workspace/series/the-brief/episodes/2026-08-14/
next: agsoc video ingest 2026-08-14 --research "<query>"

$ cat > .../2026-08-14/script.yaml <<'YAML'   # the brief's two-beat script
$ shasum -a 256 .../2026-08-14/script.yaml
cc0f42d9b61c6d30ea8352965673296ef6d7431d8dc75d671418d8710bbcf3d6  .../script.yaml

$ time uv run agsoc video preview 2026-08-14 --series the-brief
wrote /tmp/t3/workspace/series/the-brief/episodes/2026-08-14/out/vertical-1080x1920.mp4
uv run agsoc video preview 2026-08-14 --series the-brief  66.07s user 3.59s system 147% cpu 47.071 total

$ ffprobe -v error -show_entries format=duration,tags=comment -of default=nw=1 <mp4>   # the brief's command
duration=6.000000

$ ffprobe -v error -show_entries format=duration:format_tags=comment,title -of default=nw=1 <mp4>   # corrected
duration=6.000000
TAG:title=The Brief — 2026-08-14
TAG:comment=script_sha256=cc0f42d9b61c6d30ea8352965673296ef6d7431d8dc75d671418d8710bbcf3d6

$ ls -la .../2026-08-14/out/
total 1640
drwxr-xr-x@ 4 aabdukarim  wheel     128 Aug 17 11:51 .
drwxr-xr-x@ 6 aabdukarim  wheel     192 Aug 17 11:51 ..
-rw-------@ 1 aabdukarim  wheel    1110 Aug 17 11:51 plan-vertical.json
-rw-r--r--@ 1 aabdukarim  wheel  832204 Aug 17 11:51 vertical-1080x1920.mp4

$ find .../2026-08-14 -name '.frames' -o -name '*.png'
   (no output — no .frames directory and no PNG survives)

$ head -5 .../2026-08-14/script.yaml     # status untouched by preview
---
episode: '2026-08-14'
series: the-brief
status: draft
pace: 1.0
```

The `comment` tag carries `cc0f42d9…f3d6`, byte-identical to `shasum -a 256` of
`script.yaml` on disk. Duration 6.000000s = two beats × 3.0s hold at pace 1.0.

Real `--probe` run, verifying Deviation 2:

```
$ time uv run agsoc video preview 2026-08-14 --series the-brief --probe
wrote /tmp/t3/workspace/series/the-brief/episodes/2026-08-14/out/probe
... 1.36s user 0.19s system 104% cpu 1.478 total

$ ls -la .../out/probe/
-rw-r--r--@ 1 aabdukarim  wheel  709244 Aug 17 11:52 s00.png
-rw-r--r--@ 1 aabdukarim  wheel  673683 Aug 17 11:52 s01.png
```

`engine/probe/` still holds its own unrelated frames — the episode probe no
longer stamps on it.

---

## 4. Files changed

| File | Commit |
|---|---|
| `engine/package.json`, `engine/package-lock.json`, `engine/README.md` | `fe91ea2` |
| `tests/test_video_render.py` (new), `tests/test_video_cli.py` (+2 tests) | `db61487` |
| `src/agenticsocial/video/render.py` (new), `src/agenticsocial/video/cli.py`, `engine/render.mjs` | `803845b` |

Nothing under `docs/` was staged.

---

## 5. Vacuity audit

Every test was audited by writing the mutant it claims to kill, applying it to
the real source, and running that test. 17 mutant/test pairs; every one is
listed with its observed verdict.

| Mutant | Test | Verdict |
|---|---|---|
| M1 ffmpeg exe renamed to `true` | `test_preview_writes_the_mp4_into_out` | **SURVIVED** — see below |
| M1 | `test_ffmpeg_receives_the_plans_fps_and_the_frames` | KILLED |
| M1 | `test_the_mp4_records_the_script_hash` | KILLED |
| M1 | `test_ffmpeg_failure_surfaces_its_stderr` | KILLED |
| M2 plan file deleted after writing | `test_preview_emits_the_plan_first` | KILLED |
| M3 `--plan` renamed to `-p` | `test_node_is_invoked_with_the_plan_and_an_out_dir` | KILLED |
| M4 fps hard-coded to 25 | `test_ffmpeg_receives_the_plans_fps_and_the_frames` | KILLED |
| M5 comment metadata → a constant string | `test_the_mp4_records_the_script_hash` | KILLED |
| M6 `finally: rmtree` removed | `test_frames_are_cleaned_up` | KILLED |
| M7 `if probe:` → `if False:` | `test_probe_stops_before_ffmpeg` | KILLED |
| M8 tool error message loses the tool name | `test_missing_node_is_a_clean_error` | KILLED |
| M8 | `test_missing_ffmpeg_is_a_clean_error` | KILLED |
| M9 `_require_tools()` call removed | `test_missing_ffmpeg_is_detected_before_rendering_frames` | KILLED |
| M10 "no frames" check → `if False:` | `test_no_frames_produced_is_a_clean_error` | KILLED |
| M11 `write_plan` moved after the node run | `test_an_invalid_script_fails_before_any_subprocess` | KILLED |
| M12 `preview` rewrites `status: draft` → `approved` | `test_preview_does_not_rewrite_the_script` | KILLED |
| M12 | `test_preview_does_not_change_the_episode_status` | KILLED |
| M13 stderr tail dropped from `RenderError` | `test_node_failure_surfaces_its_stderr` | KILLED |
| M13 | `test_ffmpeg_failure_surfaces_its_stderr` | KILLED |
| M14 ffmpeg `_run` never executed at all | `test_preview_writes_the_mp4_into_out` | KILLED |
| M15 CLI echoes a constant, not the path | `test_video_preview_reports_the_output_path` | KILLED |
| M16 CLI does not catch `RenderError` | `test_video_preview_render_failure_is_a_clean_error` | KILLED |
| M17 CLI replaces the message with "preview failed" | `test_video_preview_render_failure_is_a_clean_error` | KILLED |

### The one survivor, and what it means

`test_preview_writes_the_mp4_into_out` survived M1. The cause is the stub, not
the test: `FakeRun`'s `else` branch fabricates `Path(cmd[-1])` for **any**
non-`node` command, so renaming the encoder still produced the file. Against
M14 — the true "the code does nothing" mutant, where the ffmpeg `_run` is not
executed at all — the test is **KILLED**. So it is not vacuous; it is merely
blind to *which* binary encodes, which the two dedicated ffmpeg tests
(`-framerate`, `%05d.png`, `script_sha256=`) cover. I am recording it rather
than hardening it: adding an exe assertion here would duplicate those.

### A latent hazard the audit exposed

`test_missing_node_is_a_clean_error` and `test_missing_ffmpeg_is_a_clean_error`
patch `shutil.which` but **not** `subprocess.run`. They pass today only because
`_require_tools` raises before any subprocess starts. If that check were ever
removed, those two tests would not merely fail — they would **launch real
Chromium and real ffmpeg**, violating the "no test invokes Playwright or ffmpeg"
rule and turning a 1-second suite into a multi-minute one. (This is why M9 was
aimed at `test_missing_ffmpeg_is_detected_before_rendering_frames`, which does
stub `subprocess.run`, instead.) Cheap fix for a later task: give those two
tests the `fake` fixture as well, so the stub is the safety net rather than the
production code.

---

## 6. Issues and concerns

### `ENGINE_DIR` and `parents[3]` — your suspicion is right, and it is worse

Verified, not guessed. `pyproject.toml` has
`[tool.hatch.build.targets.wheel] packages = ["src/agenticsocial"]`, so
`engine/` **is not in the wheel at all**:

```
$ uv build --wheel -o /tmp/wh
Successfully built /tmp/wh/agenticsocial-0.1.0-py3-none-any.whl
$ unzip -l /tmp/wh/*.whl | grep -iE 'engine|render'
     3648  agenticsocial/video/render.py        # <- the only hit; no engine/ anywhere
```

Installed into a clean venv, `parents[3]` climbs out of `site-packages` and
lands on a path with no meaning:

```
$ /tmp/venv3/bin/python -c "import agenticsocial.video.render as R; print(R.ENGINE_DIR, R.ENGINE_DIR.exists())"
/private/tmp/venv3/lib/python3.11/engine False

$ /tmp/venv3/bin/agsoc video preview 2026-08-14 --series the-brief
could not start the renderer: [Errno 2] No such file or directory: PosixPath('/private/tmp/venv3/lib/python3.11/engine')
```

It is at least a clean error, not a traceback (`cwd=` raising `OSError` is caught
by `_run`), but the message points at a directory the operator has never heard
of and does not say "the render engine is not installed".

**What it should be — three parts, not one:**

1. **Ship the engine inside the package.** Move `engine/` to
   `src/agenticsocial/engine/` (or `force-include` it in the hatch wheel
   target). Until it is in the wheel, no path expression can be correct —
   `parents[N]` for any `N` is fixing the arithmetic on a directory that does
   not exist.
2. **Anchor to the package, never to a parent count:**
   `ENGINE_DIR = Path(importlib.resources.files("agenticsocial")) / "engine"` —
   or at minimum `Path(__file__).resolve().parent.parent / "engine"` once the
   engine lives under the package. A parent count encodes the repo's directory
   depth in an unrelated module and breaks silently the moment either the repo
   layout or the install mode changes; `importlib.resources` is exactly the API
   for "a file that travels with this package".
3. **Add an `$AGSOC_ENGINE` override and a fail-fast check.** Operators running
   a checked-out engine against an installed `agsoc` need the override, and
   `preview` should verify `ENGINE_DIR / "render.mjs"` is a file *inside*
   `_require_tools`, raising a `RenderError` that names the path and the env
   var. That converts a cryptic errno into an actionable one, and — matching
   the brief's own "check the toolchain up front" argument — does it before any
   frame is rendered.

I have **not** made this change: it moves a tracked Node subproject and edits
packaging config, which is outside a task scoped to wiring `preview` together.
It should be its own task, and I would put it before Phase 8 ships `render`.

### Operator input that still produces a traceback

None found. Swept the reachable failure modes through the real CLI; zero
occurrences of `Traceback` (`grep -c Traceback` → `0`):

| Input | Output | |
|---|---|---|
| `preview nope` | `no episode 'nope' in the-brief — create it with …` | clean |
| `preview … --series nope` | `no series 'nope' — create it with …` | clean |
| `preview ../../escape` | `unsafe episode id '../../escape' — must be a single directory name` | clean |
| `out/` chmod 500 | `cannot write output: [Errno 13] Permission denied: …tmp` | clean |
| `out/plan-vertical.json` is a directory | `cannot write output: [Errno 21] Is a directory: …` | clean |
| beat `type: jumpChart` | `beat 0 has unsupported type 'jumpChart' — this phase renders: statement` | clean |
| `beats: []` | `no beats to render` | clean |
| engine missing (pip install) | `could not start the renderer: [Errno 2] …` | clean, but cryptic |

Three residual notes rather than tracebacks:

- **The two `cannot write output:` messages leak a tempfile name** from inside
  `atomic_write` (`…/out/tmppq1ra_i3.tmp`). Correct behaviour, confusing text —
  the operator did not create that file and cannot find it afterwards.
- **`preview()` is not a total function over `RenderError`.** `write_plan` and
  `plan_path.read_text` can raise `OSError`, and `preview`'s contract does not
  wrap it. The CLI catches `OSError` separately so the operator is fine, but any
  future caller (Phase 8's `render`, a skill) must remember to catch both.
- **Interrupting a render is safe.** Ctrl-C during the 47-second run unwinds
  through the `finally`, so no multi-GB `.frames` directory is left behind.
  Click converts `KeyboardInterrupt` to `Aborted!` — no traceback.

### Is `preview` the right name?

Yes for now, with one condition attached.

The reasoning in the brief holds and I would not weaken it: shipping a
gate-bypassing command under the name the gated command will take is how a gate
stops meaning anything. `preview` is also honest about what an operator gets
today — an artifact with no approval behind it.

The drift risk is real but small and manageable, because the split is not
symmetric. Phase 8's `render` is `preview` plus a status transition:

```
assert_transition(current, RENDERING)  →  preview(...)  →  set_status(RENDERED)
```

Everything that could drift — the ffmpeg flags, the frame cleanup, the sha256
metadata, the toolchain check — lives in the one `preview()` function both
commands call. Drift only becomes likely if Phase 8 copies the body instead of
calling it.

Two things worth pinning now so that stays true:

1. Phase 8 must implement `render` as a **wrapper** over `preview`, and there
   should be a test asserting the two produce the same ffmpeg argv.
2. `preview`'s help text should keep saying it does not change status, and
   `render`'s should say it does. If the two ever both claim to "render an
   episode", the operator has no way to tell which one they want — and that
   ambiguity, not code duplication, is the way this split actually goes wrong.

One smaller naming point: `preview` collides conceptually with `--probe`, which
is *also* a preview (and with `scene.html`'s slider, which the engine README
calls "preview without rendering"). Three things named preview-ish is one too
many. If a rename is ever on the table I would suggest `--probe` become
`--frames` or `--sample`, not that `preview` change.
