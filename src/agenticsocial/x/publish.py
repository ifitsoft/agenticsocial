"""Thread validation and (in Task 11) resume-safe publishing."""
from __future__ import annotations

from ..models import Status, Variant
from ..textutils import TWEET_LIMIT, split_thread, weighted_length
from ..workspace import Workspace


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


def publish_variant(ws: Workspace, variant: Variant, client) -> str:
    """Post an approved (or failed, when resuming) X variant as a thread.

    posted_ids is persisted after every tweet so an interruption never
    double-posts: resuming skips len(posted_ids) tweets and replies to the
    last posted id.
    """
    tweets = validate_thread(variant.body)
    if variant.status is not Status.PUBLISHING:
        ws.set_status(variant, Status.PUBLISHING)  # gate: only approved/failed may enter
    posted: list[str] = list(variant.meta.get("posted_ids") or [])
    try:
        for text in tweets[len(posted):]:
            reply_to = posted[-1] if posted else None
            posted.append(client.post_tweet(text, in_reply_to=reply_to))
            variant.meta["posted_ids"] = posted
            ws.save_variant(variant)
    except BaseException:
        ws.set_status(variant, Status.FAILED)
        raise
    variant.meta["posted_url"] = f"https://x.com/i/web/status/{posted[0]}"
    ws.set_status(variant, Status.PUBLISHED)
    return variant.meta["posted_url"]
