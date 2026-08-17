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


from pathlib import Path

import pytest

from agenticsocial.models import Status
from agenticsocial.workspace import Workspace
from agenticsocial.x.client import XApiError
from agenticsocial.x.publish import publish_variant


class FakeClient:
    def __init__(self, fail_at: int | None = None):
        self.posted: list[tuple[str, str | None]] = []
        self.fail_at = fail_at
        self._n = 0

    def post_tweet(self, text, in_reply_to=None):
        self._n += 1
        if self.fail_at is not None and self._n >= self.fail_at:
            raise XApiError("boom")
        self.posted.append((text, in_reply_to))
        return f"id{self._n}"


@pytest.fixture()
def approved_variant(tmp_path):
    ws = Workspace.init(tmp_path / "ws")
    src = ws.create_source("Thread", created="2026-07-13")
    v = ws.create_variant(src, "x", body="One\n\n---tweet---\n\nTwo\n\n---tweet---\n\nThree")
    ws.set_status(v, Status.IN_REVIEW)
    ws.set_status(v, Status.APPROVED)
    return ws, src, v


def test_publish_posts_thread_with_reply_chain(approved_variant):
    ws, src, v = approved_variant
    client = FakeClient()
    url = publish_variant(ws, v, client)
    assert url == "https://x.com/i/web/status/id1"
    assert client.posted == [("One", None), ("Two", "id1"), ("Three", "id2")]
    saved = ws.load_variant(src, "x")
    assert saved.status == Status.PUBLISHED
    assert saved.meta["posted_ids"] == ["id1", "id2", "id3"]
    assert saved.meta["posted_url"] == url
    assert saved.meta["posted_at"]


def test_publish_failure_marks_failed_and_keeps_posted_ids(approved_variant):
    ws, src, v = approved_variant
    with pytest.raises(XApiError):
        publish_variant(ws, v, FakeClient(fail_at=3))
    saved = ws.load_variant(src, "x")
    assert saved.status == Status.FAILED
    assert saved.meta["posted_ids"] == ["id1", "id2"]


def test_publish_resume_skips_already_posted(approved_variant):
    ws, src, v = approved_variant
    with pytest.raises(XApiError):
        publish_variant(ws, v, FakeClient(fail_at=3))
    resumed = ws.load_variant(src, "x")
    client = FakeClient()
    publish_variant(ws, resumed, client)
    # only the third tweet is posted, replying to the last posted id
    assert client.posted == [("Three", "id2")]
    assert ws.load_variant(src, "x").status == Status.PUBLISHED


def test_publish_resumes_from_stuck_publishing(approved_variant):
    ws, src, v = approved_variant
    with pytest.raises(XApiError):
        publish_variant(ws, v, FakeClient(fail_at=3))
    stuck = ws.load_variant(src, "x")
    stuck.status = Status.PUBLISHING          # simulate hard-kill before FAILED was written
    ws.save_variant(stuck)
    client = FakeClient()
    publish_variant(ws, ws.load_variant(src, "x"), client)
    assert client.posted == [("Three", "id2")]
    assert ws.load_variant(src, "x").status == Status.PUBLISHED


def test_publish_refuses_unapproved(tmp_path):
    ws = Workspace.init(tmp_path / "ws")
    src = ws.create_source("Nope", created="2026-07-13")
    v = ws.create_variant(src, "x", body="hi")  # draft
    from agenticsocial.models import TransitionError
    with pytest.raises(TransitionError):
        publish_variant(ws, v, FakeClient())


def test_a_stale_variant_cannot_publish_a_draft(tmp_path):
    """Leader-verified bypass: a Variant claiming PUBLISHING skipped the gate,
    posted every tweet, and save_variant then stamped `publishing` onto the
    draft so the closing transition passed too."""
    import pytest

    from agenticsocial.models import Status, TransitionError
    from agenticsocial.workspace import Workspace
    from agenticsocial.x.publish import publish_variant

    class Client:
        def __init__(self):
            self.posted = []

        def post_tweet(self, text, in_reply_to=None):
            self.posted.append(text)
            return str(len(self.posted))

    ws = Workspace.init(tmp_path / "workspace")
    src = ws.create_source("Unapproved")
    v = ws.create_variant(src, "x", body="one\n\n---tweet---\n\ntwo")
    v.status = Status.PUBLISHING          # the stale claim

    client = Client()
    with pytest.raises(TransitionError):
        publish_variant(ws, v, client)

    assert client.posted == []
    assert ws.load_variant(src, "x").status is Status.DRAFT


def test_resuming_a_genuinely_publishing_variant_still_works(tmp_path):
    """The legitimate case the skip existed for: disk really says publishing."""
    from agenticsocial.models import Status
    from agenticsocial.workspace import Workspace
    from agenticsocial.x.publish import publish_variant

    class Client:
        def __init__(self):
            self.posted = []

        def post_tweet(self, text, in_reply_to=None):
            self.posted.append(text)
            return "id" + str(len(self.posted))

    ws = Workspace.init(tmp_path / "workspace")
    src = ws.create_source("Approved")
    v = ws.create_variant(src, "x", body="one\n\n---tweet---\n\ntwo")
    ws.set_status(v, Status.IN_REVIEW)
    ws.set_status(v, Status.APPROVED)
    ws.set_status(v, Status.PUBLISHING)
    v.meta["posted_ids"] = ["id1"]        # one tweet already out
    ws.save_variant(v)

    client = Client()
    url = publish_variant(ws, v, client)
    assert client.posted == ["two"]       # only the remainder
    assert ws.load_variant(src, "x").status is Status.PUBLISHED
    assert url.endswith("id1")
