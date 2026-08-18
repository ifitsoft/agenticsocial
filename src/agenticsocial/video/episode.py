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

import hashlib
import re
from dataclasses import replace
from pathlib import Path

import yaml

from ..models import VIDEO_TRANSITIONS, Status, assert_transition
from ..workspace import atomic_write
from .models import Episode, EpisodeError, Series
from ..workspace import assert_safe_name

# One length limit, not two. A second `= 64` here drifts from series.py's the
# first time either is tuned — the D-036 pattern that has produced five defects.
# series.py does not import this module, so this direction is the acyclic one.
from .series import MAX_NAME_LEN as MAX_ID_LEN

SUBDIRS = ("sources", "out", "probe")

EPISODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*$")

_DOC_START_RE = re.compile(r"\A---[ \t]*(\r\n|\r|\n)")
_SEP_RE = re.compile(r"(\r\n|\r|\n)---[ \t]*(\r\n|\r|\n)")


def _split(text: str) -> tuple[str, str | None, str]:
    """Split into (metadata text, verbatim remainder, newline).

    Purely textual — nothing here parses YAML. The separator's trailing newline
    is consumed by the match, so the remainder begins at the first byte the
    operator wrote. Do NOT reintroduce a lookahead and compute the offset from
    the leading newline's length: the two newlines can differ (CRLF metadata,
    LF beats) and that arithmetic silently ate the first byte of beats. See
    D-033.

    The search begins at `start.end() - len(nl)` so the newline ending the
    opening `---` can serve as the separator's leading newline when the
    metadata document is empty.
    """
    start = _DOC_START_RE.match(text)
    if not start:
        return text, None, "\n"
    nl = start.group(1)
    sep = _SEP_RE.search(text, start.end() - len(nl))
    if not sep:
        return text[start.end() :], None, nl
    return text[start.end() : sep.start()], text[sep.end() :], nl


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
    except UnicodeDecodeError as e:
        raise EpisodeError(
            f"{path}: script.yaml is not valid UTF-8 — {e}. "
            "Re-save it as UTF-8; agsoc writes and expects UTF-8 everywhere."
        )
    meta_text, beats_text, nl = _split(text)
    meta = _parse_meta(meta_text, path)
    if beats_text is None and "beats" in meta:
        raise EpisodeError(
            f"{path}: `beats` appears in the metadata document. script.yaml needs "
            "a `---` separator line between the metadata and the beats document."
        )
    return meta, beats_text, nl


def read_script(path: Path) -> tuple[dict, str | None, str]:
    """Read `script.yaml`: (metadata, verbatim beats text, newline).

    READ ONLY. The beats text is returned exactly as written and must never be
    re-serialised — see this module's docstring and DECISIONS D-026.
    """
    return _read_meta(path)


def _compose(meta: dict, beats_text: str | None, nl: str = "\n") -> str:
    head = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    head = head.replace("\n", nl)
    body = f"beats: []{nl}" if beats_text is None else beats_text
    return f"---{nl}{head}{nl}---{nl}{body}"


def create_episode(series: Series, ep_id: str) -> Episode:
    assert_safe_name(ep_id, "episode id", EpisodeError)
    if len(ep_id) > MAX_ID_LEN:
        raise EpisodeError(
            f"episode id is too long ({len(ep_id)} characters, limit {MAX_ID_LEN})"
        )
    if not EPISODE_ID_RE.match(ep_id):
        raise EpisodeError(
            f"invalid episode id {ep_id!r} — use lowercase letters, digits, dots "
            "and hyphens, starting with a letter or digit (ids become directory names)"
        )
    d = series.episodes_dir / ep_id
    if d.exists() or d.is_symlink():
        raise EpisodeError(f"episode already exists: {series.slug}/{ep_id}")
    try:
        d.mkdir(parents=True)  # atomic claim; FileExistsError if we lost
    except FileExistsError:
        raise EpisodeError(f"episode already exists: {series.slug}/{ep_id}")
    try:
        for sub in SUBDIRS:
            (d / sub).mkdir()
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


def load_episode(series: Series, ep_id: str) -> Episode:
    assert_safe_name(ep_id, "episode id", EpisodeError)
    d = series.episodes_dir / ep_id
    path = d / "script.yaml"
    if not path.is_file():
        raise EpisodeError(
            f"no episode '{ep_id}' in {series.slug} — create it with `agsoc video new {ep_id}`"
        )
    meta, _, _ = _read_meta(path)
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
    assert_safe_name(query, "episode id", EpisodeError)
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


def beats_sha256(episode: Episode) -> str:
    """sha256 over the BEATS DOCUMENT's bytes — spec §10's `script_sha256`.

    Not the whole file, and the difference is load-bearing. The file also holds
    the metadata document, which carries `status` and the approval record
    itself, so a whole-file digest is either self-invalidating (approve writes
    the digest into the bytes it just hashed) or invalidated by the pipeline's
    own next move — `approved → rendering` rewrites the status, and every drift
    check after it would report a change nobody made. This module's docstring
    says the same thing from the other side: beats are re-emitted verbatim on a
    status change precisely so approval survives one.

    What it therefore does NOT cover is the metadata document: `pace` scales
    every hold and `date_long` is on screen. `approve` records `pace` beside the
    digest rather than pretending the hash covers it.

    Hashed as read — `read_script` opens with `newline=""`, so CRLF stays CRLF
    and the digest is over the operator's bytes, not Python's translation of
    them (D-031).
    """
    _, beats_text, _ = _read_meta(episode.script_path)
    if beats_text is None:
        raise EpisodeError(
            f"{episode.script_path}: no beats document — script.yaml needs a "
            "`---` separator line, then `beats:`"
        )
    return hashlib.sha256(beats_text.encode("utf-8")).hexdigest()


def set_status(episode: Episode, target: Status, record: dict | None = None) -> Episode:
    """Move an episode to `target`, gated on the status ON DISK.

    `record` is extra metadata to write IN THE SAME WRITE — the approval record,
    today. It is a parameter rather than a second function because D-059's root
    cause was a second, ungated status writer: an `approve` that called
    `set_status` and then wrote its record separately would be two writes, and
    a crash between them leaves an approved episode nobody signed. It cannot
    carry a status: `status` is set from `target` after `record` is merged, so
    `{"status": ...}` in here is overwritten rather than honoured.

    The gate is checked against the status ON DISK, not against `episode.status`.
    A caller holding a stale Episode must not be able to reach RENDERING from a
    file that says `draft` — spec §8.4 and §10 exist to make rendering
    unreachable without a human, and an in-memory check is not that guarantee.

    Returns a NEW Episode; the argument is unchanged. See workspace.set_status
    for why the dataclass is frozen.
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
    meta.update(record or {})
    meta["status"] = target.value
    atomic_write(episode.script_path, _compose(meta, beats_text, nl))
    return replace(episode, status=target, meta=meta)
