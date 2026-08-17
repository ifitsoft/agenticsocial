# Task 0 Report — carried debt: the text pipeline's gate, and two Chromium-capable tests

**Branch:** `feat/video-phase-02-ingest`
**Commits:** `6a1ea3f` (tests, RED) · `ed9d8a6` (implementation, GREEN)

## 1. What I changed

- `src/agenticsocial/workspace.py::set_status` — the transition gate now reads the
  status from disk (`frontmatter.parse(v.path.read_text())`) instead of trusting
  `v.status`, with an invalid-status guard that raises `WorkspaceError`. Only the
  status comes from disk; `v.meta` is written as-is, so `publish_variant`'s
  in-memory `posted_url` / `posted_ids` still reach the file. Exactly the shape of
  `video/episode.py::set_status` (D-045).
- `tests/test_workspace.py` — three appended tests (disk gate, meta preservation,
  invalid disk status).
- `tests/test_video_render.py` — added the `fake` fixture to the signature of
  `test_missing_node_is_a_clean_error` and `test_missing_ffmpeg_is_a_clean_error`.
  Nothing else in either test changed.

No other existing test was touched. No dependencies added.

## 2. TDD evidence

RED (`uv run pytest tests/test_workspace.py tests/test_video_render.py`, tail):

```
FAILED tests/test_workspace.py::test_set_status_gates_on_disk_not_the_in_memory_variant - Failed: DID NOT RAISE TransitionError
FAILED tests/test_workspace.py::test_set_status_rejects_an_unreadable_status_on_disk - Failed: DID NOT RAISE WorkspaceError
========================= 2 failed, 34 passed in 0.66s =========================
```

`test_set_status_preserves_in_memory_meta` passed pre-fix by design — it is the
guard against the hazard, not a driver of it. Its killing mutant is mutant 2.

GREEN, full suite after the fix:

```
============================= 375 passed in 1.45s ==============================
```

Final re-run at the end of the task: `375 passed in 1.19s`.

## 3. Mutation results

| # | Mutant | Suite result | Failing tests |
|---|--------|--------------|---------------|
| 1 | `assert_transition(v.status, target)` (gate on memory again) | 1 failed, 374 passed in 1.57s | `test_set_status_gates_on_disk_not_the_in_memory_variant` — DID NOT RAISE TransitionError |
| 2 | also `v.meta = disk_meta` | 3 failed, 372 passed in 0.99s | `test_set_status_preserves_in_memory_meta`, `test_publish.py::test_publish_posts_thread_with_reply_chain`, `test_cli.py::test_post_publishes_and_prints_url` — all `posted_url is None` |
| 3 | drop the invalid-status guard (`current = Status(raw)` bare) | 1 failed, 374 passed in 1.17s | `test_set_status_rejects_an_unreadable_status_on_disk` — raw `ValueError: 'banana' is not a valid Status` |
| 4 | `_require_tools` returns immediately | 3 failed, 372 passed in **1.20s** | `test_missing_node_is_a_clean_error`, `test_missing_ffmpeg_is_a_clean_error` (both `Failed: DID NOT RAISE RenderError`), plus `test_missing_ffmpeg_is_detected_before_rendering_frames` (AttributeError from its own `lambda` stub — also never reaches a real subprocess) |

Mutant 4 detail: the two Step-1b tests alone ran in **0.28s** and failed on the
assertion. No Chromium, no ffmpeg, no hang — Step 1b works. Full suite under
mutant 4 stayed at 1.20s, i.e. unchanged from baseline.

Every mutant was reverted with `git checkout --` immediately after its run;
`git status --porcelain -- src tests` is empty.

## 4. Files changed

- `src/agenticsocial/workspace.py` (commit `ed9d8a6`)
- `tests/test_workspace.py`, `tests/test_video_render.py` (commit `6a1ea3f`)

## 5. Vacuity audit

Each new/changed test has a dedicated mutant that kills it, and none of them is
killed only by an unrelated mutant:

| Test | Its mutant | Killed? |
|---|---|---|
| `test_set_status_gates_on_disk_not_the_in_memory_variant` | mutant 1 | yes (and RED before the fix) |
| `test_set_status_preserves_in_memory_meta` | mutant 2 | yes |
| `test_set_status_rejects_an_unreadable_status_on_disk` | mutant 3 | yes (and RED before the fix) |
| `test_missing_node_is_a_clean_error` + `..._ffmpeg_...` (Step 1b) | mutant 4 | yes — they fail on the assertion in 0.28s |

No test passes vacuously: mutants 1 and 3 each fail exactly one test, so neither
new assertion is a duplicate of an existing one, and mutant 2 shows
`test_set_status_preserves_in_memory_meta` is load-bearing rather than a
tautology (it fails alongside the two real publish tests it stands in for).

I found no defect in this brief's code blocks: they are internally consistent
and consistent with the prose. Two cosmetic notes, no action taken (code blocks
are authoritative and were followed verbatim): the three appended tests re-import
`pytest`, `Status`, `Workspace` and `WorkspaceError` locally although
`tests/test_workspace.py` already imports all four at module level; and the new
`WorkspaceError` is raised inside `except ValueError` without `from None`, so the
traceback chains — which matches the existing style in `load_variant` and
`episode.load_episode`.

## 6. Issues and concerns

### 6a. Is the resume path still correct with the gate reading disk?

Yes. Trace of `publish_variant`, tweets `t1..tn`:

1. `set_status(PUBLISHING)` — disk gate sees `approved` (or `failed` on resume);
   writes `status: publishing`.
2. For each tweet: post, append to `posted`, `save_variant`. **`save_variant`
   writes `v.status`, which is still `PUBLISHING`** — so disk stays `publishing`
   for the whole loop. The disk gate therefore observes the same value the old
   in-memory gate did.
3. Death anywhere in the loop leaves disk = `status: publishing` +
   `posted_ids: [...k]`.
4. Resume: `cli.py::post` loads fresh, sees `PUBLISHING`, demands `--resume`,
   and skips its pre-check (`v.status is not Status.PUBLISHING` is false).
   `publish_variant` likewise skips step 1, slices `tweets[k:]`, and finishes
   with `set_status(PUBLISHED)` — disk says `publishing`, so `publishing →
   published` passes. No double post, no spurious gate failure.
5. Death between the last `save_variant` and the final `set_status` is the same
   case with `k == n`: the slice is empty, nothing is reposted, and the final
   transition still passes.

The hazard the brief flagged is real and is what mutant 2 demonstrates: had the
gate replaced `v.meta` with the disk copy, `posted_url` (set in memory one line
earlier) would be dropped and `agsoc post` would print `published: None` while
the thread was live.

One pre-existing window, not introduced here and not in scope: `post_tweet`
returns *before* `save_variant` runs, so a crash in that gap loses one id and a
resume reposts that single tweet. Save-after-each-post bounds the damage to one
tweet, which is the invariant's intent.

### 6b. Anywhere else that gates on in-memory state while writing to disk?

Yes — I found a fourth, and it is not closed by this fix.

**`x/publish.py:45` (mirrored at `cli.py:207`):**

```python
if variant.status is not Status.PUBLISHING:
    ws.set_status(variant, Status.PUBLISHING)  # gate
```

The decision *whether to run the gate at all* is made on the in-memory status.
A caller holding a `Variant` whose in-memory status is `PUBLISHING` while the
file says `draft` skips the gate entirely, posts every tweet to X, and the
loop's `save_variant` then stamps `status: publishing` onto the draft file — so
the closing `set_status(PUBLISHED)` also passes. My disk gate cannot help,
because it is never called. This is the same family (in-memory predicate,
disk-visible effect) and it guards the same thing D-049 guards: posting to X.
Like D-049 it is unreachable through today's CLI, because `cli.py` loads fresh
per invocation — but that is exactly the argument that was made for the video
gate before a reviewer broke it.

**Related, and arguably the root cause: `Workspace.save_variant` is an ungated
status writer.** It does `v.meta["status"] = v.status.value` and writes,
consulting no transition table and no disk state. Any caller can move a variant
to any status through it. `publish_variant` uses it legitimately (status
unchanged inside the loop), but it is the escape hatch through which the whole
`ALLOWED_TRANSITIONS` invariant can be bypassed in one line. `video/episode.py`
has no such counterpart — there is exactly one writer of episode status, and it
is gated. Worth considering: make `save_variant` write only the body and
non-status metadata, and let `set_status` own the `status` key.

Other places I checked and cleared:

- `video/plan.py::_load_script` re-reads `script.yaml` from disk for both the
  hash and the beats — one read, so the digest and content cannot disagree.
- `video/render.py::preview` writes no status at all (deliberate, per its
  docstring), so it has no gate to bypass.
- `video/cli.py::list` loads each episode from disk per id.
- `cli.py` status reads (lines 101–145, 202) are display or pre-checks over
  freshly loaded variants; the authoritative gate now sits in `set_status`.

Separate family, noted in passing: `create_source` and `create_variant` check
`path.exists()` and then write, where `create_episode` deliberately uses
`mkdir()` as an atomic claim. `create_variant` in particular would silently
overwrite a concurrently created variant. Low risk for a single-operator local
tool; flagging it rather than fixing it, since it is outside this task.
