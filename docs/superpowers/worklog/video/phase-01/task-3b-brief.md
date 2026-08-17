# Task 3b Brief: Never parse, never rewrite, never lose the beats document

**Phase:** 1 · **Branch:** `feat/video-phase-01-scaffolding` · **Follows:** `512655e`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why

The Task 3 implementer attacked the design, as asked, and found three real
defects plus two smaller ones. All were mine.

1. **Data loss, reproduced.** `_read` substitutes `{"beats": []}` whenever
   document 2 is not a dict — including when beats is written as a bare YAML
   *sequence*, a natural shape. `set_status` then writes that substitute to
   disk. A third document is dropped the same way. Silently. My own docstring
   promised document 2 "must survive every write here untouched"; it was
   aspirational.
2. **The contract is not delivered.** `_read` has no guard around
   `safe_load_all`, so an unparseable script raises `yaml.scanner.ScannerError`,
   not `EpisodeError`. Task 4 will write `except EpisodeError` — matching every
   handler in `cli.py` — and `agsoc video list` will traceback on exactly the
   corrupt file D-018 exists to survive.
3. **My tests gave false confidence.** Every corrupt-episode fixture uses
   `status: banana`, which is *valid YAML*. Nothing in the suite ever hands the
   parser something it cannot parse.
4. `create_episode` has no cleanup on partial failure, leaving a directory
   invisible to `episode_ids`, un-creatable, and whose two error messages
   contradict each other. Its sibling `scaffold_series` handles exactly this
   with an `rmtree` and a comment saying why.
5. `episode_ids` uses `.exists()` where `series_slugs` uses `.is_file()`.

## The design decision this settles

The implementer argued for collapsing to a single document. **I am keeping two,
for a reason I failed to give the first time — and the new reason dictates a
different implementation.**

The value of two documents is not "beats is structured data". It is that
**metadata can be rewritten without touching the beats bytes at all.** That
matters concretely:

- Spec §10 binds approval to `script_sha256` and refuses to render a script that
  changed after approval. If a status write reformats beats, drift detection
  fires on churn we caused ourselves.
- Phase 2's `storyboard` skill writes `script.yaml` with deliberate formatting
  and comments. `yaml.safe_dump` destroys both. An operator running
  `agsoc video approve` must not find their script reflowed.
- A beats syntax error must not stop you reading the status — D-018's principle,
  one level down.

None of those hold today, because `_read` parses document 2, `list()`s it, and
`_dump` re-serialises it. The implementer's diagnosis was exact: *"the current
shape has the costs of one design and the benefits of neither."*

So: **Phase 1 never parses document 2.** It splits the file textually, parses
only document 1, and re-emits document 2's bytes verbatim. That is simpler than
what exists now, removes the substitution entirely, and delivers the isolation
the two-document form was supposed to buy.

The `frontmatter.parse` trap the implementer found is real and stays real — that
helper will happily read a `script.yaml` and return beats as an unparsed string.
Mitigated here with a loud module docstring; Phase 3's brief will name the
correct parser explicitly.

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it**.
- Do not modify existing tests **except** the two amendments in Step 1b.
- Never stage anything under `docs/`. Report observed counts, not predicted ones.

## Files

- Modify: `src/agenticsocial/video/episode.py`
- Modify: `tests/test_video_episode.py`

---

- [ ] **Step 1a: Append these tests**

```python
# --- document 2 is never parsed, never rewritten, never lost -------------------
# Task 3 substituted {"beats": []} for any document 2 that was not a dict, then
# wrote the substitute back on the next status change. Reproduced with a bare
# YAML sequence, which is a natural way to write beats.


def _write_script(ep, text):
    ep.script_path.write_text(text, encoding="utf-8")


def test_set_status_preserves_a_sequence_beats_document_verbatim(series):
    ep = create_episode(series, "2026-08-14")
    body = "---\nepisode: 2026-08-14\nseries: the-brief\nstatus: draft\n---\n- type: statement\n  text: hello\n"
    _write_script(ep, body)
    reloaded = load_episode(series, "2026-08-14")
    set_status(reloaded, Status.IN_REVIEW)
    after = ep.script_path.read_text(encoding="utf-8")
    assert "- type: statement" in after
    assert "beats: []" not in after


def test_set_status_preserves_comments_and_formatting_in_beats(series):
    """The storyboard skill writes deliberate formatting. Approving must not
    reflow it, and script_sha256 drift must not fire on churn we caused."""
    ep = create_episode(series, "2026-08-14")
    beats = (
        "beats:\n"
        "  # the cold open carries the whole episode\n"
        "  - type: statement\n"
        '    text: "Google shipped its main agentic model."\n'
        "\n"
        "  - type:  kpis          # deliberate double space\n"
        "    hold:  4.6\n"
    )
    _write_script(
        ep, f"---\nepisode: 2026-08-14\nseries: the-brief\nstatus: draft\n---\n{beats}"
    )
    reloaded = load_episode(series, "2026-08-14")
    set_status(reloaded, Status.IN_REVIEW)
    after = ep.script_path.read_text(encoding="utf-8")
    assert after.endswith(beats)


def test_set_status_preserves_a_third_document(series):
    ep = create_episode(series, "2026-08-14")
    _write_script(
        ep,
        "---\nepisode: 2026-08-14\nseries: the-brief\nstatus: draft\n"
        "---\nbeats: []\n---\nnotes: kept\n",
    )
    reloaded = load_episode(series, "2026-08-14")
    set_status(reloaded, Status.IN_REVIEW)
    assert "notes: kept" in ep.script_path.read_text(encoding="utf-8")


def test_beats_bytes_are_identical_across_a_status_change(series):
    ep = create_episode(series, "2026-08-14")
    beats = "beats:\n  - type: statement\n    text: unchanged\n"
    _write_script(
        ep, f"---\nepisode: 2026-08-14\nseries: the-brief\nstatus: draft\n---\n{beats}"
    )
    before = ep.script_path.read_text(encoding="utf-8").split("\n---\n", 1)[1]
    reloaded = load_episode(series, "2026-08-14")
    set_status(reloaded, Status.IN_REVIEW)
    set_status(reloaded, Status.APPROVED)
    after = ep.script_path.read_text(encoding="utf-8").split("\n---\n", 1)[1]
    assert after == before


# --- a beats syntax error must not stop you reading the status -----------------


def test_status_is_readable_even_when_beats_is_unparseable(series):
    """D-018 one level down: the diagnostic path must survive broken beats."""
    ep = create_episode(series, "2026-08-14")
    _write_script(
        ep,
        "---\nepisode: 2026-08-14\nseries: the-brief\nstatus: in_review\n"
        "---\nbeats: [unclosed\n  : : :\n",
    )
    assert load_episode(series, "2026-08-14").status is Status.IN_REVIEW


# --- unparseable METADATA raises EpisodeError, never a YAML exception ----------


@pytest.mark.parametrize(
    "body",
    [
        "---\n: : :\n  - broken\n---\nbeats: []\n",
        "---\nepisode: [unclosed\n---\nbeats: []\n",
        "\x00\x01 not yaml at all\n",
        '---\n"unterminated\n---\nbeats: []\n',
    ],
)
def test_unparseable_metadata_raises_episode_error(series, body):
    ep = create_episode(series, "2026-08-14")
    _write_script(ep, body)
    with pytest.raises(EpisodeError):
        load_episode(series, "2026-08-14")


def test_non_mapping_metadata_raises_episode_error(series):
    ep = create_episode(series, "2026-08-14")
    _write_script(ep, "---\n- just\n- a list\n---\nbeats: []\n")
    with pytest.raises(EpisodeError, match="metadata"):
        load_episode(series, "2026-08-14")


def test_episode_ids_survives_an_unparseable_script(series):
    """The enumerator must never parse anything. This is the D-018 guarantee
    Task 4's `except EpisodeError` will rely on."""
    create_episode(series, "2026-08-14")
    bad = create_episode(series, "2026-08-15")
    _write_script(bad, "\x00\x01 : : not yaml [\n")
    assert episode_ids(series) == ["2026-08-14", "2026-08-15"]


def test_resolve_a_healthy_episode_despite_an_unparseable_neighbour(series):
    create_episode(series, "2026-08-14")
    bad = create_episode(series, "2026-08-15")
    _write_script(bad, "\x00\x01 : : not yaml [\n")
    assert resolve_episode(series, "2026-08-14").id == "2026-08-14"


# --- create_episode must not leave a half-built directory ----------------------


def test_failed_create_leaves_no_partial_directory(series, monkeypatch):
    import agenticsocial.video.episode as ep_mod

    def explode(path, text):
        raise OSError("disk full")

    monkeypatch.setattr(ep_mod, "atomic_write", explode)
    with pytest.raises(OSError):
        create_episode(series, "doomed")
    assert not (series.episodes_dir / "doomed").exists()
    monkeypatch.undo()
    create_episode(series, "doomed")  # retry must work


def test_episode_ids_ignores_a_directory_where_the_script_should_be(series):
    create_episode(series, "2026-08-14")
    d = series.episodes_dir / "weird"
    (d / "script.yaml").mkdir(parents=True)
    assert episode_ids(series) == ["2026-08-14"]
```

- [ ] **Step 1b: Two amendments**

`test_created_script_is_two_yaml_documents` and
`test_set_status_persists_and_preserves_beats` both call `yaml.safe_load_all`
and assert `docs[1] == {"beats": []}`. Both stay — a freshly created script
still has exactly that shape, and they now also pin that we did not change the
on-disk format. No edit needed. **Confirm this in your report rather than
assuming it**; if either fails, tell me instead of editing it.

- [ ] **Step 2: Run, then commit the tests**

```bash
uv run pytest tests/test_video_episode.py 2>&1 | tail -40
git add tests/test_video_episode.py
git commit -m "test: pin beats-document preservation and EpisodeError contract

Task 3 substituted {beats: []} for any document 2 that was not a dict and
wrote the substitute back. Every corrupt-episode fixture used valid YAML,
so nothing ever handed the parser something unparseable."
```

- [ ] **Step 3: Replace the top of `src/agenticsocial/video/episode.py`**

Replace the module docstring and everything down to (and including) `_read`
with:

```python
"""Episode directories and the episode status lifecycle.

`script.yaml` is a TWO-DOCUMENT YAML file. Document 1 is metadata (episode id,
series, status, pace); document 2 is `beats:`.

Phase 1 never parses document 2. It splits the file textually, parses only
document 1, and re-emits document 2's bytes verbatim. That is deliberate:

  * `script_sha256` binds approval to the script (spec §10). Re-serialising
    beats on a status change would fire drift detection on churn we caused.
  * The storyboard skill writes deliberate formatting and comments, and
    `yaml.safe_dump` destroys both. `agsoc video approve` must not reflow an
    operator's script.
  * A beats syntax error must not stop you reading the status.

DO NOT read this file with `agenticsocial.frontmatter.parse`. It will appear to
work — it returns correct metadata and hands you the beats as an unparsed
string — which makes it a silent-wrong-answer trap rather than an error. Phase 3
owns the real beats parser.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ..models import VIDEO_TRANSITIONS, Status, assert_transition
from ..workspace import atomic_write
from .models import Episode, EpisodeError, Series

SUBDIRS = ("sources", "out", "probe")
_SEP = "\n---\n"


def _split(text: str) -> tuple[str, str | None]:
    """Split into (metadata text, verbatim remainder-after-separator).

    Returns `None` for the remainder when the file has no second document.
    Purely textual — nothing here parses YAML.
    """
    if not text.startswith("---\n"):
        return text, None
    end = text.find(_SEP, 3)
    if end == -1:
        return text[4:], None
    return text[4:end], text[end + len(_SEP) :]


def _parse_meta(meta_text: str, path: Path) -> dict:
    try:
        meta = yaml.safe_load(meta_text)
    except yaml.YAMLError as e:
        raise EpisodeError(f"{path}: cannot parse script metadata — {e}")
    if meta is None:
        return {}
    if not isinstance(meta, dict):
        raise EpisodeError(
            f"{path}: script metadata must be a mapping, got {type(meta).__name__}"
        )
    return meta


def _read_meta(path: Path) -> tuple[dict, str | None]:
    """Return (metadata, verbatim beats text). Never parses the beats."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise EpisodeError(f"{path}: cannot read script.yaml — {e}")
    meta_text, beats_text = _split(text)
    return _parse_meta(meta_text, path), beats_text


def _compose(meta: dict, beats_text: str | None) -> str:
    head = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    body = "beats: []\n" if beats_text is None else beats_text
    return f"---\n{head}\n---\n{body}"
```

- [ ] **Step 4: Update the four functions that used `_read` / `_dump`**

`create_episode` gains cleanup, mirroring `scaffold_series`:

```python
def create_episode(series: Series, ep_id: str) -> Episode:
    d = series.episodes_dir / ep_id
    if d.exists():
        raise EpisodeError(f"episode already exists: {series.slug}/{ep_id}")
    for sub in SUBDIRS:
        (d / sub).mkdir(parents=True)
    meta = {
        "episode": ep_id,
        "series": series.slug,
        "status": Status.DRAFT.value,
        "date_long": "",
        "pace": 1.0,
    }
    try:
        atomic_write(d / "script.yaml", _compose(meta, None))
    except BaseException:
        # Mirror scaffold_series: a half-built episode is invisible to
        # episode_ids, blocks re-creation, and reports two contradictory errors.
        import shutil

        shutil.rmtree(d, ignore_errors=True)
        raise
    return Episode(
        id=ep_id, series_slug=series.slug, dir=d, status=Status.DRAFT, meta=meta
    )
```

`load_episode` uses `_read_meta`:

```python
def load_episode(series: Series, ep_id: str) -> Episode:
    d = series.episodes_dir / ep_id
    path = d / "script.yaml"
    if not path.is_file():
        raise EpisodeError(
            f"no episode '{ep_id}' in {series.slug} — create it with `agsoc video new {ep_id}`"
        )
    meta, _ = _read_meta(path)
    raw = meta.get("status", Status.DRAFT.value)
    try:
        status = Status(raw)
    except ValueError:
        raise EpisodeError(
            f"{path}: invalid status '{raw}' — one of: "
            f"{', '.join(s.value for s in Status)}"
        )
    return Episode(id=ep_id, series_slug=series.slug, dir=d, status=status, meta=meta)
```

`episode_ids` matches `series_slugs`:

```python
def episode_ids(series: Series) -> list[str]:
    """Enumerate episode ids. Parses nothing, so it cannot fail on a corrupt
    episode — see D-018. Task 4's `except EpisodeError` depends on this."""
    if not series.episodes_dir.is_dir():
        return []
    return sorted(
        d.name for d in series.episodes_dir.iterdir() if (d / "script.yaml").is_file()
    )
```

`set_status` rewrites document 1 only:

```python
def set_status(episode: Episode, target: Status) -> None:
    assert_transition(episode.status, target, VIDEO_TRANSITIONS)
    meta, beats_text = _read_meta(episode.script_path)
    meta["status"] = target.value
    atomic_write(episode.script_path, _compose(meta, beats_text))
    episode.status = target
    episode.meta = meta
```

Delete `_dump` and `_read`. Nothing else should reference them — confirm with
`grep -rn "_dump\|_read(" src/`.

- [ ] **Step 5: Run everything, commit**

```bash
uv run pytest tests/test_video_episode.py -v 2>&1 | tail -40
uv run pytest 2>&1 | tail -5
git add src/agenticsocial/video/episode.py
git commit -m "fix: never parse or rewrite the beats document

Document 2 is now split textually and re-emitted verbatim. It was being
parsed, substituted with {beats: []} when it was not a mapping, and
written back -- destroying a bare-sequence beats block or a third
document silently.

YAML errors in metadata now raise EpisodeError, which Task 4's CLI will
catch; previously a corrupt script raised ScannerError and would have
tracebacked out of `agsoc video list`. create_episode cleans up a
partial directory, mirroring scaffold_series."
```

- [ ] **Step 6: Mutation check**

Apply each, run, `git checkout` between. All must fail:

1. `_compose` → re-serialise beats via `yaml.safe_dump(yaml.safe_load(beats_text))`
2. `_parse_meta` → drop the `try`, let `yaml.YAMLError` escape
3. `_parse_meta` → drop the non-mapping check
4. `episode_ids` → `.is_file()` back to `.exists()`
5. `create_episode` → remove the `rmtree` cleanup
6. `_split` → return `text, None` always (collapse to one document)

---

## Your report

`docs/superpowers/worklog/video/phase-01/task-3b-report.md`:

1. **What I changed.**
2. **TDD evidence** — RED (piped) and GREEN (both runs).
3. **Mutation results** — a row per mutant with the test that caught it.
4. **Step 1b confirmation** — did both existing tests still pass unmodified?
5. **Files changed**, both commit SHAs.
6. **Issues or concerns**, including:
   - Is textual splitting on `"\n---\n"` safe? A YAML block scalar could
     contain that sequence. Construct a `script.yaml` where it breaks, or argue
     convincingly that it cannot.
   - `_compose` writes `beats: []` when document 2 is absent. Is that right, or
     should absence be preserved as absence?
   - Does anything still lose data on a write path?
