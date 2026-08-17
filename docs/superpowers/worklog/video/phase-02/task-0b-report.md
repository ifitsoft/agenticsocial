# Task 0b Report: One gated status writer

**Branch:** `feat/video-phase-02-ingest`
**Commits:** `2dd9ef1` (tests, RED) → `110745a` (implementation)

---

## 1. What I changed

**`src/agenticsocial/workspace.py`**

- Added `_write_variant(v, meta)` — the single raw writer. Takes the meta dict
  explicitly so no method can write `v.meta` and a status key by accident.
- Added `disk_status(v) -> Status` — parses the file and returns the status the
  *file* records, raising `WorkspaceError` on an unparseable value. This is the
  logic that was previously inlined and private to `set_status`; it is now the
  one place any caller asks "what is this variant, really?".
- `save_variant` no longer writes `v.status`. It writes a *copy* of `v.meta`
  with `status` forced back to `disk_status(v)`. Body and every other metadata
  key (crucially `posted_ids`) still persist.
- `set_status` gates on `disk_status(v)` and writes the status key itself, on a
  copy of `v.meta`. It no longer routes through `save_variant` — that indirection
  is what made `save_variant` a status writer in the first place.

**`src/agenticsocial/x/publish.py`** — the gate-skip decision reads the file:

```python
    if ws.disk_status(variant) is not Status.PUBLISHING:
        ws.set_status(variant, Status.PUBLISHING)  # gate: only approved/failed may enter
```

**`src/agenticsocial/cli.py::post`** — same, and the pre-keyring gate check too:

```python
    if ws.disk_status(v) is not Status.PUBLISHING:  # resume case is already mid-publish
        try:
            assert_transition(ws.disk_status(v), Status.PUBLISHING)  # gate BEFORE the keyring
```

The `v.status in (Status.FAILED, Status.PUBLISHING)` branch above it — which only
produces the "rerun with `--resume`" *message* — was left on `v.status` per the
brief. That is safe: `v` there comes from `_load` → `load_variant`, so its status
is disk-derived by construction.

No dependencies added. Nothing under `docs/` staged.

The shape now matches `video/episode.py::set_status`: read the file, gate on what
the file says, write, then update the object. One gated writer per pipeline.

## 2. TDD evidence

### RED — after commit `2dd9ef1`, before any source change

```
FAILED tests/test_workspace.py::test_save_variant_does_not_change_status - AssertionError: assert <Status.PUBLISHED: 'published'> is <Status.DRAFT: 'd...
FAILED tests/test_workspace.py::test_disk_status_reports_the_file_not_the_object - AttributeError: 'Workspace' object has no attribute 'disk_status'
FAILED tests/test_publish.py::test_a_stale_variant_cannot_publish_a_draft - Failed: DID NOT RAISE TransitionError
========================= 3 failed, 29 passed in 0.43s =========================
```

Three of the four new tests failed for the right reasons — including the headline
one, `DID NOT RAISE TransitionError`, which *is* the bug: two tweets of a draft
went out. The fourth, `test_resuming_a_genuinely_publishing_variant_still_works`,
passed at RED by design; it is an over-correction guard, not a bug reproduction.
Its non-vacuity is demonstrated in §5.

### GREEN — full suite after `110745a`

```
FAILED tests/test_cli.py::test_post_stuck_publishing_requires_resume - AssertionError: assert '--resume' in 'no X token — connect first with `agso...
======================== 1 failed, 378 passed in 1.32s =========================
```

Baseline before this task was **375 passed**. Four tests added → 379 collected.
**378 pass; one pre-existing test now fails.** Analysed in §4. It is left
untouched.

## 3. Step 5 — the original bypass, reproduced by hand

The exact script from the brief, verbatim:

```
refused: TransitionError cannot move draft -> publishing; allowed next: in_review
posted: [] | status: draft
```

Compare with the leader-verified pre-fix output:

```
status on disk : draft
tweets posted  : 2 ['tweet one', 'tweet two']
status after   : published

*** A DRAFT WAS PUBLISHED ***
```

Zero tweets posted, status untouched at `draft`, and the refusal happens before
the first network call.

## 4. Mutation results, and the existing test that failed

Applied one at a time, full suite each, `git checkout` between.

| # | Mutation | Result | Suite |
|---|---|---|---|
| 1 | `save_variant` → `meta["status"] = v.status.value` | **killed** | 1 failed, 378 passed |
| 2 | `publish_variant` decides from `variant.status` | **killed** | 2 failed, 377 passed |
| 3 | `cli.py` decides from `v.status` | **SURVIVED** | 1 failed, 378 passed |
| 4 | `disk_status` returns `v.status` | **killed** | 5 failed, 374 passed |

Kills:

- **1** — `test_save_variant_does_not_change_status`: `assert <Status.PUBLISHED>
  is <Status.DRAFT>`. Note that under this mutant the pre-existing CLI test
  passes again (378), which is direct causal evidence for §4's analysis below.
- **2** — `test_a_stale_variant_cannot_publish_a_draft`: `assert ['one', 'two'] == []`.
  That assertion failure *is* the bug: both tweets of the draft went out.
- **4** — five failures, including two pre-existing tests
  (`test_set_status_gates_on_disk_not_the_in_memory_variant`,
  `test_set_status_rejects_an_unreadable_status_on_disk`) plus both new
  workspace tests and the publish bypass test.

### Mutant 3 survived — analysis

Reverting `cli.py` to decide from `v.status` changes no test outcome. This is an
**equivalent mutant under the current CLI**, not a coverage hole in the sense of
an untested behaviour difference: in `post`, `v` comes from `_load` →
`ws.load_variant`, which constructs the `Variant` by parsing the file. `v.status`
and `ws.disk_status(v)` are therefore equal at that point on every reachable path.
There is no way to reach `cli.py::post` holding a stale `Variant` without
monkeypatching `_load`, and a test that patched `_load` would be asserting
against a hypothetical rather than a reachable state.

I did not add such a test, and I did not weaken the change to make the mutant
die. The `disk_status` call in `cli.py` stays as defence in depth: it removes the
*class* of bug rather than the instance, and it means a future refactor that
starts passing a longer-lived `Variant` into `post` cannot silently reintroduce
it. Worth flagging explicitly: **this line is currently unkilled by the suite.**

### Existing test that failed: `tests/test_cli.py::test_post_stuck_publishing_requires_resume`

```python
def test_post_stuck_publishing_requires_resume(approved, monkeypatch):
    ws, src = approved
    v = ws.load_variant(src, "x")
    v.status = Status.PUBLISHING
    ws.save_variant(v)                      # <- the ungated writer, now removed
    result = runner.invoke(app, ["post", "ready"])
    assert result.exit_code == 1
    assert "--resume" in result.output      # <- fails here
```

**The test's setup is wrong; the behaviour it asserts is intact.** The test
reaches the "stuck in publishing" state by mutating the object and calling
`save_variant` — i.e. by using the exact ungated status writer that this task
deleted. Post-change, disk still says `approved`, so the CLI never takes the
"interrupted, use `--resume`" branch; it proceeds to the gate (approved →
publishing is legal), reaches the keyring, and exits 1 with `no X token`. The
`exit_code == 1` assertion still passes — for the wrong reason — and the
`--resume` assertion fails.

I verified the asserted behaviour survives when the stuck state is created the
legitimate way (`set_status(v, Status.PUBLISHING)`, a legal approved → publishing
move), driving the real CLI:

```
exit_code: 1
output: 2026-07-13-ready was interrupted after 0 tweets — rerun with --resume to continue the thread
disk status: publishing
```

So: same exit code, same message, same disk state. The only thing that changed is
that a test can no longer forge a status by writing it directly — which is the
whole point of the task.

Per instructions I have **not** edited it. The obvious repair is a two-line
change to the fixture setup (`ws.set_status(v, Status.PUBLISHING)` in place of
the `v.status = ...; ws.save_variant(v)` pair), and it needs your call. It is
worth noticing that this test is a small piece of evidence *for* the change: the
only test in the suite that broke is the one that was using the defect as an API.

`tests/test_publish.py::test_publish_resumes_from_stuck_publishing` uses the same
`v.status = ...; save_variant` idiom and **still passes**, because there the disk
status at that point is `failed`, and `failed → publishing` is a legal resume
transition. It reaches the same end state by a legitimate route, so its
assertions hold.

## 5. Vacuity audit

| Test | Fails without the fix? | Killed by |
|---|---|---|
| `test_save_variant_does_not_change_status` | yes — RED, `PUBLISHED is not DRAFT` | mutant 1, 4 |
| `test_disk_status_reports_the_file_not_the_object` | yes — RED, `AttributeError` | mutant 4 |
| `test_a_stale_variant_cannot_publish_a_draft` | yes — RED, `DID NOT RAISE` | mutants 2, 4 |
| `test_resuming_a_genuinely_publishing_variant_still_works` | no (guard test) | see below |

The fourth test passes before and after, so RED does not demonstrate its value. I
proved it non-vacuous separately by mutating the skip away entirely — replacing
the `disk_status` check with `if True:` so the gate always runs:

```
FAILED tests/test_publish.py::test_resuming_a_genuinely_publishing_variant_still_works - agenticsocial.models.TransitionError: cannot move publishing -> publishing;...
========================= 1 failed, 9 passed in 0.25s ==========================
```

That is the failure mode it exists to catch: the cheapest way to "fix" this bug
is to delete the skip, which would break `--resume` — a thread interrupted at
tweet 4 of 6 could never be finished. The test pins the legitimate case the skip
exists for, and it also pins the resume arithmetic (`client.posted == ["two"]`,
not `["one", "two"]`) and the returned URL pointing at the *first* tweet.

Non-vacuity of the other three: each asserts on state read back from disk via
`load_variant`, not on the in-memory object, so none can pass by the object
happening to agree with itself. `test_a_stale_variant_cannot_publish_a_draft`
asserts three independent things — the exception, `client.posted == []`, and the
disk status — so it cannot pass by raising for an unrelated reason after posting.

## 6. Issues and concerns

### `save_variant` now reads the file on every call, and `publish_variant` calls it after every tweet. Does that cost anything, and can the read fail mid-thread?

**Cost: no, not measurably, and not in the place that matters.** The extra work is
one `read_text` plus a frontmatter parse of a file that is a few hundred bytes and
was written by this same process microseconds earlier — it is in page cache with
certainty. The full suite went 1.17s → 1.32s, and that includes four new tests;
the per-call cost is lost in the noise. More to the point, the call sits directly
after `client.post_tweet`, a network round-trip to the X API measured in hundreds
of milliseconds. A filesystem read against a hot cache is roughly four orders of
magnitude cheaper than the operation it follows. If throughput here ever became a
concern, the thread-posting loop is not where the time is going.

**Failure mode: yes, one exists, and it is a strict improvement on the old
behaviour.** If the read fails mid-thread — file deleted, permissions changed,
disk error, or the frontmatter corrupted — `save_variant` raises
(`OSError`/`WorkspaceError`) from inside the `try` block, so `publish_variant`'s
`except BaseException:` catches it and calls `ws.set_status(variant,
Status.FAILED)` — which *also* reads the file, and will also raise. The original
exception is then lost, replaced by the one from the failed `set_status`, and the
thread is left mid-flight with `posted_ids` on disk one tweet behind reality.

Two things blunt this. First, the resume invariant is not violated in the
dangerous direction: the tweet that was posted but not recorded would be
re-posted on `--resume`, which is a duplicate tweet, not a lost or double-charged
one — annoying, recoverable by hand, and strictly better than the alternative.
Second, this failure mode is not new. The old `save_variant` also wrote to the
same file with `atomic_write`, which does `mkstemp(dir=path.parent)` and would
have failed on the same underlying conditions (missing directory, permissions,
full disk). The new read fails on a slightly *larger* set of conditions — a
corrupted or externally-truncated frontmatter now breaks the loop where before it
would have been silently overwritten. I consider that the correct trade: silently
overwriting a file whose contents you could not parse is how the original bug
laundered itself.

The genuinely uncovered gap is the double-fault in the `except` handler — the
error-path `set_status` can itself raise and mask the real cause. That is
pre-existing (the old `set_status` read the file too) and out of scope here, but
it is worth a task: `publish_variant`'s recovery path should be able to record
`failed` without depending on the same read that just failed, or at minimum
should chain the original exception rather than replace it.

### Is `disk_status` the right shape, or should `Variant` simply not carry a mutable `status` at all?

**It should not carry one.** I'll argue both sides, but I don't think this is
close.

*The case for keeping it.* `Variant` is a dataclass modelling a file, and the
file has a status; a model that omits its subject's central field is a strange
model. Reading `v.status` is convenient and correct in the overwhelming majority
of call sites — the CLI uses it for messages, `status`/`list` render it, and in
every one of those places `v` was loaded from disk moments earlier and is
accurate. Removing the field means every one of those call sites grows an
`ws.disk_status(v)` call, which is an I/O operation dressed up as an attribute
access, which invites its own bugs (a rendering loop over twenty variants now
does twenty file reads) and makes `Variant` useless in isolation from a
`Workspace`. And the field being *mutable* is what lets `set_status` keep the
in-memory object coherent after a write, so callers holding the object don't see
a stale value.

*The case against, which I find decisive.* Three bypasses (D-045, D-049, D-059)
have now had the identical root cause: someone read the object where they needed
to read the file. That is not three mistakes, that is a design that makes the
mistake the natural thing to write. `v.status` and `ws.disk_status(v)` look
interchangeable at the call site — one is an attribute access, the other a method
call, and nothing in either name says "this one is a guess." The security-relevant
distinction is invisible in the code, and the invisible-but-critical distinction
is exactly the shape of defect that recurs. Worse, `status` being *writable* means
an attacker or a bug does not merely read a stale value — it can *assert* a
false one, and until this task that assertion was persisted by `save_variant`.
The field is not just a stale cache, it is a forgeable claim.

The convenience argument does not survive contact with the alternative. The right
shape is: `Variant` carries no `status` field; `disk_status` is renamed to
`status(v)` on `Workspace` — or better, the field is kept but made *read-only*
and documented as "as of load time, never valid for a gate decision," with
`set_status` returning a fresh `Variant` rather than mutating in place. The
display call sites lose nothing under the read-only variant, and the twenty-file-
reads objection is answered by `list_sources`/`variants` already reading every
file anyway. The determinism the video engine gets from `window.__seek(t)` being
a pure function of `t` is the same property wanted here: a gate decision should be
a pure function of the file, and the only way to guarantee that is to make the
non-file value unavailable at the decision point.

What I would *not* do is stop at `disk_status`. This task removes the third
instance; it does not remove the ability to write a fourth. `disk_status` is the
right *mechanism* and the wrong *stopping point* — as long as `v.status` is
readable and writable next to it, the next gate check written in this codebase is
one keystroke away from being wrong again, and it will look fine in review. My
recommendation is a follow-up task that makes `Variant.status` non-mutable
(`dataclasses.field(...)` on a frozen dataclass, or a property with no setter)
and audits every read of it. That would have made all three bypasses
unrepresentable rather than merely fixed.

### Any remaining writer of a status key anywhere in `src/`

Audited with `grep -rn '"status"' src/`. Five hits outside the video module's
own equivalents:

- `workspace.py:165` — `create_variant` writes `"status": Status.DRAFT.value` in
  the initial meta. This is a **creation** writer, not a transition writer, and
  it is safe: it refuses if the path already exists (`raise WorkspaceError(f"{platform}
  variant already exists")`), so it can never overwrite an existing status.
  `DRAFT` is also the bottom of the lattice — it grants no capability.
- `workspace.py:180` — `load_variant` *reads*.
- `workspace.py:213` — `disk_status` *reads*.
- `workspace.py:230` — `save_variant`, now writing back what `disk_status`
  returned. This is a status writer only in the sense that it must re-emit the
  key to keep the frontmatter well-formed; it cannot change the value.
- `workspace.py:248` — `set_status`. **The only writer that can change a status.**

The video pipeline mirrors this exactly: `episode.py:165` creation-only,
`:180`/`:246` reads, `:255` the single gated writer in `set_status`.

No writer of a status key exists outside `workspace.py` and `video/episode.py`.
`cli.py` contains none; `x/publish.py` contains none. Both pipelines now have
exactly one gated status writer each, which was the goal.
