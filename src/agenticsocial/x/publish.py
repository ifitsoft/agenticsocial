"""Thread validation and (in Task 11) resume-safe publishing."""
from __future__ import annotations

from ..textutils import TWEET_LIMIT, split_thread, weighted_length


class ValidationError(Exception):
    pass


def validate_thread(body: str) -> list[str]:
    tweets = split_thread(body)
    if not tweets:
        raise ValidationError("variant body is empty")
    for i, t in enumerate(tweets, 1):
        n = weighted_length(t)
        if n > TWEET_LIMIT:
            raise ValidationError(
                f"tweet {i} is {n} weighted chars (limit {TWEET_LIMIT}); URLs count as 23"
            )
    return tweets


def format_review(tweets: list[str]) -> str:
    lines = []
    for i, t in enumerate(tweets, 1):
        n = weighted_length(t)
        flag = "  ⚠ OVER LIMIT" if n > TWEET_LIMIT else ""
        lines.append(f"── tweet {i}/{len(tweets)} · {n}/{TWEET_LIMIT} chars{flag}")
        lines.append(t)
        lines.append("")
    return "\n".join(lines)
