import pytest

from agenticsocial.models import Status, TransitionError, assert_transition


def test_status_values_match_spec():
    assert [s.value for s in Status] == [
        "draft", "in_review", "approved", "scheduled",
        "publishing", "published", "failed",
    ]


@pytest.mark.parametrize(
    "current,target",
    [
        (Status.DRAFT, Status.IN_REVIEW),
        (Status.IN_REVIEW, Status.DRAFT),
        (Status.IN_REVIEW, Status.APPROVED),
        (Status.APPROVED, Status.IN_REVIEW),
        (Status.APPROVED, Status.PUBLISHING),
        (Status.PUBLISHING, Status.PUBLISHED),
        (Status.PUBLISHING, Status.FAILED),
        (Status.FAILED, Status.PUBLISHING),
    ],
)
def test_allowed_transitions(current, target):
    assert_transition(current, target)  # must not raise


@pytest.mark.parametrize(
    "current,target",
    [
        (Status.DRAFT, Status.APPROVED),      # can't skip review
        (Status.DRAFT, Status.PUBLISHED),
        (Status.IN_REVIEW, Status.PUBLISHING),  # can't post unapproved
        (Status.PUBLISHED, Status.DRAFT),     # published is terminal
        (Status.SCHEDULED, Status.PUBLISHING),  # reserved in v1
    ],
)
def test_forbidden_transitions(current, target):
    with pytest.raises(TransitionError):
        assert_transition(current, target)


def test_error_message_names_allowed_states():
    with pytest.raises(TransitionError, match="allowed next: draft, approved"):
        assert_transition(Status.IN_REVIEW, Status.PUBLISHED)
