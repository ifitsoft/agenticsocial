# Task 6 Brief: Gate fixes — the four findings that block the merge

**Phase:** 1 · **Branch:** `feat/video-phase-01-scaffolding` · **Follows:** `94b4797`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

The phase-gate review returned **merge-after-fixes**. This task is those fixes.
Nothing else. When it lands, Phase 1 merges.

## The four

**F1 — `--series` is the one operator input never validated.** Every other string
goes through `_text()`. `agsoc video new X --series $'caf\xe9'` prints a full
`UnicodeEncodeError` traceback. Fourth instance of D-036.

**F2 — the approval gate can be walked past with a stale object.**
Leader-verified:

```
on disk now      : draft
stale object says: approved
after set_status : rendering        *** GATE BYPASSED ***
```

`set_status` checks `episode.status` (in memory) and writes against the file it
reads two lines later. Spec §8.4 and §10 exist to make rendering unreachable
without a human; this is the one invariant the product is built around. I had
adjudicated a weaker form of this to Phase 7 (D-032 F6) — that was wrong, and it
assigned the bug to a component that would *call* the broken function.

**F3 — a single-document `script.yaml` destroys operator beats.** A file with a
leading `---` but no separator has its beats parsed into document 1, then
`_compose` fabricates `beats: []` as document 2. Comments destroyed, and the
beats contract now claims the episode is empty.

**F4 — the tripwire for the 3d mutant does not fire.** Leader-verified: applying
the mutant leaves all 311 tests green. `test_empty_metadata_document_keeps_its_beats`
uses a substring-anywhere assertion that the corrupted output also satisfies.
This is D-035 reappearing *inside the test written to close D-035's third
instance*.

**F5 — concurrent `video new` deletes the winner's episode.** `create_episode`
puts its `mkdir` loop inside the `try` whose `except BaseException` calls
`rmtree`. Two concurrent creates: the loser's `FileExistsError` triggers cleanup
of the winner's finished episode.

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it**.
- Do not add dependencies. Report observed counts.
- Never stage anything under `docs/`.
- **Authorised test edit:** `test_empty_metadata_document_keeps_its_beats` in
  `tests/test_video_episode.py` — Step 1's replacement strengthens it. No other
  existing assertion may change.

---

- [ ] **Step 1: Tests**

Replace `test_empty_metadata_document_keeps_its_beats` entirely with:

```python
def test_empty_metadata_document_keeps_its_beats(series):
    """F4: the previous version asserted a substring that the CORRUPTED output
    also contains, so the 3d mutant survived. Assert bytes at the end."""
    ep = create_episode(series, "2026-08-14")
    beats = b"beats:\n  - type: statement\n"
    ep.script_path.write_bytes(b"---\n---\n" + beats)
    set_status(load_episode(series, "2026-08-14"), Status.IN_REVIEW)
    raw = ep.script_path.read_bytes()
    assert raw.endswith(beats), raw
```

Append to `tests/test_video_episode.py`:

```python
# --- F2: the gate must be checked against disk, not a stale object -------------


def test_set_status_checks_the_gate_against_disk_not_memory(series):
    """The approval gate is the one invariant the product rests on. A stale
    Episode must not be able to walk past it."""
    ep = create_episode(series, "2026-08-14")
    set_status(ep, Status.IN_REVIEW)
    set_status(ep, Status.APPROVED)
    ep.script_path.write_text(
        ep.script_path.read_text().replace("status: approved", "status: draft"),
        encoding="utf-8",
    )
    with pytest.raises(TransitionError):
        set_status(ep, Status.RENDERING)
    assert load_episode(series, "2026-08-14").status is Status.DRAFT


def test_set_status_refreshes_the_object_from_disk(series):
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        ep.script_path.read_text().replace("status: draft", "status: in_review"),
        encoding="utf-8",
    )
    set_status(ep, Status.APPROVED)  # legal from in_review, illegal from draft
    assert ep.status is Status.APPROVED


def test_set_status_rejects_an_unreadable_status_on_disk(series):
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "---\nepisode: e\nstatus: banana\n---\nbeats: []\n", encoding="utf-8"
    )
    with pytest.raises(EpisodeError, match="banana"):
        set_status(ep, Status.IN_REVIEW)


# --- F3: refuse the ambiguous shape rather than destroy beats ------------------


def test_script_without_a_separator_is_refused_not_reflowed(series):
    """Beats in document 1 were parsed as metadata, then `beats: []` was
    fabricated as document 2 — comments destroyed and the episode reported
    empty."""
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "---\nepisode: e\nseries: the-brief\nstatus: draft\n"
        "beats:\n  # hand written\n  - type: statement\n",
        encoding="utf-8",
    )
    with pytest.raises(EpisodeError, match="separator"):
        load_episode(series, "2026-08-14")


def test_metadata_only_script_is_still_allowed(series):
    """No beats key and no second document is the create path, not ambiguity."""
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "---\nepisode: e\nseries: the-brief\nstatus: draft\n", encoding="utf-8"
    )
    assert load_episode(series, "2026-08-14").status is Status.DRAFT


# --- F5: a losing concurrent create must not delete the winner -----------------


def test_create_over_an_existing_dir_does_not_delete_it(series, monkeypatch):
    """Two concurrent `video new`: the loser's FileExistsError must not trigger
    cleanup of the winner's finished episode."""
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text("---\nstatus: approved\n---\nbeats: [1]\n", encoding="utf-8")
    before = ep.script_path.read_bytes()
    with pytest.raises(EpisodeError, match="already exists"):
        create_episode(series, "2026-08-14")
    assert ep.script_path.read_bytes() == before
```

Append to `tests/test_video_cli.py`:

```python
def test_series_option_with_undecodable_text_fails_cleanly(ws):
    """F1: --series was the one operator input never passed through _text()."""
    result = run("video", "new", "2026-08-14", "--series", "caf\udce9")
    assert result.exit_code == 1
    assert "UTF-8" in result.output
```

```bash
uv run pytest 2>&1 | tail -20
git add tests/
git commit -m "test: pin the four gate findings

The gate can be walked past with a stale Episode; --series is the one
operator input never validated; a script with no separator has its beats
reflowed into the metadata document; and the tripwire written to pin the
3d mutant does not fire."
```

- [ ] **Step 2: Implement**

**2a — F2.** In `src/agenticsocial/video/episode.py`, `set_status` reads first
and gates on what it read:

```python
def set_status(episode: Episode, target: Status) -> None:
    """Move an episode to `target`.

    The gate is checked against the status ON DISK, not against `episode.status`.
    A caller holding a stale Episode must not be able to reach RENDERING from a
    file that says `draft` — spec §8.4 and §10 exist to make rendering
    unreachable without a human, and an in-memory check is not that guarantee.
    """
    meta, beats_text, nl = _read_meta(episode.script_path)
    raw = meta.get("status", Status.DRAFT.value)
    try:
        current = Status(raw)
    except ValueError:
        raise EpisodeError(
            f"{episode.script_path}: invalid status '{raw}' — one of: "
            f"{', '.join(s.value for s in Status)}"
        )
    assert_transition(current, target, VIDEO_TRANSITIONS)
    meta["status"] = target.value
    atomic_write(episode.script_path, _compose(meta, beats_text, nl))
    episode.status = target
    episode.meta = meta
```

The read happens before the gate check, but nothing is written unless the check
passes, so `test_a_rejected_transition_does_not_touch_the_file` still holds.

**2b — F3.** In `_read_meta`, refuse the ambiguous shape:

```python
    meta_text, beats_text, nl = _split(text)
    meta = _parse_meta(meta_text, path)
    if beats_text is None and "beats" in meta:
        raise EpisodeError(
            f"{path}: `beats` appears in the metadata document. script.yaml needs "
            "a `---` separator line between the metadata and the beats document."
        )
    return meta, beats_text, nl
```

Refusing is the whole point: the alternative is reflowing operator-written beats
through `safe_dump` and then claiming the episode is empty.

**2c — F5.** In `create_episode`, claim the directory atomically *outside* the
cleanup block, so a loser never deletes a winner:

```python
    try:
        d.mkdir(parents=True)          # atomic claim; FileExistsError if we lost
    except FileExistsError:
        raise EpisodeError(f"episode already exists: {series.slug}/{ep_id}")
    try:
        for sub in SUBDIRS:
            (d / sub).mkdir()
        atomic_write(d / "script.yaml", _compose(_new_meta(series, ep_id), None))
    except BaseException:
        import shutil

        shutil.rmtree(d, ignore_errors=True)
        raise
```

Keep the existing `if d.exists() or d.is_symlink()` check above it — it gives the
clean message in the common case; the `mkdir` is the race-safe backstop.

**2d — F1.** In `src/agenticsocial/video/cli.py`, `--series` goes through
`_text()` in both commands that accept it:

```python
@video_app.command("new")
def video_new(
    episode: str,
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
) -> None:
    """Create an episode directory with a stub script.yaml."""
    ws = _workspace()
    episode = _text(episode, "The episode id")
    series = _text(series, "The series slug")
    ...
```

```python
@video_app.command("list")
def video_list(
    series: str = typer.Option(DEFAULT_SERIES, "--series", help="series slug"),
) -> None:
    """List episodes and their statuses. Reports broken ones rather than dying."""
    ws = _workspace()
    series = _text(series, "The series slug")
    ...
```

- [ ] **Step 3: Run everything, then commit**

```bash
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/episode.py src/agenticsocial/video/cli.py
git commit -m "fix: check the approval gate against disk, and stop destroying beats

set_status gated on the in-memory status while writing against the file,
so a stale Episode could reach RENDERING from a script that said draft --
the one invariant the product is built around.

A script.yaml with no separator had its operator-written beats reflowed
into the metadata document and replaced with a fabricated `beats: []`;
that shape is now refused. --series was the one operator input never
validated. A losing concurrent create no longer deletes the winner."
```

- [ ] **Step 4: Mutation check**

Apply, run the full suite, `git checkout` between. All must fail:

1. `set_status` → gate on `episode.status` instead of the disk status
2. `_split` → `search(text, start.end())` **(the 3d mutant F4 failed to kill)**
3. `_read_meta` → drop the `"beats" in meta` refusal
4. `video_new` → drop `_text(series, ...)`
5. `create_episode` → move `d.mkdir` back inside the cleanup `try`

Mutant 2 is the one that matters: it survived the whole suite before this task.

---

## Your report

`docs/superpowers/worklog/video/phase-01/task-6-report.md`:

1. **What I changed.**
2. **TDD evidence** — RED (piped) and GREEN.
3. **Mutation results** — a row per mutant with the test that caught it.
4. **Files changed**, both commit SHAs.
5. **Issues or concerns**, including:
   - Re-run the F2 gate bypass by hand and paste it. Is there any *other* way to
     reach `RENDERING` without passing the gate?
   - Does gating on disk break any legitimate caller — a batch operation holding
     several `Episode` objects, for instance?
   - The gate review found four vacuous tests and four more weaker than they
     read. Audit the tests **you** just wrote by the same standard: what would
     each do if the code did nothing at all?
