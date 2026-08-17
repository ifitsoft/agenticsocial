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
