"""Domain model: sources, variants, and the status lifecycle.

The approval gate lives here: there is deliberately no edge from
in_review to publishing, and none into approved except from in_review.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Status(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"  # reserved for the v2 calendar
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


ALLOWED_TRANSITIONS: dict[Status, set[Status]] = {
    Status.DRAFT: {Status.IN_REVIEW},
    Status.IN_REVIEW: {Status.DRAFT, Status.APPROVED},
    Status.APPROVED: {Status.IN_REVIEW, Status.PUBLISHING},
    Status.SCHEDULED: set(),
    Status.PUBLISHING: {Status.PUBLISHED, Status.FAILED},
    Status.PUBLISHED: set(),
    Status.FAILED: {Status.PUBLISHING},
}

_ORDER = list(Status)


class TransitionError(Exception):
    def __init__(self, current: Status, target: Status):
        allowed = ", ".join(
            s.value for s in _ORDER if s in ALLOWED_TRANSITIONS[current]
        ) or "none (terminal)"
        super().__init__(
            f"cannot move {current.value} -> {target.value}; allowed next: {allowed}"
        )


def assert_transition(current: Status, target: Status) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise TransitionError(current, target)


@dataclass
class Source:
    id: str
    type: str  # url | idea | transcript
    title: str
    dir: Path
    origin_url: str | None = None
    created: str = ""


@dataclass
class Variant:
    platform: str  # x | linkedin | youtube
    status: Status
    meta: dict
    body: str
    path: Path
