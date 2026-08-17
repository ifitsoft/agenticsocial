# Task 3 Brief: Episode scaffolding

**Phase:** 1 · **Branch:** `feat/video-phase-01-scaffolding` · **Follows:** Task 2
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Ground rules

- **Two commits.** Failing tests first, then the implementation. Do not squash —
  a reviewer must verify the RED phase from git history, not from your report.
- **Pipe command output to a file and paste from it.** Do not hand-transcribe.
- Every code block below is authoritative — write exactly what it shows. Prose
  explains *why*. If prose and a code block disagree, follow the code block **and
  flag it in your report**; three earlier briefs of mine had exactly that defect.
- Do not modify any existing test. Do not add dependencies.
- Never stage anything under `docs/`. I edit worklog files while you work.
- Predicted test counts are my arithmetic, not gospel. Report what you observe.
- If the brief is wrong, implement as written and say so in your report.

## Context

Spec §5 and §10. An episode is one dated instalment of a series — the unit that
becomes one video. It composes *many* sources, which is why it gets its own
directory rather than fitting the existing one-source-to-N-variants shape.

**An episode always has a `script.yaml`, from the moment it is created.** Status
lives in that file, so there is never a moment where an episode exists but its
status has nowhere to be stored.

**`script.yaml` is a two-document YAML file.** Document 1 is metadata, document 2
is `beats:`. The spec's examples show `---` fences that look like the frontmatter
used elsewhere in this codebase — they are not. They are YAML document
separators, and `yaml.safe_load_all` reads them natively. This is deliberate:
`beats` is structured data, not a markdown body, so it should be parsed by the
YAML parser rather than by `frontmatter.parse`. **This task owns document 1 only;
Phase 3 builds the beat schema on document 2** and must find it intact.

`resolve_episode` mirrors the existing `Workspace.resolve_source`: exact match
wins, then unique substring, then an actionable error.

## Files

- Create: `src/agenticsocial/video/episode.py`
- Test: `tests/test_video_episode.py`

## Interfaces you must produce

`Series`, `Episode`, `EpisodeError` already exist in
`src/agenticsocial/video/models.py` from Task 2 — read that file first; do not
redefine them. Produce in `agenticsocial.video.episode`:

- `SUBDIRS: tuple[str, ...]`
- `create_episode(series: Series, ep_id: str) -> Episode`
- `load_episode(series: Series, ep_id: str) -> Episode`
- `resolve_episode(series: Series, query: str) -> Episode`
- `episode_ids(series: Series) -> list[str]`
- `list_episodes(series: Series) -> list[Episode]`
- `set_status(episode: Episode, target: Status) -> None`

### Why `episode_ids` exists — decision D-018

Task 2 raised this and it is now settled policy for the whole project:
**an addressed operation may raise; an enumerating operation must not die over
one bad member.**

`load_episode("2026-08-14")` names one episode — if it is corrupt, raise, there
is no partial answer. But `agsoc video list` is the *diagnostic* command: it is
what an operator runs precisely when something is broken and they do not know
what. A single malformed `script.yaml` must not make the one tool that could say
"14th is fine, 15th has a bad status on line 3" refuse to say anything.

So `episode_ids` is the cheap enumerator that cannot fail, and `list_episodes`
is the strict convenience defined **in terms of it** — one line, no duplicated
directory logic. The CLI (Task 4) will iterate `episode_ids` and load each one
inside a try/except, keeping presentation policy out of `episode.py`.

These take `Series`, not `Workspace`: a `Series` already carries `episodes_dir`,
so a workspace argument would be dead weight.

---

- [ ] **Step 1: Write the failing tests**

Create `tests/test_video_episode.py`:

```python
import pytest
import yaml

from agenticsocial.models import Status, TransitionError
from agenticsocial.video.episode import (
    create_episode,
    episode_ids,
    list_episodes,
    load_episode,
    resolve_episode,
    set_status,
)
from agenticsocial.video.models import EpisodeError
from agenticsocial.video.series import scaffold_series
from agenticsocial.workspace import Workspace


@pytest.fixture()
def ws(tmp_path):
    return Workspace.init(tmp_path / "workspace")


@pytest.fixture()
def series(ws):
    return scaffold_series(ws, "the-brief", name="The Brief")


def test_create_makes_the_full_layout(series):
    ep = create_episode(series, "2026-08-14")
    assert ep.dir == series.episodes_dir / "2026-08-14"
    assert ep.script_path.exists()
    assert ep.sources_dir.is_dir()
    assert ep.out_dir.is_dir()
    assert (ep.dir / "probe").is_dir()
    assert ep.status is Status.DRAFT
    assert ep.series_slug == "the-brief"


def test_created_script_is_two_yaml_documents(series):
    ep = create_episode(series, "2026-08-14")
    docs = list(yaml.safe_load_all(ep.script_path.read_text(encoding="utf-8")))
    assert len(docs) == 2
    assert docs[0]["episode"] == "2026-08-14"
    assert docs[0]["series"] == "the-brief"
    assert docs[0]["status"] == "draft"
    assert docs[1] == {"beats": []}


def test_create_is_not_destructive(series):
    create_episode(series, "2026-08-14")
    with pytest.raises(EpisodeError, match="already exists"):
        create_episode(series, "2026-08-14")


def test_load_returns_status_from_disk(series):
    create_episode(series, "2026-08-14")
    assert load_episode(series, "2026-08-14").status is Status.DRAFT


def test_load_missing_episode_is_actionable(series):
    with pytest.raises(EpisodeError, match="agsoc video new"):
        load_episode(series, "2026-01-01")


def test_invalid_status_names_the_file_and_valid_values(series):
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "---\nepisode: 2026-08-14\nseries: the-brief\nstatus: banana\n---\nbeats: []\n",
        encoding="utf-8",
    )
    with pytest.raises(EpisodeError) as excinfo:
        load_episode(series, "2026-08-14")
    assert "banana" in str(excinfo.value)
    assert "rendering" in str(excinfo.value)


def test_load_tolerates_a_single_document_script(series):
    """A hand-edited script that lost its second document must not crash."""
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "episode: 2026-08-14\nseries: the-brief\nstatus: draft\n", encoding="utf-8"
    )
    assert load_episode(series, "2026-08-14").status is Status.DRAFT


def test_load_tolerates_an_empty_script(series):
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text("", encoding="utf-8")
    assert load_episode(series, "2026-08-14").status is Status.DRAFT


def test_resolve_exact_id_wins(series):
    create_episode(series, "2026-08-14")
    assert resolve_episode(series, "2026-08-14").id == "2026-08-14"


def test_resolve_by_unique_substring(series):
    create_episode(series, "2026-08-14")
    assert resolve_episode(series, "08-14").id == "2026-08-14"


def test_resolve_ambiguous_lists_candidates(series):
    create_episode(series, "2026-08-14")
    create_episode(series, "2026-08-15")
    with pytest.raises(EpisodeError) as excinfo:
        resolve_episode(series, "2026-08")
    assert "2026-08-14" in str(excinfo.value)
    assert "2026-08-15" in str(excinfo.value)


def test_resolve_no_match_is_actionable(series):
    create_episode(series, "2026-08-14")
    with pytest.raises(EpisodeError, match="agsoc video list"):
        resolve_episode(series, "1999")


def test_resolve_a_healthy_episode_despite_a_corrupt_neighbour(series):
    """D-018: matching runs over ids, so only the resolved episode is loaded."""
    create_episode(series, "2026-08-14")
    bad = create_episode(series, "2026-08-15")
    bad.script_path.write_text("status: banana\n", encoding="utf-8")
    assert resolve_episode(series, "2026-08-14").id == "2026-08-14"


def test_resolving_the_corrupt_episode_itself_still_raises(series):
    bad = create_episode(series, "2026-08-15")
    bad.script_path.write_text("status: banana\n", encoding="utf-8")
    with pytest.raises(EpisodeError, match="banana"):
        resolve_episode(series, "2026-08-15")


def test_list_episodes_is_sorted(series):
    create_episode(series, "2026-08-15")
    create_episode(series, "2026-08-14")
    assert [e.id for e in list_episodes(series)] == ["2026-08-14", "2026-08-15"]


def test_list_episodes_when_none(series):
    assert list_episodes(series) == []


def test_list_episodes_skips_dirs_without_a_script(series):
    create_episode(series, "2026-08-14")
    (series.episodes_dir / "junk").mkdir()
    assert [e.id for e in list_episodes(series)] == ["2026-08-14"]


def test_episode_ids_survives_a_corrupt_episode(series):
    """D-018: enumeration must not die over one bad member. `agsoc video list`
    is the diagnostic command — it runs precisely when something is broken."""
    create_episode(series, "2026-08-14")
    bad = create_episode(series, "2026-08-15")
    bad.script_path.write_text("status: banana\n", encoding="utf-8")
    assert episode_ids(series) == ["2026-08-14", "2026-08-15"]


def test_list_episodes_is_strict_about_a_corrupt_episode(series):
    """The strict counterpart: loading everything fails loudly. The CLI uses
    episode_ids + per-episode load instead."""
    create_episode(series, "2026-08-14")
    bad = create_episode(series, "2026-08-15")
    bad.script_path.write_text("status: banana\n", encoding="utf-8")
    with pytest.raises(EpisodeError, match="banana"):
        list_episodes(series)


def test_episode_ids_on_empty_series(series):
    assert episode_ids(series) == []


def test_set_status_persists_and_preserves_beats(series):
    ep = create_episode(series, "2026-08-14")
    set_status(ep, Status.IN_REVIEW)
    assert load_episode(series, "2026-08-14").status is Status.IN_REVIEW
    docs = list(yaml.safe_load_all(ep.script_path.read_text(encoding="utf-8")))
    assert docs[1] == {"beats": []}


def test_set_status_updates_the_in_memory_episode(series):
    ep = create_episode(series, "2026-08-14")
    set_status(ep, Status.IN_REVIEW)
    assert ep.status is Status.IN_REVIEW


def test_set_status_does_not_lose_beats_written_by_a_later_phase(series):
    """Phase 3 writes real beats into document 2. A status change must not eat them."""
    ep = create_episode(series, "2026-08-14")
    ep.script_path.write_text(
        "---\nepisode: 2026-08-14\nseries: the-brief\nstatus: draft\n"
        "---\nbeats:\n- type: statement\n  text: hello\n",
        encoding="utf-8",
    )
    reloaded = load_episode(series, "2026-08-14")
    set_status(reloaded, Status.IN_REVIEW)
    docs = list(yaml.safe_load_all(ep.script_path.read_text(encoding="utf-8")))
    assert docs[1]["beats"] == [{"type": "statement", "text": "hello"}]


def test_set_status_enforces_the_video_table(series):
    ep = create_episode(series, "2026-08-14")
    with pytest.raises(TransitionError):
        set_status(ep, Status.RENDERING)


def test_set_status_allows_the_approved_render_path(series):
    ep = create_episode(series, "2026-08-14")
    set_status(ep, Status.IN_REVIEW)
    set_status(ep, Status.APPROVED)
    set_status(ep, Status.RENDERING)
    assert load_episode(series, "2026-08-14").status is Status.RENDERING


def test_a_rejected_transition_does_not_touch_the_file(series):
    ep = create_episode(series, "2026-08-14")
    before = ep.script_path.read_text(encoding="utf-8")
    with pytest.raises(TransitionError):
        set_status(ep, Status.RENDERING)
    assert ep.script_path.read_text(encoding="utf-8") == before
    assert ep.status is Status.DRAFT
```

- [ ] **Step 2: Run and confirm they fail**

```bash
uv run pytest tests/test_video_episode.py 2>&1 | tail -15
```

Expected: collection error,
`ModuleNotFoundError: No module named 'agenticsocial.video.episode'`

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_video_episode.py
git commit -m "test: specify episode scaffolding and video status persistence"
```

- [ ] **Step 4: Implement**

Create `src/agenticsocial/video/episode.py`:

```python
"""Episode directories and the episode status lifecycle.

`script.yaml` is a two-document YAML file: document 1 is metadata (episode id,
series, status, pace), document 2 is `beats:`. Phase 1 owns document 1 only —
document 2 must survive every write here untouched, because Phase 3 fills it.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from ..models import VIDEO_TRANSITIONS, Status, assert_transition
from ..workspace import atomic_write
from .models import Episode, EpisodeError, Series

SUBDIRS = ("sources", "out", "probe")


def _dump(meta: dict, beats_doc: dict) -> str:
    head = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    body = yaml.safe_dump(beats_doc, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{head}\n---\n{body}\n"


def _read(path: Path) -> tuple[dict, dict]:
    docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    meta = docs[0] if len(docs) > 0 and isinstance(docs[0], dict) else {}
    beats = docs[1] if len(docs) > 1 and isinstance(docs[1], dict) else {"beats": []}
    return meta, beats


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
    atomic_write(d / "script.yaml", _dump(meta, {"beats": []}))
    return Episode(
        id=ep_id, series_slug=series.slug, dir=d, status=Status.DRAFT, meta=meta
    )


def load_episode(series: Series, ep_id: str) -> Episode:
    d = series.episodes_dir / ep_id
    path = d / "script.yaml"
    if not path.exists():
        raise EpisodeError(
            f"no episode '{ep_id}' in {series.slug} — create it with `agsoc video new {ep_id}`"
        )
    meta, _ = _read(path)
    raw = meta.get("status", Status.DRAFT.value)
    try:
        status = Status(raw)
    except ValueError:
        raise EpisodeError(
            f"{path}: invalid status '{raw}' — one of: "
            f"{', '.join(s.value for s in Status)}"
        )
    return Episode(id=ep_id, series_slug=series.slug, dir=d, status=status, meta=meta)


def episode_ids(series: Series) -> list[str]:
    """Enumerate episode ids. Cannot fail on a corrupt episode — see D-018."""
    if not series.episodes_dir.is_dir():
        return []
    return sorted(
        d.name for d in series.episodes_dir.iterdir() if (d / "script.yaml").exists()
    )


def list_episodes(series: Series) -> list[Episode]:
    """Load every episode. Strict: raises if ANY episode is malformed.

    For partial results — which is what `agsoc video list` needs — iterate
    `episode_ids()` and load each inside a try/except. See D-018.
    """
    return [load_episode(series, i) for i in episode_ids(series)]


def resolve_episode(series: Series, query: str) -> Episode:
    """Resolve a query to one episode, loading ONLY the one that matches.

    Matching runs over ids, not loaded episodes, so a corrupt episode cannot
    stop you addressing a healthy one (D-018). It still raises if the episode
    you actually asked for is the corrupt one — that is an addressed operation.
    """
    ids = episode_ids(series)
    if query in ids:
        return load_episode(series, query)
    matches = [i for i in ids if query.lower() in i.lower()]
    if len(matches) > 1:
        raise EpisodeError(f"'{query}' matches multiple episodes: {', '.join(matches)}")
    if not matches:
        raise EpisodeError(
            f"no episode matching '{query}' in {series.slug} — see `agsoc video list`"
        )
    return load_episode(series, matches[0])


def set_status(episode: Episode, target: Status) -> None:
    assert_transition(episode.status, target, VIDEO_TRANSITIONS)
    meta, beats = _read(episode.script_path)
    meta["status"] = target.value
    atomic_write(episode.script_path, _dump(meta, beats))
    episode.status = target
    episode.meta = meta
```

Note the ordering in `set_status`: `assert_transition` runs **before** any read
or write, so a rejected transition leaves the file byte-identical. That is what
`test_a_rejected_transition_does_not_touch_the_file` pins.

- [ ] **Step 5: Run everything**

```bash
uv run pytest tests/test_video_episode.py -v 2>&1 | tail -30
uv run pytest 2>&1 | tail -5
```

Expected: 27 passed in the new file, and a full-suite total of the Task 2 total
(130) plus those. Report the numbers you observe rather than the ones I predict —
my arithmetic has been wrong before and adjusting code to hit a predicted count
would be the worst possible response.

- [ ] **Step 6: Commit the implementation**

```bash
git add src/agenticsocial/video/episode.py
git commit -m "feat: add episode scaffolding and video status persistence"
```

---

## Your report

Write `docs/superpowers/worklog/video/phase-01/task-3-report.md`:

1. **What I implemented.**
2. **TDD evidence** — `### RED` (piped, from the test-only commit) and `### GREEN`
   (both runs, piped).
3. **Files changed** and both commit SHAs.
4. **Self-review findings.**
5. **Issues or concerns**, including your view on these three:
   - D-018 splits enumeration (`episode_ids`, cannot fail) from strict loading
     (`list_episodes`, raises), and `resolve_episode` matches over ids so it
     loads only what it resolves. Does the split hold up, or does it just move
     the problem into Task 4's CLI? Is `list_episodes` now dead weight — is there
     any caller who genuinely wants "all of them, or an exception"?
   - Two-document YAML versus a single document with a top-level `beats` key.
     Phase 3 has to live with this. Would you change it now, while it is cheap?
   - `_read` silently substitutes `{"beats": []}` for a malformed second
     document. Is that tolerance or is it data loss waiting to happen, given
     `set_status` then writes that substitute back to disk?
