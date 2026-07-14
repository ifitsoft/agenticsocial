"""Deterministic text helpers: slugs, thread splitting, X-weighted length."""
from __future__ import annotations

import re

TWEET_LIMIT = 280
URL_WEIGHT = 23  # X wraps every URL in t.co, which always counts as 23 chars
THREAD_DELIM = "---tweet---"

_URL_RE = re.compile(r"https?://\S+")


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60].rstrip("-") or "untitled"


def split_thread(body: str) -> list[str]:
    """Split on lines containing only the delimiter; drop empty segments."""
    segments: list[list[str]] = [[]]
    for line in body.splitlines():
        if line.strip() == THREAD_DELIM:
            segments.append([])
        else:
            segments[-1].append(line)
    tweets = ["\n".join(seg).strip() for seg in segments]
    return [t for t in tweets if t]


def weighted_length(text: str) -> int:
    """Approximate X character weighting: URLs are 23, everything else 1.

    (CJK double-weighting is not modeled in v1.)
    """
    stripped, n_urls = _URL_RE.subn("", text)
    return len(stripped) + n_urls * URL_WEIGHT
