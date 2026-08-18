"""The coverage ledger: has this series told this story before?

Ported from `engine/coverage.mjs` (retired in Phase 11), with one change of
scope: the ledger is **per-series**. `engine/coverage.json` was a single file
shared by every series, and two series sharing one ledger means one series'
history suppresses the other's stories — a story silently dropped, which is the
inverse of the failure the ledger exists to prevent and just as bad.

Three properties carried over deliberately from D-112:

1. **The matcher is one-directional.** `squashed` strips every non-alphanumeric
   character from BOTH the term and the haystack and asks for containment, so
   the transformation can only ever *add* a match, never drop one. `gemini-3.7`,
   `gemini 3.7`, `gemini-3-7-flash` and `gemini3.7` are one query. Its cost is
   false positives (`aiact` finds *EU AI Act*), and that is the correct
   direction to be wrong in for a check whose failure mode is re-telling a
   story as new.
2. **Containment, not token equality.** `watermark` still finds *watermarking*
   and `llm` still finds *LiteLLM*. Matching whole tokens would have fixed
   `gemini-3.7` and lost those — one silent miss traded for others.
3. **The message never says "safe".** A search that finds nothing knows one
   thing: the string is not there. The ledger is also written after an episode
   ships, so absence is bounded twice over. Say both, and do not say "safe".

`spaced` survives as a TOKENISER — how a term is split for the "related, and
not a hit" pointer — and not as a matcher (D-112: the second pass was dead code
dressed as a second opinion).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models import Status
from ..workspace import atomic_write
from .models import Episode, Series

LEDGER_NAME = "coverage.json"

# What a term is matched against. Everything a person might type when they mean
# "this story": its id, what the card said, the operator's note, the entities
# the checker extracted, and where it came from.
HAYSTACK_FIELDS = ("id", "title", "note", "act", "angle")

# A derived title is a whole card's text; a ledger row an operator can read is
# one line. Truncation is display-only — the entities and sources carry the
# matchable atoms, so a long tail is never the only place a product name lives.
MAX_TITLE = 240
MAX_ID = 72


class CoverageError(Exception):
    pass


def squashed(s: str) -> str:
    """Lowercase, and every non-alphanumeric character removed. The matcher."""
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def spaced(s: str) -> str:
    """Lowercase, separators collapsed to single spaces. The tokeniser."""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def haystack(story: dict) -> str:
    parts = [str(story.get(f, "") or "") for f in HAYSTACK_FIELDS]
    for key in ("entities", "sources"):
        value = story.get(key) or []
        if isinstance(value, list):
            parts.extend(str(v) for v in value)
    return " ".join(parts)


def matches(story: dict, term: str) -> bool:
    t = squashed(term)
    # A term of pure punctuation normalises to nothing, and an empty needle is a
    # substring of every string — the loosest possible matcher, arrived at by
    # accident. Nothing matches nothing.
    if not t:
        return False
    return t in squashed(haystack(story))


# --- reading and writing ---------------------------------------------------------------


def ledger_path(series: Series) -> Path:
    return series.dir / LEDGER_NAME


def load_ledger(series: Series) -> dict:
    path = ledger_path(series)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CoverageError(
            f"no {LEDGER_NAME} in {series.dir} — a series scaffolded before "
            "Phase 11 can be given one by copying the template from "
            "`agsoc series new`, or migrated with `agsoc coverage migrate`"
        )
    except OSError as e:
        raise CoverageError(f"{path}: cannot read the ledger — {e}")
    except json.JSONDecodeError as e:
        raise CoverageError(f"{path}: malformed {LEDGER_NAME} — {e}")
    return validate_ledger(raw, path)


def validate_ledger(raw: Any, where: Any) -> dict:
    if not isinstance(raw, dict):
        raise CoverageError(f"{where}: the ledger must be a mapping")
    episodes = raw.get("episodes", [])
    if not isinstance(episodes, list):
        raise CoverageError(f"{where}: `episodes` must be a list")
    for i, ep in enumerate(episodes):
        if not isinstance(ep, dict):
            raise CoverageError(f"{where}: episode {i} must be a mapping")
        if not isinstance(ep.get("date", ""), str):
            raise CoverageError(f"{where}: episode {i} has a non-string `date`")
        stories = ep.get("stories", [])
        if not isinstance(stories, list) or any(not isinstance(s, dict) for s in stories):
            raise CoverageError(
                f"{where}: episode {ep.get('date', i)} `stories` must be a list of mappings"
            )
    raw["episodes"] = episodes
    return raw


def save_ledger(series: Series, ledger: dict) -> None:
    atomic_write(
        ledger_path(series),
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n",
    )


def all_stories(ledger: dict) -> list[dict]:
    """Every story, newest first, each carrying the date of its episode."""
    out = [
        {**s, "date": ep.get("date", "")}
        for ep in ledger["episodes"]
        for s in ep.get("stories", [])
    ]
    out.sort(key=lambda s: s["date"], reverse=True)
    return out


def counts(ledger: dict) -> tuple[int, int]:
    return len(all_stories(ledger)), len(ledger["episodes"])


# --- check ------------------------------------------------------------------------------


@dataclass(frozen=True)
class TermResult:
    term: str
    found: list[dict] = field(default_factory=list)
    related: list[tuple[str, int]] = field(default_factory=list)
    elsewhere: list[tuple[str, int]] = field(default_factory=list)


def related_terms(stories: list[dict], term: str) -> list[tuple[str, int]]:
    """Pieces of an absent term that the ledger does know.

    The step the runner who caught D-112 had to think of unaided: re-run the
    bare vendor or product word. A pointer, not a hit — it never moves a count.
    """
    whole = spaced(term)
    words = [
        w
        for w in dict.fromkeys(whole.split(" "))
        # Four characters, not three: a fragment like `pro` out of `v4-pro`
        # matches *profiles* and *improve* and points at nothing. A pointer that
        # is usually noise gets skipped, and then it is not a pointer.
        if len(w) >= 4 and not w.isdigit() and w != whole
    ]
    hits = [(w, sum(1 for s in stories if matches(s, w))) for w in words]
    return [(w, n) for w, n in hits if n > 0]


def check_terms(
    ledger: dict, terms: list[str], others: dict[str, dict] | None = None
) -> list[TermResult]:
    """One result per term. `others` maps a neighbouring series' slug to its
    ledger; its matches are reported and never counted (R3)."""
    stories = all_stories(ledger)
    results = []
    for term in terms:
        found = [s for s in stories if matches(s, term)]
        elsewhere = []
        for slug, other in (others or {}).items():
            n = sum(1 for s in all_stories(other) if matches(s, term))
            if n:
                elsewhere.append((slug, n))
        results.append(
            TermResult(
                term=term,
                found=found,
                related=[] if found else related_terms(stories, term),
                elsewhere=elsewhere,
            )
        )
    return results


# --- add: what a story is ----------------------------------------------------------------


def _slug(text: str) -> str:
    s = spaced(text).replace(" ", "-")
    return s[:MAX_ID].rstrip("-") or "story"


def _one_line(text: str) -> str:
    line = " · ".join(part.strip() for part in text.splitlines() if part.strip())
    return line[: MAX_TITLE - 1] + "…" if len(line) > MAX_TITLE else line


def _manifest(episode: Episode) -> dict:
    path = episode.sources_dir / "_manifest.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # A missing or broken manifest costs the ledger a hostname, not an
        # entry. The corpus is the verifier's problem, not the ledger's.
        return {}
    return raw if isinstance(raw, dict) else {}


def _host(url: Any) -> str:
    if not isinstance(url, str):
        return ""
    m = re.match(r"^[a-z][a-z0-9+.-]*://([^/?#]+)", url.strip(), re.I)
    host = m.group(1) if m else ""
    return host.split("@")[-1].split(":")[0].lower()


def derive_stories(script, manifest: dict) -> list[dict]:
    """One entry per beat that asserts something about the world.

    **What a story is, decided.** Not the operator's memory of the day and not
    the beat text alone: an entry is *what the episode put on screen*, plus the
    entities `claims.py` already extracted from it and the source it cited.
    Three reasons.

    - `check` matches against what is *in* the ledger. The entity atoms are the
      product and vendor names an author will type six months from now
      (`DeepSeek`, `Gemini 3.7 Flash`) — the exact strings D-112's defect was
      about — and they are derived by the same code that verified the beat,
      so the ledger and the claim ledger cannot drift apart.
    - Beats that assert nothing (`title`, `signoff`) are exempt here for the
      same reason they are exempt from citation. A ledger row for "Five stories
      from the last 24 hours" matches every future episode and points at none.
    - It is derivable, so it is *actually written*. The old ledger was
      hand-maintained after each episode, which is why the storyboard skill had
      to tell authors there was no way to record an update.
    """
    from .claims import EXEMPT_TYPES, beat_text

    out: list[dict] = []
    seen: dict[str, dict] = {}
    for beat in script.beats:
        if beat.type in EXEMPT_TYPES:
            continue
        text = _one_line(beat_text(beat)) if beat.type not in ("custom",) else ""
        title = text or f"{beat.type} beat {beat.index + 1}"
        story = {
            "id": _slug(title),
            "title": title,
            "act": beat.act,
            "beat": beat.type,
            "entities": _entities(beat),
            "sources": _sources(beat, manifest),
        }
        if story["id"] in seen:
            # Two beats on one story: merge rather than write two rows with one
            # id, which would make `list --ids` lie about how many stories there
            # are without adding anything a search could find.
            prior = seen[story["id"]]
            for key in ("entities", "sources"):
                prior[key] = sorted(set(prior[key]) | set(story[key]))
            continue
        seen[story["id"]] = story
        out.append(story)
    return out


def _entities(beat) -> list[str]:
    from .claims import beat_text
    from .claims import atoms as atoms_of

    if beat.type == "custom":
        return []
    return sorted({a.value for a in atoms_of(beat_text(beat)) if a.kind == "entity"})


def _sources(beat, manifest: dict) -> list[str]:
    out = []
    if beat.src:
        out.append(beat.src)
        entry = manifest.get(beat.src)
        host = _host(entry.get("url")) if isinstance(entry, dict) else ""
        if host:
            out.append(host)
    return out


def render_record(episode: Episode) -> dict:
    record = episode.meta.get("render")
    return record if isinstance(record, dict) else {}


def episode_entry(episode: Episode, script, note: str = "") -> dict:
    """The ledger row for one rendered episode."""
    record = render_record(episode)
    entry: dict[str, Any] = {"date": episode.id}
    if record.get("file"):
        entry["video"] = record["file"]
    if isinstance(record.get("runtime_sec"), (int, float)):
        entry["runtimeSec"] = record["runtime_sec"]
    entry["recorded_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    if note:
        entry["note"] = note
    entry["stories"] = derive_stories(script, _manifest(episode))
    return entry


def assert_recordable(episode: Episode) -> None:
    """`add` records after render (R5), and refuses before it.

    An episode still in review has not told anyone anything, and an entry for it
    would suppress a story the series never ran. The bound in the other
    direction — a render that is discarded and never posted — is why `add` is a
    command the operator runs and not a side effect of `render`.
    """
    if episode.status is not Status.RENDERED:
        raise CoverageError(
            f"{episode.id} is {episode.status.value}, not rendered — the ledger "
            "records what the series actually put out. Render it first "
            f"(`agsoc video render {episode.id}`), then record it."
        )
    if not render_record(episode):
        raise CoverageError(
            f"{episode.id} is marked rendered but carries no render record in "
            "script.yaml. Re-render it rather than record an episode nothing "
            "can account for."
        )


def add_entry(ledger: dict, entry: dict, replace: bool = False) -> dict:
    existing = [e for e in ledger["episodes"] if e.get("date") == entry["date"]]
    if existing and not replace:
        raise CoverageError(
            f"{entry['date']} is already in the ledger ({len(existing[0].get('stories', []))} "
            "stories). Re-record it with --replace, or leave the record that is "
            "already there."
        )
    episodes = [e for e in ledger["episodes"] if e.get("date") != entry["date"]]
    episodes.append(entry)
    episodes.sort(key=lambda e: e.get("date", ""))
    ledger["episodes"] = episodes
    return ledger


# --- migration ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MigrationReport:
    episodes_moved: list[str]
    episodes_skipped: list[str]
    stories_before: int
    stories_after: int
    stories_source: int


def load_legacy(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CoverageError(f"no such ledger: {path}")
    except OSError as e:
        raise CoverageError(f"{path}: cannot read — {e}")
    except json.JSONDecodeError as e:
        raise CoverageError(f"{path}: malformed JSON — {e}")
    return validate_ledger(raw, path)


def migrate(ledger: dict, legacy: dict) -> tuple[dict, MigrationReport]:
    """Merge a legacy ledger into a series ledger, losing nothing.

    A migration that silently drops an entry is worse than no migration at all,
    because the failure mode is a story re-told as new. So: episodes are matched
    by date, an identical date is skipped (the migration is idempotent, which is
    what lets an operator who is unsure just run it), a *differing* date is
    refused by name rather than resolved by guess, and the story count is
    asserted before the result is handed back.
    """
    before_stories, _ = counts(ledger)
    seen: set = set()
    for ep in legacy["episodes"]:
        date = ep.get("date")
        if date in seen:
            raise CoverageError(
                f"the source holds {date} twice. Nothing was written — merging "
                "it would put one date in the ledger twice, and `coverage "
                "episode` would then show one of the two and hide the other."
            )
        seen.add(date)
    by_date = {e.get("date"): e for e in ledger["episodes"]}
    moved, skipped = [], []
    episodes = list(ledger["episodes"])
    for ep in legacy["episodes"]:
        date = ep.get("date")
        mine = by_date.get(date)
        if mine is None:
            episodes.append(ep)
            moved.append(date)
        elif mine == ep:
            skipped.append(date)
        else:
            raise CoverageError(
                f"{date} is already in this series' ledger with different "
                "content. Nothing was written. Reconcile the two entries by "
                "hand — picking a winner here would lose whichever entry was "
                "not picked, and a lost entry is a story re-told as new."
            )
    episodes.sort(key=lambda e: e.get("date", ""))
    merged = {**ledger, "episodes": episodes}
    after_stories, _ = counts(merged)
    source_stories, _ = counts(legacy)
    moved_stories = sum(
        len(e.get("stories", [])) for e in legacy["episodes"] if e.get("date") in moved
    )
    if after_stories != before_stories + moved_stories:
        # Unreachable by construction; asserted anyway because the one thing
        # this function must never do quietly is lose a row.
        raise CoverageError(
            f"migration arithmetic does not balance: {before_stories} + "
            f"{moved_stories} != {after_stories}. Nothing was written."
        )
    return merged, MigrationReport(
        episodes_moved=moved,
        episodes_skipped=skipped,
        stories_before=before_stories,
        stories_after=after_stories,
        stories_source=source_stories,
    )
