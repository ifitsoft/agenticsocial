# Task 5 Brief: Path safety, and stop the two modules drifting

**Phase:** 1 · **Branch:** `feat/video-phase-01-scaffolding` · **Follows:** `8bd2cb3`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

This is the **last task before the phase gate.**

## Why

Leader-verified workspace escape:

```
$ agsoc video new 2026-08-14 --series ../../outside
created episode ../../outside/2026-08-14 …
*** ESCAPED WORKSPACE *** /private/tmp/t5c/outside/episodes/2026-08-14/script.yaml
```

`scaffold_series` calls `_validate_slug`. **`load_series` does not** — and
`video new --series` reaches `create_episode` through `load_series`. It is not a
crash, which is why 24 traceback probes missed it: it succeeds.

This is the third instance of one pattern (D-036): a guard added to one module or
one function and never checked in its sibling. `episode.py` has had three tasks
of attention; `series.py` gets each fix late or never.

## The distinction this task introduces

Two different questions have been conflated in one helper:

- **Naming rules** govern what agsoc will *create*. `_validate_slug` owns this:
  lowercase, digits, hyphens, length cap. Applies to `scaffold_series` only.
- **Path safety** governs what agsoc will *touch*. New. Applies to every function
  that turns a caller-supplied name into a path — `load_series`, `load_episode`,
  `resolve_episode`, and both creators.

Keeping them separate matters: a directory a human named `My-Show` is perfectly
loadable and must stay loadable, while `../../outside` must not be, regardless of
who created it. Folding path safety into `_validate_slug` would break the first
case to fix the second.

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it**.
- Do not add dependencies. Report observed counts.
- Never stage anything under `docs/`.
- **Authorised test change:** `test_over_long_name_fails_cleanly` in
  `tests/test_video_cli.py` currently passes via the `OSError` path, because
  `[Errno 63] File name too long` contains the literal `"too long"` — so the
  length cap is unpinned (Task 4b mutant 4 survived). Step 1b tightens it. Change
  only that assertion.

## Files

- Modify: `src/agenticsocial/video/series.py`
- Modify: `src/agenticsocial/video/episode.py`
- Modify: `tests/test_video_series.py`, `tests/test_video_episode.py`, `tests/test_video_cli.py`

---

- [ ] **Step 1a: Append path-safety tests**

To `tests/test_video_series.py`:

```python
# --- path safety: what agsoc will TOUCH, distinct from what it will CREATE -----

UNSAFE = ["../../outside", "..", ".", "", "a/b", "a\\b", "/abs", "sub/dir"]


@pytest.mark.parametrize("bad", UNSAFE)
def test_load_series_refuses_unsafe_names(ws, bad):
    """scaffold_series validated its slug; load_series did not, and
    `video new --series ../../outside` reaches create_episode through it."""
    with pytest.raises(SeriesError, match="unsafe"):
        load_series(ws, bad)


@pytest.mark.parametrize("bad", UNSAFE)
def test_scaffold_series_refuses_unsafe_names(ws, bad):
    with pytest.raises(SeriesError):
        scaffold_series(ws, bad)


def test_load_series_still_accepts_a_hand_made_directory_name(ws):
    """Path safety is not a naming rule. A directory a human called `My-Show`
    must stay loadable even though agsoc would not have created it."""
    d = ws.series_dir / "My-Show"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_text('[series]\nname = "Mine"\n', encoding="utf-8")
    assert load_series(ws, "My-Show").name == "Mine"


def test_scaffold_series_detects_a_dangling_symlink(ws):
    """create_episode checks is_symlink(); its sibling did not, so Path.exists()
    followed the link and mkdir reported [Errno 17] instead of a clean error."""
    ws.series_dir.mkdir(parents=True, exist_ok=True)
    (ws.series_dir / "ghost").symlink_to(ws.series_dir / "nowhere")
    with pytest.raises(SeriesError, match="already exists"):
        scaffold_series(ws, "ghost")
```

To `tests/test_video_episode.py`:

```python
@pytest.mark.parametrize(
    "bad", ["../../outside", "..", ".", "", "a/b", "a\\b", "/abs", "sub/dir"]
)
def test_load_episode_refuses_unsafe_ids(series, bad):
    with pytest.raises(EpisodeError, match="unsafe"):
        load_episode(series, bad)


@pytest.mark.parametrize("bad", ["../../outside", "..", "a/b", "/abs"])
def test_resolve_episode_refuses_unsafe_ids(series, bad):
    create_episode(series, "2026-08-14")
    with pytest.raises(EpisodeError):
        resolve_episode(series, bad)


def test_load_episode_still_accepts_a_hand_made_directory_name(series):
    d = series.episodes_dir / "Ep_01"
    (d / "sources").mkdir(parents=True)
    (d / "script.yaml").write_text(
        "---\nepisode: Ep_01\nseries: the-brief\nstatus: draft\n---\nbeats: []\n",
        encoding="utf-8",
    )
    assert load_episode(series, "Ep_01").status is Status.DRAFT
```

- [ ] **Step 1b: Tighten the one unpinned assertion**

In `tests/test_video_cli.py`, `test_over_long_name_fails_cleanly` currently
asserts `"too long" in output.lower() or "length" in ...`. The `OSError` message
satisfies that, so removing the cap keeps the test green. Replace **only** its
assertion block with:

```python
    assert result.exit_code == 1
    assert "limit 64" in result.output
```

- [ ] **Step 1c: Add the CLI escape test**

Append to `tests/test_video_cli.py`:

```python
def test_video_new_cannot_escape_the_workspace(ws, tmp_path):
    """Verified escape: --series ../../outside wrote a real episode outside the
    workspace whenever the traversal target was itself a valid series."""
    outside = tmp_path / "outside"
    (outside / "episodes").mkdir(parents=True)
    (outside / "series.toml").write_text('[series]\nname = "O"\n', encoding="utf-8")
    depth = len(ws.series_dir.parts) - len(tmp_path.parts)
    traversal = "/".join([".."] * depth) + "/outside"
    result = run("video", "new", "2026-08-14", "--series", traversal)
    assert result.exit_code == 1
    assert not (outside / "episodes" / "2026-08-14").exists()
```

```bash
uv run pytest tests/test_video_series.py tests/test_video_episode.py tests/test_video_cli.py 2>&1 | tail -25
git add tests/
git commit -m "test: pin path safety across both modules

video new --series ../../outside wrote an episode outside the workspace:
scaffold_series validated its slug, load_series did not, and the CLI
reaches create_episode through load_series."
```

- [ ] **Step 2: Implement**

**2a.** In `src/agenticsocial/video/series.py`, add above `_validate_slug`:

```python
_UNSAFE_CHARS = ("/", "\\", "\x00")


def _assert_safe_name(name: str, kind: str, error: type[Exception]) -> None:
    """Reject anything that could address a path outside its parent directory.

    Deliberately separate from the naming rules. Naming governs what agsoc will
    CREATE; this governs what it will TOUCH. A directory a human named `My-Show`
    stays loadable; `../../outside` does not, whoever made it. See D-038.
    """
    if not name or name in {".", ".."} or any(c in name for c in _UNSAFE_CHARS):
        raise error(
            f"unsafe {kind} {name!r} — must be a single directory name, "
            "not a path"
        )
```

Call it first in **both** `scaffold_series` and `load_series`:

```python
def scaffold_series(ws: Workspace, slug: str, name: str | None = None) -> Series:
    _assert_safe_name(slug, "series name", SeriesError)
    _validate_slug(slug)
    d = ws.series_dir / slug
    if d.exists() or d.is_symlink():
        raise SeriesError(f"series already exists: {slug}")
    ...
```

```python
def load_series(ws: Workspace, slug: str) -> Series:
    _assert_safe_name(slug, "series name", SeriesError)
    d = ws.series_dir / slug
    ...
```

Note the added `or d.is_symlink()` — `Path.exists()` follows symlinks, so a
dangling one was invisible and `mkdir` reported `[Errno 17]` where
`create_episode`'s sibling check says "already exists".

**2b.** In `src/agenticsocial/video/episode.py`, import the helper and use it in
all three path-taking functions:

```python
from .series import _assert_safe_name
```

```python
def create_episode(series: Series, ep_id: str) -> Episode:
    _assert_safe_name(ep_id, "episode id", EpisodeError)
    if len(ep_id) > MAX_ID_LEN:
        ...
```

```python
def load_episode(series: Series, ep_id: str) -> Episode:
    _assert_safe_name(ep_id, "episode id", EpisodeError)
    d = series.episodes_dir / ep_id
    ...
```

```python
def resolve_episode(series: Series, query: str) -> Episode:
    _assert_safe_name(query, "episode id", EpisodeError)
    ids = episode_ids(series)
    ...
```

`resolve_episode`'s existing empty-query guard is now redundant with
`_assert_safe_name`'s `not name` check — delete the old two-line guard and let
the shared helper own it. Confirm `test_empty_query_does_not_resolve_an_episode`
still passes; if it now fails on the message text, say so rather than editing it.

If importing a leading-underscore name across modules bothers you, say so in
your report — I chose one shared implementation over two that drift, which is
the entire subject of this task, but the naming is arguable.

- [ ] **Step 3: Run everything, then commit**

```bash
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/series.py src/agenticsocial/video/episode.py
git commit -m "fix: refuse names that address paths outside the workspace

agsoc video new --series ../../outside created a real episode outside the
workspace whenever the traversal target was itself a valid series.
scaffold_series validated its slug; load_series did not, and the CLI
reaches create_episode through load_series.

Path safety is now one shared helper used by every function that turns a
caller-supplied name into a path, kept separate from the naming rules so
a hand-made directory stays loadable."
```

- [ ] **Step 4: Mutation check**

Apply, run the full suite, `git checkout` between. All must fail:

1. `load_series` → drop `_assert_safe_name`
2. `load_episode` → drop `_assert_safe_name`
3. `resolve_episode` → drop `_assert_safe_name`
4. `_assert_safe_name` → drop the `name in {".", ".."}` check
5. `_assert_safe_name` → drop the `"\\" in name` check
6. `scaffold_series` → drop `or d.is_symlink()`
7. `_validate_slug` → drop the length cap **(this survived in Task 4b; Step 1b
   should now kill it)**

---

## Your report

`docs/superpowers/worklog/video/phase-01/task-5-report.md`:

1. **What I changed.**
2. **TDD evidence** — RED (piped) and GREEN.
3. **Mutation results** — a row per mutant with the test that caught it.
4. **Files changed**, both commit SHAs.
5. **Issues or concerns**, including:
   - Re-run the escape by hand against the real CLI, not just pytest. Paste it.
   - Is there any *other* way to address a path outside the workspace? Consider
     absolute paths, symlinked series directories, `AGSOC_WORKSPACE` itself, and
     a `series.toml` whose own contents point elsewhere.
   - **Final sibling sweep.** Compare `series.py` and `episode.py` function by
     function one more time and list every remaining asymmetry, however small.
     This is the last task before the phase gate; I would rather have the list
     than a clean bill of health.
