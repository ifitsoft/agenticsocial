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
    RENDERING = "rendering"
    RENDERED = "rendered"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


ALLOWED_TRANSITIONS: dict[Status, set[Status]] = {
    Status.DRAFT: {Status.IN_REVIEW},
    Status.IN_REVIEW: {Status.DRAFT, Status.APPROVED},
    Status.APPROVED: {Status.IN_REVIEW, Status.PUBLISHING},
    Status.SCHEDULED: set(),
    Status.RENDERING: set(),  # video-only; unreachable for text variants
    Status.RENDERED: set(),   # video-only; unreachable for text variants
    Status.PUBLISHING: {Status.PUBLISHED, Status.FAILED},
    Status.PUBLISHED: set(),
    Status.FAILED: {Status.PUBLISHING},
}

# Video episodes have their own lifecycle: the expensive step is rendering, and
# it sits behind the same human gate that publishing sits behind for text.
VIDEO_TRANSITIONS: dict[Status, set[Status]] = {
    Status.DRAFT: {Status.IN_REVIEW},
    Status.IN_REVIEW: {Status.DRAFT, Status.APPROVED},
    Status.APPROVED: {Status.IN_REVIEW, Status.RENDERING},
    Status.SCHEDULED: set(),
    Status.RENDERING: {Status.RENDERED, Status.FAILED},
    # Back to `rendering`, and NOWHERE else. Spec §9 makes one approval render
    # every enabled format, and the formats are rendered minutes or days apart;
    # a second format is the same story producing a second artifact from the
    # same signed bytes, through the same three gates. It is not lifecycle
    # progress, which is why the only edge out is the one that comes back here.
    #
    # D-006 is untouched: it cut `rendered -> publishing` because that edge was
    # never exercised and made `failed` ambiguous. `rendered` having no outgoing
    # edge at all was its consequence, not its purpose — and the consequence was
    # that `render <ep> --format wide` was refused on the one episode most
    # likely to want it. Publishing is still unreachable from every video state.
    Status.RENDERED: {Status.RENDERING},
    Status.PUBLISHING: set(),    # unreachable in MVP; kept for table totality
    Status.PUBLISHED: set(),
    Status.FAILED: {Status.RENDERING},
}

_ORDER = list(Status)


class TransitionError(Exception):
    def __init__(
        self,
        current: Status,
        target: Status,
        table: dict[Status, set[Status]],
    ):
        # Kept as attributes, not only interpolated: a caller that has to decide
        # what to SUGGEST needs to know which state it is in. `rendered` is
        # terminal, and telling that operator to run `approve` sends them to a
        # command that will refuse them too.
        self.current = current
        self.target = target
        allowed = ", ".join(
            s.value for s in _ORDER if s in table[current]
        ) or "none (terminal)"
        super().__init__(
            f"cannot move {current.value} -> {target.value}; allowed next: {allowed}"
        )


def assert_transition(
    current: Status,
    target: Status,
    table: dict[Status, set[Status]] | None = None,
) -> None:
    table = ALLOWED_TRANSITIONS if table is None else table
    if target not in table[current]:
        raise TransitionError(current, target, table)


@dataclass
class Source:
    id: str
    type: str  # url | idea | transcript
    title: str
    dir: Path
    origin_url: str | None = None
    created: str = ""


@dataclass(frozen=True)
class Variant:
    platform: str  # x | linkedin | youtube
    status: Status
    meta: dict
    body: str
    path: Path
