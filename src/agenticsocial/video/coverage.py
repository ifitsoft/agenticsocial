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
