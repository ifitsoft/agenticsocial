# Task 0b Brief: One gated status writer

**Phase:** 2 · **Branch:** `feat/video-phase-02-ingest` · **Follows:** `ed9d8a6`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why

Task 0 fixed the gate in `Workspace.set_status`. **It was not enough.**
Leader-verified against the real code:

```
status on disk : draft
tweets posted  : 2 ['tweet one', 'tweet two']
status after   : published

*** A DRAFT WAS PUBLISHED ***
```

Two tweets of unapproved content went out, and the file ended up marked
`published`. The README's central promise — *"Nothing goes live without you
running `agsoc approve`"* — is breakable.

**Two defects, one root cause.**

**1. The gate can be skipped entirely.** `x/publish.py:45` (mirrored at
`cli.py:207`) decides *whether to run the gate* from in-memory status:

```python
    if variant.status is not Status.PUBLISHING:
        ws.set_status(variant, Status.PUBLISHING)   # gate: only approved/failed may enter
```

A stale `Variant` claiming `PUBLISHING` skips that line, so the gate never runs.

**2. `save_variant` is an ungated status writer.** This is the root cause and the
more important half:

```python
    def save_variant(self, v: Variant) -> None:
        v.meta["status"] = v.status.value      # no table, no disk read, no gate
```

It stamps whatever the object claims. So after the gate is skipped, the posting
loop's `save_variant` writes `status: publishing` onto the draft — and the
closing `set_status(PUBLISHED)` then passes legitimately, because by then disk
really does say `publishing`. **The bypass launders itself.**

The video pipeline has exactly **one** writer of episode status, and it is gated.
The text pipeline has two, and one of them is not. That asymmetry is the bug.

## The fix

**`set_status` owns the `status` key. Nothing else writes it.**

## Ground rules

- **Two commits.** Failing tests first, then implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it**.
- Do not add dependencies. Never stage anything under `docs/`.
- **Do not modify any existing test.** If one fails, that is a finding — report
  it rather than editing it. Several existing tests exercise this path and I have
  not verified they all survive.
- Report observed counts.

## Files

- Modify: `src/agenticsocial/workspace.py`
- Modify: `src/agenticsocial/x/publish.py`
- Modify: `src/agenticsocial/cli.py`
- Test: `tests/test_publish.py`, `tests/test_workspace.py` (append only)

---

- [ ] **Step 1: Append the tests**

To `tests/test_workspace.py`:

```python
def test_save_variant_does_not_change_status(tmp_path):
    """save_variant persists body and metadata. Status belongs to set_status
    alone — a second, ungated status writer is what let a draft be published."""
    from agenticsocial.models import Status
    from agenticsocial.workspace import Workspace

    ws = Workspace.init(tmp_path / "workspace")
    src = ws.create_source("Kill staging")
    v = ws.create_variant(src, "x", body="hello")

    v.status = Status.PUBLISHED          # a stale or hostile object
    v.meta["posted_ids"] = ["1"]
    ws.save_variant(v)

    reloaded = ws.load_variant(src, "x")
    assert reloaded.status is Status.DRAFT        # unchanged on disk
    assert reloaded.meta["posted_ids"] == ["1"]   # metadata still persisted


def test_disk_status_reports_the_file_not_the_object(tmp_path):
    from agenticsocial.models import Status
    from agenticsocial.workspace import Workspace

    ws = Workspace.init(tmp_path / "workspace")
    src = ws.create_source("Kill staging")
    v = ws.create_variant(src, "x", body="hello")
    v.status = Status.APPROVED
    assert ws.disk_status(v) is Status.DRAFT
```

To `tests/test_publish.py`:

```python
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
```

```bash
uv run pytest tests/test_workspace.py tests/test_publish.py 2>&1 | tail -15
git add tests/test_workspace.py tests/test_publish.py
git commit -m "test: pin one gated status writer

A Variant claiming PUBLISHING skipped the gate and published a draft;
save_variant then stamped publishing onto the file so the closing
transition passed legitimately. The bypass laundered itself."
```

- [ ] **Step 2: Implement**

**2a.** In `src/agenticsocial/workspace.py`, split writing from gating:

```python
    def _write_variant(self, v: Variant, meta: dict) -> None:
        atomic_write(v.path, frontmatter.dump(meta, v.body))

    def disk_status(self, v: Variant) -> Status:
        """The variant's status as the FILE records it, not as the object claims.

        Callers deciding whether a transition is allowed must use this. Three
        separate bypasses in this codebase came from reading the object instead
        (D-045, D-049, D-059).
        """
        meta, _ = frontmatter.parse(v.path.read_text(encoding="utf-8"))
        raw = meta.get("status", Status.DRAFT.value)
        try:
            return Status(raw)
        except ValueError:
            raise WorkspaceError(
                f"{v.path}: invalid status '{raw}' — one of: "
                f"{', '.join(s.value for s in Status)}"
            )

    def save_variant(self, v: Variant) -> None:
        """Persist body and metadata. Does NOT change status.

        `set_status` is the only writer of the status key. A second, ungated
        writer is what allowed a draft to be published: the skipped gate was
        laundered by this method stamping `publishing` onto the file.
        """
        meta = dict(v.meta)
        meta["status"] = self.disk_status(v).value
        self._write_variant(v, meta)

    def set_status(self, v: Variant, target: Status) -> None:
        """Move a variant to `target`, gated on the status ON DISK.

        Only the status is read from disk; `v.meta` is written as-is, because
        publish_variant sets `posted_url` in memory and relies on this call to
        persist it.
        """
        assert_transition(self.disk_status(v), target)
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        if target is Status.APPROVED:
            v.meta["approved_at"] = now
        if target is Status.PUBLISHED:
            v.meta["posted_at"] = now
        v.status = target
        meta = dict(v.meta)
        meta["status"] = target.value
        self._write_variant(v, meta)
```

**2b.** In `src/agenticsocial/x/publish.py`, decide from disk:

```python
    if ws.disk_status(variant) is not Status.PUBLISHING:
        ws.set_status(variant, Status.PUBLISHING)  # gate: only approved/failed may enter
```

**2c.** In `src/agenticsocial/cli.py`, the same pre-check (currently around line
207, `if v.status is not Status.PUBLISHING:`) reads disk:

```python
    if ws.disk_status(v) is not Status.PUBLISHING:  # resume case is already mid-publish
        try:
            assert_transition(ws.disk_status(v), Status.PUBLISHING)  # gate BEFORE the keyring
        except TransitionError as e:
            raise _fail(str(e))
```

Check the surrounding lines before editing — the resume/failed handling above it
uses `v.status` for *messages*, which is fine and should stay.

- [ ] **Step 3: Run everything, then commit**

```bash
uv run pytest 2>&1 | tail -8
git add src/agenticsocial/workspace.py src/agenticsocial/x/publish.py src/agenticsocial/cli.py
git commit -m "fix: make set_status the only writer of variant status

A Variant claiming PUBLISHING skipped the gate entirely, posted every
tweet of a draft, and save_variant stamped publishing onto the file so
the closing transition passed legitimately -- the bypass laundered
itself. save_variant now preserves the status on disk, and both
gate-skip decisions read the file rather than the object."
```

- [ ] **Step 4: Mutation check**

Apply, run the full suite, `git checkout` between. All must fail:

1. `save_variant` → `meta["status"] = v.status.value` (the ungated writer)
2. `publish_variant` → decide from `variant.status` again
3. `cli.py` → decide from `v.status` again
4. `disk_status` → return `v.status` instead of reading the file

- [ ] **Step 5: Reproduce the original bypass by hand**

Run the exact script that proved it, and paste the output. It must now refuse:

```bash
uv run python - <<'PY'
from pathlib import Path
from agenticsocial.models import Status
from agenticsocial.workspace import Workspace
from agenticsocial.x.publish import publish_variant
class C:
    def __init__(self): self.posted=[]
    def post_tweet(self, text, in_reply_to=None):
        self.posted.append(text); return str(len(self.posted))
import shutil; shutil.rmtree("/tmp/gate4b", ignore_errors=True)
ws = Workspace.init(Path("/tmp/gate4b/workspace"))
src = ws.create_source("Unapproved thoughts")
v = ws.create_variant(src, "x", body="tweet one\n\n---tweet---\n\ntweet two")
v.status = Status.PUBLISHING
c = C()
try:
    publish_variant(ws, v, c); print("*** STILL BYPASSED ***", c.posted)
except Exception as e:
    print("refused:", type(e).__name__, e)
print("posted:", c.posted, "| status:", ws.load_variant(src,"x").status.value)
PY
```

---

## Your report

`docs/superpowers/worklog/video/phase-02/task-0b-report.md`:

1. **What I changed.**
2. **TDD evidence** — RED (piped) and GREEN.
3. **Step 5's by-hand reproduction**, pasted.
4. **Mutation results**, and **any existing test that failed** — I did not verify
   they all survive, and a failure is a finding, not something to edit away.
5. **Vacuity audit** of your tests.
6. **Issues or concerns**, including:
   - `save_variant` now reads the file on every call, and `publish_variant` calls
     it after every tweet. Does that cost anything that matters, and is there a
     failure mode where the read fails mid-thread?
   - Is `disk_status` the right shape, or should `Variant` simply not carry a
     mutable `status` at all? Argue it — the object's status has now caused
     three bypasses.
   - Any remaining writer of a status key anywhere in `src/`.
