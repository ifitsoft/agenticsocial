# Task 4b Brief: Complete the CLI error surface, and make the CLI tests able to fail

**Phase:** 1 · **Branch:** `feat/video-phase-01-scaffolding` · **Follows:** `4f09274`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why

The Task 4 implementer found 14 reproducing tracebacks across 4 root causes, and
— more importantly — proved that **the CLI test file cannot detect any of them.**

`CliRunner.invoke` defaults to `catch_exceptions=True`. Leader-verified:

```
exit_code = 1        output = ''        exception = ValueError: uncaught crash

  assert exit_code == 1                   -> True   (passes)
  assert 'traceback' not in output        -> True   (passes)
```

An uncaught crash is indistinguishable from a clean `_fail`. Every "fails
cleanly" assertion in `tests/test_video_cli.py` is vacuous, which is why mutant 3
survived.

This is the **third** time a test harness has performed the very transformation
the test was meant to detect (D-027: a corrupt fixture that was still valid YAML;
D-031: `write_text`/`read_text` cancelling newline translation on both sides).

The four root causes, all leader- or implementer-verified:

| | Defect | Reachability |
|---|---|---|
| a | Slug/id over 255 chars → uncaught `OSError: File name too long` | typing/pasting a URL |
| b | Non-UTF-8 `series.toml` → `UnicodeDecodeError` escapes `SeriesError`, **`agsoc series list` dies entirely** | a cp1252-defaulting editor |
| c | `series_slugs` lacks the `OSError` guard `episode_ids` has | unreadable `series/` |
| d | Write-path `OSError` uncaught in both `new` commands | read-only dir, full disk, `series` as a file |

**(b) is the one that stings.** It is the same bug Task 4 Step 0 fixed in
`episode.py`, still open in its sibling `series.py`. I fixed one side and never
checked the other.

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it**.
- Do not add dependencies. Report observed counts.
- Never stage anything under `docs/`.
- **Authorised exception to "do not modify existing tests":** you must change how
  `tests/test_video_cli.py` invokes the CLI (Step 1a). That file is from this
  phase and its harness is defective. Change *only* the invocation mechanism —
  do not weaken or delete any assertion.

## Files

- Modify: `tests/test_video_cli.py`
- Modify: `src/agenticsocial/video/series.py`
- Modify: `src/agenticsocial/video/episode.py`
- Modify: `src/agenticsocial/video/cli.py`

---

- [ ] **Step 1a: Make the CLI tests able to fail**

In `tests/test_video_cli.py`, replace the runner with a helper that refuses to
swallow exceptions, and route every existing call through it:

```python
runner = CliRunner()


def run(*args):
    """Invoke the CLI with exceptions propagating.

    CliRunner catches exceptions by default and reports exit_code 1 with empty
    output — identical to a clean _fail — so an uncaught traceback passes every
    assertion a test would naturally write. See D-035.
    """
    return runner.invoke(app, list(args), catch_exceptions=False)
```

Then mechanically rewrite every `runner.invoke(app, [...])` in the file to
`run(...)`. For example `runner.invoke(app, ["series", "new", "the-brief"])`
becomes `run("series", "new", "the-brief")`. Change nothing else about any test.

`typer.Exit` raises `SystemExit`, which `CliRunner` still handles even with
`catch_exceptions=False`, so clean failures keep reporting `exit_code == 1`.

- [ ] **Step 1b: Append the new tests**

```python
# --- every operator-typable input must fail cleanly, never traceback -----------


@pytest.mark.parametrize("cmd", [("series", "new"), ("video", "new")])
def test_over_long_name_fails_cleanly(ws, cmd):
    """Reachable by pasting a URL. The regexes constrain the alphabet but not
    the length, and mkdir raises OSError: File name too long at NAME_MAX + 1."""
    result = run(*cmd, "a" * 300)
    assert result.exit_code == 1
    assert "too long" in result.output.lower() or "length" in result.output.lower()


def test_series_list_survives_a_non_utf8_series_toml(ws):
    """The D-018 failure mode: one file saved by a cp1252-defaulting editor
    currently kills the entire listing with a raw UnicodeDecodeError."""
    run("series", "new", "good-one")
    d = ws.series_dir / "latin1"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_bytes(b'[series]\nname = "caf\xe9"\n')
    result = run("series", "list")
    assert result.exit_code == 0
    assert "good-one" in result.output
    assert "latin1" in result.output


def test_load_series_on_non_utf8_raises_series_error(ws):
    from agenticsocial.video.models import SeriesError
    from agenticsocial.video.series import load_series

    d = ws.series_dir / "latin1"
    (d / "episodes").mkdir(parents=True)
    (d / "series.toml").write_bytes(b'[series]\nname = "caf\xe9"\n')
    with pytest.raises(SeriesError, match="UTF-8"):
        load_series(ws, "latin1")


def test_series_list_survives_an_unreadable_series_dir(ws):
    import os
    import stat

    run("series", "new", "the-brief")
    mode = ws.series_dir.stat().st_mode
    os.chmod(ws.series_dir, 0)
    try:
        if os.access(ws.series_dir, os.R_OK):
            pytest.skip("cannot revoke read permission as this user")
        result = run("series", "list")
        assert result.exit_code == 1
        assert "cannot list" in result.output.lower()
    finally:
        os.chmod(ws.series_dir, stat.S_IMODE(mode))


def test_series_new_into_a_read_only_workspace_fails_cleanly(ws):
    import os
    import stat

    ws.series_dir.mkdir(parents=True, exist_ok=True)
    mode = ws.series_dir.stat().st_mode
    os.chmod(ws.series_dir, stat.S_IRUSR | stat.S_IXUSR)
    try:
        if os.access(ws.series_dir, os.W_OK):
            pytest.skip("cannot revoke write permission as this user")
        result = run("series", "new", "the-brief")
        assert result.exit_code == 1
        assert "cannot create" in result.output.lower()
    finally:
        os.chmod(ws.series_dir, stat.S_IMODE(mode))


def test_series_list_reports_an_unknown_episode_count_rather_than_zero(ws):
    """`0 episodes` is a claim. When the count cannot be read, say so."""
    import os
    import stat

    run("series", "new", "the-brief")
    run("video", "new", "2026-08-14", "--series", "the-brief")
    eps = ws.series_dir / "the-brief" / "episodes"
    mode = eps.stat().st_mode
    os.chmod(eps, 0)
    try:
        if os.access(eps, os.R_OK):
            pytest.skip("cannot revoke read permission as this user")
        result = run("series", "list")
        assert result.exit_code == 0
        assert "? episodes" in result.output
        assert "0 episodes" not in result.output
    finally:
        os.chmod(eps, stat.S_IMODE(mode))
```

```bash
uv run pytest tests/test_video_cli.py 2>&1 | tail -25
git add tests/test_video_cli.py
git commit -m "test: stop CliRunner swallowing crashes, pin the CLI error surface

catch_exceptions=True made an uncaught traceback indistinguishable from
a clean failure: exit_code 1, empty output. Every 'fails cleanly'
assertion in this file was vacuous, which is why the Task 4 mutant that
disabled UTF-8 validation survived."
```

- [ ] **Step 2: Implement**

**2a.** In `src/agenticsocial/video/series.py`, `load_series`'s `try` gains a
clause — `tomllib.load` decodes UTF-8 itself and raises `ValueError`, not
`OSError`:

```python
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise SeriesError(f"{path}: malformed series.toml — {e}")
    except UnicodeDecodeError as e:
        raise SeriesError(
            f"{path}: series.toml is not valid UTF-8 — {e}. "
            "Re-save it as UTF-8; agsoc writes and expects UTF-8 everywhere."
        )
    except OSError as e:
        raise SeriesError(f"{path}: cannot read series.toml — {e}")
```

**2b.** `series_slugs` gains the guard its sibling `episode_ids` already has:

```python
def series_slugs(ws: Workspace) -> list[str]:
    """Enumerate series slugs. Cannot fail on a malformed series — see D-018.
    An unreadable series/ still surfaces as SeriesError, never OSError."""
    if not ws.series_dir.is_dir():
        return []
    try:
        return sorted(
            d.name for d in ws.series_dir.iterdir() if (d / "series.toml").is_file()
        )
    except OSError as e:
        raise SeriesError(f"{ws.series_dir}: cannot list series — {e}")
```

**2c.** Length caps, at validation time rather than derived from the platform.
In `series.py`, `_validate_slug` gains a first check:

```python
MAX_NAME_LEN = 64


def _validate_slug(slug: str) -> None:
    if len(slug) > MAX_NAME_LEN:
        raise SeriesError(
            f"series slug is too long ({len(slug)} characters, limit {MAX_NAME_LEN})"
        )
    if not SLUG_RE.match(slug):
        raise SeriesError(
            f"invalid series slug {slug!r} — use lowercase letters, digits and "
            "hyphens, starting with a letter or digit (slugs become directory names)"
        )
```

In `episode.py`, the same shape at the top of `create_episode`, before the
regex check:

```python
    if len(ep_id) > MAX_ID_LEN:
        raise EpisodeError(
            f"episode id is too long ({len(ep_id)} characters, limit {MAX_ID_LEN})"
        )
```

with `MAX_ID_LEN = 64` beside `EPISODE_ID_RE`.

**2d.** Both `new` commands catch write-path `OSError`. In
`src/agenticsocial/video/cli.py`:

```python
    try:
        s = scaffold_series(ws, slug, name=name)
    except SeriesError as e:
        raise _fail(str(e))
    except OSError as e:
        raise _fail(f"cannot create series {slug!r}: {e}")
```

and in `video_new`:

```python
    try:
        s = _resolve_series(ws, series, autocreate=True)
        ep = create_episode(s, episode)
    except (SeriesError, EpisodeError) as e:
        raise _fail(str(e))
    except OSError as e:
        raise _fail(f"cannot create episode {episode!r}: {e}")
```

**2e.** `series_list` reports an unknown count honestly:

```python
        try:
            n: object = len(episode_ids(s))
        except EpisodeError:
            n = "?"
```

and `series_slugs` errors surface rather than crash:

```python
    try:
        slugs = series_slugs(ws)
    except SeriesError as e:
        raise _fail(str(e))
```

- [ ] **Step 3: Run everything, then commit**

```bash
uv run pytest tests/test_video_cli.py -v 2>&1 | tail -40
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/series.py src/agenticsocial/video/episode.py src/agenticsocial/video/cli.py
git commit -m "fix: no operator input reaches a traceback

UnicodeDecodeError escaped SeriesError, so one cp1252-saved series.toml
killed the whole listing -- the same bug fixed in episode.py one task
earlier and never checked in its sibling. Adds length caps, the
series_slugs OSError guard episode_ids already had, write-path OSError
handling in both new commands, and an honest '?' when an episode count
cannot be read."
```

- [ ] **Step 4: Mutation check**

Apply, run the full suite, `git checkout` between. All must fail:

1. `run()` → drop `catch_exceptions=False` **(must fail; if it does not, the
   harness fix did not take)**
2. `load_series` → drop the `UnicodeDecodeError` clause
3. `series_slugs` → drop the `OSError` guard
4. `_validate_slug` → drop the length cap
5. `series_list` → report `0` instead of `"?"`

Mutant 1 is the important one: it proves the tests can now see a crash.

---

## Your report

`docs/superpowers/worklog/video/phase-01/task-4b-report.md`:

1. **What I changed.**
2. **TDD evidence** — RED (piped) and GREEN (both runs). Say how many previously
   passing tests changed behaviour when `catch_exceptions=False` landed; if any
   test that passed before now fails, that is a bug it was hiding and I want it
   called out separately.
3. **Mutation results** — a row per mutant with the test that caught it.
4. **Files changed**, both commit SHAs.
5. **Issues or concerns**, including:
   - Re-run your Task 4 traceback hunt against the fixed code. What still
     tracebacks? This is the last task before the phase gate.
   - Is `MAX_NAME_LEN = 64` right, or does it break a plausible real id?
   - Anywhere else in `src/` where one module was fixed and its sibling was not.
     I did exactly that with the UTF-8 guard; assume I did it elsewhere.
