# Task 3c Brief: Make byte preservation actually true

**Phase:** 1 · **Branch:** `feat/video-phase-01-scaffolding` · **Follows:** `e0c00da`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why

Task 3b promised that `set_status` leaves the beats document byte-identical.
**It does not, and QA proved it.** Reproduced through the real API:

```
beats before: b'beats:\r\n  # a comment\r\n  - type: statement\r\n'
beats after : b'beats:\n  # a comment\n  - type: statement\n'
BYTE-IDENTICAL: False
```

`Path.read_text()` opens with universal newlines, so CRLF (or lone-CR) content is
translated to LF on read and written back as LF. Every byte of the beats document
changes. That is exactly the `script_sha256` drift (spec §10) that D-026 gives as
*the reason* for the two-document design.

This is not new scope — D-028 caps *additional* work on `episode.py`, and this is
3b's own stated contract not being met.

**How it got missed is worth knowing.** The Task 3 implementer flagged CRLF but
attributed it to `_split`; I re-verified by checking that *parsing still works*
and declared it a non-defect. Parsing is not the guarantee. Byte identity is. QA
tested the right property. The tests missed it for the same reason: every
preservation test uses `write_text`/`read_text`, so the suite pins **content**,
not **bytes** — and four mutants live in that gap.

Three smaller error-contract items ride along, because Task 4 is about to write
`except EpisodeError` and depends on them.

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it**.
- Do not modify existing tests. Do not add dependencies.
- Never stage anything under `docs/`. Report observed counts.

## Files

- Modify: `src/agenticsocial/video/episode.py`
- Modify: `src/agenticsocial/workspace.py` (one keyword — Step 3c)
- Modify: `tests/test_video_episode.py` (append only)

---

- [ ] **Step 1: Append the tests**

```python
# --- byte-level preservation ---------------------------------------------------
# The existing preservation tests use write_text/read_text, which apply universal
# newline translation on BOTH sides — so they pin content, not bytes, and a CRLF
# script had every byte rewritten while they stayed green. These use bytes.


def _write_bytes(ep, meta_lines, beats, nl):
    body = nl.join(meta_lines).encode() + nl.encode()
    ep.script_path.write_bytes(
        b"---" + nl.encode() + body + b"---" + nl.encode() + beats
    )


def _beats_bytes(ep, nl):
    raw = ep.script_path.read_bytes()
    return raw.split(b"---" + nl.encode(), 2)[-1]


META = ["episode: e", "series: the-brief", "status: draft"]


@pytest.mark.parametrize("nl", ["\n", "\r\n", "\r"])
def test_beats_bytes_survive_a_status_change(series, nl):
    ep = create_episode(series, "ep")
    beats = nl.join(["beats:", "  # a comment", "  - type: statement", ""]).encode()
    _write_bytes(ep, META, beats, nl)
    set_status(load_episode(series, "ep"), Status.IN_REVIEW)
    assert _beats_bytes(ep, nl) == beats


@pytest.mark.parametrize("nl", ["\n", "\r\n"])
def test_beats_bytes_survive_repeated_status_changes(series, nl):
    """script_sha256 must not drift across a draft -> review -> approve run."""
    ep = create_episode(series, "ep")
    beats = nl.join(["beats:", "  - type: kpis", "    hold:  4.6", ""]).encode()
    _write_bytes(ep, META, beats, nl)
    for target in (Status.IN_REVIEW, Status.APPROVED, Status.IN_REVIEW):
        set_status(load_episode(series, "ep"), target)
    assert _beats_bytes(ep, nl) == beats


def test_trailing_whitespace_and_tabs_in_beats_are_preserved(series):
    ep = create_episode(series, "ep")
    beats = b"beats:\n\t- type: statement   \n\n\n  # trailing blank lines\n\n"
    _write_bytes(ep, META, beats, "\n")
    set_status(load_episode(series, "ep"), Status.IN_REVIEW)
    assert _beats_bytes(ep, "\n") == beats


def test_beats_without_a_trailing_newline_is_preserved(series):
    ep = create_episode(series, "ep")
    beats = b"beats:\n  - type: statement"
    _write_bytes(ep, META, beats, "\n")
    set_status(load_episode(series, "ep"), Status.IN_REVIEW)
    assert _beats_bytes(ep, "\n") == beats


# --- the error contract Task 4's `except EpisodeError` depends on --------------


def test_unreadable_episodes_dir_raises_episode_error(series):
    import os
    import stat

    create_episode(series, "2026-08-14")
    d = series.episodes_dir
    mode = d.stat().st_mode
    os.chmod(d, 0)
    try:
        if os.access(d, os.R_OK):  # running as root; the probe is meaningless
            pytest.skip("cannot revoke read permission as this user")
        with pytest.raises(EpisodeError):
            episode_ids(series)
    finally:
        os.chmod(d, stat.S_IMODE(mode))


def test_create_over_a_dangling_symlink_raises_episode_error(series):
    (series.episodes_dir).mkdir(parents=True, exist_ok=True)
    (series.episodes_dir / "ghost").symlink_to(series.episodes_dir / "nowhere")
    with pytest.raises(EpisodeError):
        create_episode(series, "ghost")


def test_empty_query_does_not_resolve_an_episode(series):
    """`agsoc video review ""` must not silently pick the only episode."""
    create_episode(series, "2026-08-14")
    with pytest.raises(EpisodeError):
        resolve_episode(series, "")
```

- [ ] **Step 2: Run, then commit the tests**

```bash
uv run pytest tests/test_video_episode.py 2>&1 | tail -30
git add tests/test_video_episode.py
git commit -m "test: pin beats preservation at the byte level, not the content level

Existing preservation tests used write_text/read_text, so newline
translation happened on both sides and cancelled out. A CRLF script had
every byte rewritten while the suite stayed green."
```

- [ ] **Step 3: Implement**

**3a.** In `src/agenticsocial/video/episode.py`, add `import re` beside the other
imports, delete `_SEP`, and replace `_split`, `_read_meta` and `_compose` with:

```python
_DOC_START_RE = re.compile(r"\A---[ \t]*(\r\n|\r|\n)")
_SEP_RE = re.compile(r"(\r\n|\r|\n)---[ \t]*(?=\r\n|\r|\n)")


def _split(text: str) -> tuple[str, str | None, str]:
    """Split into (metadata text, verbatim remainder, newline).

    Purely textual — nothing here parses YAML. The newline is returned so the
    metadata block can be re-emitted using the file's own line ending; the
    remainder is never touched at all.
    """
    start = _DOC_START_RE.match(text)
    if not start:
        return text, None, "\n"
    nl = start.group(1)
    sep = _SEP_RE.search(text, start.end() - len(nl))
    if not sep:
        return text[start.end() :], None, nl
    return text[start.end() : sep.start()], text[sep.end() + len(sep.group(1)) :], nl


def _read_meta(path: Path) -> tuple[dict, str | None, str]:
    """Return (metadata, verbatim beats text, newline). Never parses the beats.

    Reads with newline="" so line endings reach us untranslated. Universal
    newline mode would rewrite a CRLF beats document to LF on the next write —
    which is the script_sha256 drift the two-document design exists to prevent.
    """
    try:
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
    except OSError as e:
        raise EpisodeError(f"{path}: cannot read script.yaml — {e}")
    meta_text, beats_text, nl = _split(text)
    return _parse_meta(meta_text, path), beats_text, nl


def _compose(meta: dict, beats_text: str | None, nl: str = "\n") -> str:
    head = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    head = head.replace("\n", nl)
    body = f"beats: []{nl}" if beats_text is None else beats_text
    return f"---{nl}{head}{nl}---{nl}{body}"
```

Note on `_SEP_RE`: the lookahead means the separator's *trailing* newline is not
consumed by the match, so `sep.end() + len(sep.group(1))` steps over it — the
remainder therefore starts at the first byte the operator wrote. The search
begins at `start.end() - len(nl)` so that the newline ending the opening `---`
can serve as the separator's leading newline when metadata is empty.

**3b.** Update the three call sites for the new three-tuple, and harden two
`OSError` paths:

```python
def create_episode(series: Series, ep_id: str) -> Episode:
    d = series.episodes_dir / ep_id
    if d.exists() or d.is_symlink():
        raise EpisodeError(f"episode already exists: {series.slug}/{ep_id}")
    try:
        for sub in SUBDIRS:
            (d / sub).mkdir(parents=True)
        atomic_write(d / "script.yaml", _compose(_new_meta(series, ep_id), None))
    except BaseException:
        # Mirror scaffold_series: a half-built episode is invisible to
        # episode_ids, blocks re-creation, and reports two contradictory errors.
        import shutil

        shutil.rmtree(d, ignore_errors=True)
        raise
    return Episode(
        id=ep_id,
        series_slug=series.slug,
        dir=d,
        status=Status.DRAFT,
        meta=_new_meta(series, ep_id),
    )


def _new_meta(series: Series, ep_id: str) -> dict:
    return {
        "episode": ep_id,
        "series": series.slug,
        "status": Status.DRAFT.value,
        "date_long": "",
        "pace": 1.0,
    }


def episode_ids(series: Series) -> list[str]:
    """Enumerate episode ids. Parses nothing, so a corrupt episode cannot break
    it — see D-018. Task 4's `except EpisodeError` depends on this, so even an
    unreadable directory must surface as EpisodeError rather than OSError."""
    if not series.episodes_dir.is_dir():
        return []
    try:
        return sorted(
            d.name
            for d in series.episodes_dir.iterdir()
            if (d / "script.yaml").is_file()
        )
    except OSError as e:
        raise EpisodeError(f"{series.episodes_dir}: cannot list episodes — {e}")
```

`load_episode` and `set_status` take the third tuple element:

```python
    meta, _, _ = _read_meta(path)
```

```python
def set_status(episode: Episode, target: Status) -> None:
    assert_transition(episode.status, target, VIDEO_TRANSITIONS)
    meta, beats_text, nl = _read_meta(episode.script_path)
    meta["status"] = target.value
    atomic_write(episode.script_path, _compose(meta, beats_text, nl))
    episode.status = target
    episode.meta = meta
```

And `resolve_episode` rejects an empty query — insert as its first statement:

```python
    if not query:
        raise EpisodeError("no episode specified — see `agsoc video list`")
```

**3c.** In `src/agenticsocial/workspace.py`, `atomic_write` must not translate
newlines on the way out:

```python
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
```

Without `newline=""`, Python translates `"\n"` to `os.linesep` on write. That is
a no-op on macOS and Linux and silently corrupts every file on Windows. It cannot
be tested on this platform; it is correct regardless, and the text pipeline wants
it too.

- [ ] **Step 4: Run everything, then commit**

```bash
uv run pytest tests/test_video_episode.py -v 2>&1 | tail -40
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/episode.py src/agenticsocial/workspace.py
git commit -m "fix: preserve beats bytes exactly, including line endings

read_text applied universal newline translation, so set_status rewrote
every byte of a CRLF beats document to LF -- the exact script_sha256
drift the two-document design exists to prevent. Reads with newline=''
and re-emits metadata using the file's own line ending.

episode_ids and create_episode now surface OSError as EpisodeError, which
Task 4's CLI depends on. resolve_episode rejects an empty query.
atomic_write no longer translates newlines on write."
```

- [ ] **Step 5: Mutation check**

Apply each, run the full suite, `git checkout` between. All must fail:

1. `_read_meta` → `path.read_text(encoding="utf-8")` (universal newlines back)
2. `_compose` → drop `head.replace("\n", nl)`
3. `_read_meta` → `beats_text.rstrip()` before returning
4. `_compose` → append `nl` when `beats_text` lacks a trailing newline
5. `_compose` → `beats_text.expandtabs()`
6. `episode_ids` → drop the `try/except OSError`
7. `resolve_episode` → drop the empty-query guard

Mutants 3, 4 and 5 are the whitespace blind spot QA found — they survived the
previous suite. Report any survivor rather than strengthening tests yourself.

---

## Your report

`docs/superpowers/worklog/video/phase-01/task-3c-report.md`:

1. **What I changed.**
2. **TDD evidence** — RED (piped) and GREEN (both runs).
3. **Mutation results** — a row per mutant with the test that caught it.
4. **Files changed**, both commit SHAs.
5. **Issues or concerns**, including:
   - Is `_split`'s new regex pair correct for the empty-metadata case
     (`---\n---\nbeats: []`)? Construct it and say what happens.
   - A file mixing line endings — CRLF metadata, LF beats. What do we write
     back, and is it defensible?
   - Does `newline=""` in `atomic_write` change any behaviour for the existing
     text pipeline on this platform? Prove it either way.
