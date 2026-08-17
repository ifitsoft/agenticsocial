import pytest

from agenticsocial.models import (
    ALLOWED_TRANSITIONS,
    VIDEO_TRANSITIONS,
    Status,
    TransitionError,
    assert_transition,
)


def test_render_states_exist():
    assert Status.RENDERING.value == "rendering"
    assert Status.RENDERED.value == "rendered"


def test_both_tables_are_total():
    """Every status must be a key in both tables, or lookups raise KeyError."""
    for s in Status:
        assert s in ALLOWED_TRANSITIONS, f"{s} missing from ALLOWED_TRANSITIONS"
        assert s in VIDEO_TRANSITIONS, f"{s} missing from VIDEO_TRANSITIONS"


def test_approved_may_enter_rendering():
    assert_transition(Status.APPROVED, Status.RENDERING, VIDEO_TRANSITIONS)


def test_in_review_may_not_skip_the_gate():
    with pytest.raises(TransitionError):
        assert_transition(Status.IN_REVIEW, Status.RENDERING, VIDEO_TRANSITIONS)


def test_approved_may_not_jump_straight_to_rendered():
    with pytest.raises(TransitionError):
        assert_transition(Status.APPROVED, Status.RENDERED, VIDEO_TRANSITIONS)


def test_failed_render_may_retry():
    assert_transition(Status.FAILED, Status.RENDERING, VIDEO_TRANSITIONS)


def test_rendering_may_fail():
    assert_transition(Status.RENDERING, Status.FAILED, VIDEO_TRANSITIONS)


def test_approval_may_be_revoked():
    assert_transition(Status.APPROVED, Status.IN_REVIEW, VIDEO_TRANSITIONS)


def test_published_is_terminal_for_video():
    assert VIDEO_TRANSITIONS[Status.PUBLISHED] == set()


def test_text_table_rejects_rendering():
    """A text variant must never enter a render state."""
    with pytest.raises(TransitionError):
        assert_transition(Status.APPROVED, Status.RENDERING)


def test_text_pipeline_is_unchanged():
    assert_transition(Status.APPROVED, Status.PUBLISHING)
    assert_transition(Status.IN_REVIEW, Status.APPROVED)


def test_error_message_lists_the_right_table_next_states():
    with pytest.raises(TransitionError) as excinfo:
        assert_transition(Status.APPROVED, Status.PUBLISHED, VIDEO_TRANSITIONS)
    message = str(excinfo.value)
    assert "rendering" in message
    assert "in_review" in message
    assert "publishing" not in message


def test_error_message_defaults_to_text_table():
    with pytest.raises(TransitionError) as excinfo:
        assert_transition(Status.APPROVED, Status.PUBLISHED)
    assert "publishing" in str(excinfo.value)
