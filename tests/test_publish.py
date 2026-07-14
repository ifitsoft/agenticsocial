import pytest

from agenticsocial.x.publish import ValidationError, validate_thread


def test_validate_thread_splits_and_passes():
    assert validate_thread("A\n\n---tweet---\n\nB") == ["A", "B"]


def test_validate_thread_rejects_empty_body():
    with pytest.raises(ValidationError, match="empty"):
        validate_thread("\n\n")


def test_validate_thread_rejects_overlong_tweet():
    body = "ok\n\n---tweet---\n\n" + "x" * 281
    with pytest.raises(ValidationError, match="tweet 2 is 281"):
        validate_thread(body)
