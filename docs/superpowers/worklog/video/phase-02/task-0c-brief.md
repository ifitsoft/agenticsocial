# Task 0c Brief: Make a forged status unrepresentable

**Phase:** 2 · **Branch:** `feat/video-phase-02-ingest` · **Follows:** `110745a`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why

Three gate bypasses, one root cause (D-045, D-049, D-059). The last one
**published an unapproved draft**. Each was fixed by making a specific decision
read the file instead of the object.

The Task 0b implementer argued that is the wrong stopping point, and the human
agreed:

> Three bypasses, one identical root cause — that's not three mistakes, it's a
> design where the mistake is the natural thing to write. `v.status` and
> `ws.disk_status(v)` look interchangeable at the call site; nothing in either
> name says which one is a guess. Writability means it isn't a stale cache —
> it's a **forgeable claim**.

**Goal: make the bug unrepresentable rather than fixed.** If the mutable value
does not exist, no future call site can gate on it. That is the property
`window.__seek(t)` gets from being pure in `t` — correctness guaranteed by what
is *unavailable*, not by remembering to do the right thing.

## The change

`Variant` and `Episode` become **frozen**. Both `set_status` functions return a
**new** object instead of mutating.

`meta` stays a mutable dict — `publish_variant` sets `meta["posted_ids"]` and
`meta["posted_url"]` in memory and relies on it. Freezing the dataclass prevents
*rebinding attributes*, which is the forgery; it does not prevent dict mutation,
which is legitimate.

**A consequence to state plainly:** a caller that ignores the return value now
holds a stale object. That is *better* than today — a stale read becomes visible
at the call site (you did not take the result), where a forged status was
invisible. And no gate reads the object any more, so staleness cannot grant
capability.

## Scope, measured

- `src/`: **5** `set_status` call sites, **3** attribute rebinds.
- `tests/`: **69** references across 4 files — mostly `ws.set_status(v, X)` where
  the test then reloads from disk (already correct and needing no change). Only
  chained calls on one object need the return value threaded.

`Source` and `Series` stay as they are: no gate depends on them.

## Ground rules

- **Two commits, source first, then tests.** The suite is expected to be **red
  between them** — that is why they are separate commits, and the red state is
  evidence the refactor actually bit.

  This inverts the usual tests-first rule deliberately. This task changes an
  API's shape rather than adding behaviour, so there is no failing test to write
  first: the tests that will fail are the ones that already exist, and they fail
  because the signature moved, not because a guarantee is missing. Writing new
  tests first would mean writing tests against an API that does not exist yet in
  order to describe a refactor of an API that does.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it**.
- **Authorised test change, narrowly:** you may thread the return value through
  test call sites (`ws.set_status(v, X)` → `v = ws.set_status(v, X)`). You may
  **not** change any assertion, add any assertion, or delete any test. If a test
  fails for a reason other than the API change, that is a finding — report it.
- Do not add dependencies. Never stage anything under `docs/`.

---

- [ ] **Step 1: Source and call sites (one commit)**

**1a.** `src/agenticsocial/models.py` — `Variant` only:

```python
@dataclass(frozen=True)
class Variant:
    platform: str  # x | linkedin | youtube
    status: Status
    meta: dict
    body: str
    path: Path
```

**1b.** `src/agenticsocial/video/models.py` — `Episode` only:

```python
@dataclass(frozen=True)
class Episode:
    id: str
    series_slug: str
    dir: Path
    status: Status
    meta: dict = field(default_factory=dict)
```

**1c.** `src/agenticsocial/workspace.py` — `set_status` returns a new `Variant`.
Add `from dataclasses import replace` to the imports.

```python
    def set_status(self, v: Variant, target: Status) -> Variant:
        """Move a variant to `target`, gated on the status ON DISK.

        Returns a NEW Variant; the argument is unchanged. `Variant` is frozen
        because a writable status is a forgeable claim, and three separate gate
        bypasses came from one being trusted (D-045, D-049, D-059). Callers that
        need the updated object must take the return value.

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
        meta = dict(v.meta)
        meta["status"] = target.value
        self._write_variant(v, meta)
        return replace(v, status=target)
```

**1d.** `src/agenticsocial/video/episode.py` — same shape. Add
`from dataclasses import replace`.

```python
def set_status(episode: Episode, target: Status) -> Episode:
    """Move an episode to `target`, gated on the status ON DISK.

    Returns a NEW Episode; the argument is unchanged. See workspace.set_status
    for why the dataclass is frozen.
    """
    meta, beats_text, nl = _read_meta(episode.script_path)
    raw = meta.get("status", Status.DRAFT.value)
    try:
        current = Status(raw)
    except ValueError:
        raise EpisodeError(
            f"{episode.script_path}: invalid status '{raw}' — one of: "
            f"{', '.join(s.value for s in Status)}"
        )
    assert_transition(current, target, VIDEO_TRANSITIONS)
    meta["status"] = target.value
    atomic_write(episode.script_path, _compose(meta, beats_text, nl))
    return replace(episode, status=target, meta=meta)
```

**1e.** Update the 5 `src/` call sites to take the return value where the caller
subsequently uses the object. In `x/publish.py::publish_variant`:

```python
    if ws.disk_status(variant) is not Status.PUBLISHING:
        variant = ws.set_status(variant, Status.PUBLISHING)  # gate: only approved/failed may enter
```

```python
    except BaseException:
        ws.set_status(variant, Status.FAILED)
        raise
```

```python
    variant.meta["posted_url"] = f"https://x.com/i/web/status/{posted[0]}"
    ws.set_status(variant, Status.PUBLISHED)
    return variant.meta["posted_url"]
```

The last two deliberately discard the result: nothing reads `variant.status`
afterwards, and `meta` is shared. **Check that is still true after your change
rather than trusting me** — if anything downstream reads `variant.status`, thread
it.

`cli.py:160` (`ws.set_status(v, Status.APPROVED)`) discards the result; the
command prints and exits. Verify.

```bash
uv run pytest 2>&1 | tail -6      # RED is expected here; record what fails
git add src/
git commit -m "fix: freeze Variant and Episode so a status cannot be forged

Three gate bypasses came from trusting a writable status attribute; the
last published an unapproved draft. set_status now returns a new object
and the dataclasses are frozen, so gating on a forged status is not
something a future call site can express."
```

- [ ] **Step 2: Thread the return value through tests (one commit)**

Mechanical only. `ws.set_status(v, X)` → `v = ws.set_status(v, X)` **where the
test uses `v` afterwards**. Tests that reload from disk already need no change.

**Change no assertion.** If a test fails for any reason other than needing the
return value, stop and report it.

```bash
uv run pytest 2>&1 | tail -5
git add tests/
git commit -m "test: thread set_status's return value through call sites

Mechanical: Variant and Episode are frozen, so set_status returns a new
object rather than mutating. No assertion changed."
```

- [ ] **Step 3: Prove the forgery is now impossible**

```bash
uv run python - <<'PY'
import shutil; shutil.rmtree("/tmp/frozen", ignore_errors=True)
from pathlib import Path
from agenticsocial.models import Status
from agenticsocial.workspace import Workspace
ws = Workspace.init(Path("/tmp/frozen/workspace"))
src = ws.create_source("Unapproved"); v = ws.create_variant(src, "x", body="hi")
try:
    v.status = Status.PUBLISHING
    print("*** STILL FORGEABLE ***")
except Exception as e:
    print("refused:", type(e).__name__, e)
print("meta still mutable (publish_variant needs it):", end=" ")
v.meta["posted_ids"] = ["1"]; print(v.meta["posted_ids"])
PY
```

Do the same for `Episode`. Paste both.

- [ ] **Step 4: Mutation check**

Apply, run the suite, `git checkout` between. All must fail:

1. `Variant` → `@dataclass` (unfrozen)
2. `Episode` → `@dataclass` (unfrozen)
3. `workspace.set_status` → `return v` instead of `replace(v, ...)`
4. `episode.set_status` → `return episode` instead of `replace(...)`

Mutants 1 and 2 will only fail if something asserts the class is frozen. **If
they survive, say so** — and note that the property is then enforced by nothing
but the decorator. Do not add a test unless you judge one is warranted; tell me
your reasoning either way.

---

## Your report

`docs/superpowers/worklog/video/phase-02/task-0c-report.md`:

1. **What I changed**, and the exact count of test call sites you threaded.
2. **Step 1's RED** — what failed with source frozen but tests not yet updated.
3. **Step 3's forgery proof**, both classes.
4. **Mutation results**, including whether 1 and 2 survive and your reasoning.
5. **Files changed**, both commit SHAs.
6. **Issues or concerns**, including:
   - Any place a caller now silently holds a stale object where it previously
     held a fresh one. Staleness cannot grant capability any more, but it can
     still print a wrong status to an operator.
   - Did any test fail for a reason **other** than the API change? That is the
     signal I most want.
   - `Source` and `Series` are still mutable. Is that defensible, or is it the
     same bug waiting for a gate to depend on them?
