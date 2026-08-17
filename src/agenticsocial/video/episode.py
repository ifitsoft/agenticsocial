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


def episode_ids(series: Series) -> list[str]:
    """Enumerate episode ids. Parses nothing, so it cannot fail on a corrupt
    episode — see D-018. Task 4's `except EpisodeError` depends on this."""
    if not series.episodes_dir.is_dir():
        return []
    return sorted(
        d.name for d in series.episodes_dir.iterdir() if (d / "script.yaml").is_file()
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
    meta, beats_text = _read_meta(episode.script_path)
    meta["status"] = target.value
    atomic_write(episode.script_path, _compose(meta, beats_text))
    episode.status = target
    episode.meta = meta
