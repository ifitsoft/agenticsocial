# Task 0c Report: Make a forged status unrepresentable

**Branch:** `feat/video-phase-02-ingest`
**Commit 1 (source):** `0846a317e5b1a54f242ca55f05e6729917ea9ec6`
**Commit 2 (tests):** `b37950149e94f6e1cfe09c09f1bef137045b2cfe`

---

## 1. What I changed

Source (commit 1, `src/` only):

- `src/agenticsocial/models.py` — `Variant` → `@dataclass(frozen=True)`.
- `src/agenticsocial/video/models.py` — `Episode` → `@dataclass(frozen=True)`.
- `src/agenticsocial/workspace.py` — added `from dataclasses import replace`;
  `Workspace.set_status` now returns `Variant` (was `None`), dropped `v.status = target`,
  returns `replace(v, status=target)`. Docstring per the brief.
- `src/agenticsocial/video/episode.py` — added `from dataclasses import replace`;
  `set_status` now returns `Episode`, dropped `episode.status = target` /
  `episode.meta = meta`, returns `replace(episode, status=target, meta=meta)`.
- `src/agenticsocial/x/publish.py:46` — `variant = ws.set_status(variant, Status.PUBLISHING)`.

Call sites verified rather than trusted:

- `publish.py:55` (`FAILED`) — result discarded. Correct: the next statement is `raise`.
- `publish.py:58` (`PUBLISHED`) — result discarded. Correct: the next statement returns
  `variant.meta["posted_url"]`, and `meta` is the same dict object after `replace`.
- `cli.py:160` (`APPROVED`) — result discarded. Correct: the command only echoes `src.id`
  and returns. Confirmed nothing after `publish_variant(...)` in `cli.py::post` reads
  `v.status` either.

Tests (commit 2):

- **Return value threaded at 2 call sites**, both `Episode`:
  `tests/test_video_episode.py:183` and `tests/test_video_episode.py:612`
  (`set_status(ep, X)` → `ep = set_status(ep, X)`).
  **Zero `Variant` call sites needed threading** — every one of them reloads from disk.
- **4 further edits that are not threading** (flagged, see §6): tests that construct a
  forged or edited object by attribute assignment. The field is no longer writable, so
  they now construct the same object with `dataclasses.replace`. No assertion changed,
  no test added or removed.
  - `tests/test_publish.py:94` `stuck = replace(stuck, status=Status.PUBLISHING)`
  - `tests/test_publish.py:132` `v = replace(v, status=Status.PUBLISHING)`
  - `tests/test_workspace.py:123` `v = replace(v, body="new body")`
  - `tests/test_workspace.py:215` `v = replace(v, status=Status.PUBLISHED)`
  - `tests/test_workspace.py:231` `v = replace(v, status=Status.APPROVED)`
    (that is 5 lines across 4 files' worth of tests; 5 forgery-construction edits total)

Final: **379 passed**, `git status --porcelain -- src tests` clean.

## 2. Step 1's RED

With source frozen and tests untouched: **7 failed, 372 passed**.

```
FAILED tests/test_publish.py::test_publish_resumes_from_stuck_publishing - dataclasses.FrozenInstanceError: cannot assign to field 'status'
FAILED tests/test_publish.py::test_a_stale_variant_cannot_publish_a_draft - dataclasses.FrozenInstanceError: cannot assign to field 'status'
FAILED tests/test_video_episode.py::test_set_status_updates_the_in_memory_episode - AssertionError: assert <Status.DRAFT: 'draft'> is <Status.IN_REVIEW: 'in_re...
FAILED tests/test_video_episode.py::test_set_status_refreshes_the_object_from_disk - AssertionError: assert <Status.DRAFT: 'draft'> is <Status.APPROVED: 'approv...
FAILED tests/test_workspace.py::test_save_variant_roundtrips_body_edits - dataclasses.FrozenInstanceError: cannot assign to field 'body'
FAILED tests/test_workspace.py::test_save_variant_does_not_change_status - dataclasses.FrozenInstanceError: cannot assign to field 'status'
FAILED tests/test_workspace.py::test_disk_status_reports_the_file_not_the_object - dataclasses.FrozenInstanceError: cannot assign to field 'status'
```

Two shapes: 2 `AssertionError`s (the API change proper — the object no longer mutates)
and 5 `FrozenInstanceError`s (tests that *deliberately* forge, which is the change biting
exactly where it was aimed).

## 3. Step 3's forgery proof

`Variant`:

```
refused: FrozenInstanceError cannot assign to field 'status'
meta still mutable (publish_variant needs it): ['1']
```

`Episode`:

```
refused: FrozenInstanceError cannot assign to field 'status'
refused (meta rebind): FrozenInstanceError cannot assign to field 'meta'
meta dict still mutable: 1.25
```

Both classes: the status attribute cannot be rebound; the `meta` dict's *contents*
remain mutable, which is what `publish_variant` depends on.

## 4. Mutation results

| # | Mutant | Result |
|---|---|---|
| 1 | `Variant` → `@dataclass` (unfrozen) | **SURVIVED** — 379 passed |
| 2 | `Episode` → `@dataclass` (unfrozen) | **SURVIVED** — 379 passed |
| 3 | `workspace.set_status` → `return v` | **SURVIVED** — 379 passed |
| 4 | `episode.set_status` → `return episode` | **KILLED** — 2 failed, 377 passed |

Mutant 4's kills: `test_set_status_updates_the_in_memory_episode`,
`test_set_status_refreshes_the_object_from_disk`.

**Mutants 1 and 2 survive, as you predicted they might.** Reasoning: nothing asserts the
class is frozen. After commit 2 no test *attempts* an attribute rebind — the five that
did now use `replace`, which works on frozen and unfrozen dataclasses alike. So the
property is currently enforced by the decorator alone. That is genuinely weaker than it
looks: a future editor who hits `FrozenInstanceError` while writing a new call site can
delete `(frozen=True)` and the suite stays green, which is the same "nothing stops you"
shape the refactor exists to eliminate.

**Mutant 3 is the surprise, and it is not on your list of expected survivors.**
`workspace.set_status`'s return value is **completely unverified**. Every `Variant` test
reloads from disk, and the one production caller that takes the result
(`publish.py:46`) never reads `variant.status` afterwards. So `return v` — returning a
stale object with the pre-transition status — is indistinguishable from correct behaviour
to the entire suite. The `Episode` half is pinned by two tests; the `Variant` half by none.

**Should I add tests?** Your instruction was explicit — add no assertion, no test — so I
added none. My judgment is that two are warranted and I recommend them as a follow-up:

1. `assert ws.set_status(v, Status.IN_REVIEW).status is Status.IN_REVIEW` and
   `assert v.status is Status.DRAFT` on the argument — kills mutant 3 and pins the
   "argument unchanged" half of the contract, which nothing checks for either class.
2. `with pytest.raises(FrozenInstanceError): v.status = ...` for both classes — kills
   mutants 1 and 2 and turns "frozen" from a decorator into an asserted invariant. This
   is the one I'd argue hardest for: the whole point of the task is that the property
   survives future editors, and right now removing it is silent.

## 5. Files changed

Commit 1 `0846a31` (source):
`src/agenticsocial/models.py`, `src/agenticsocial/video/models.py`,
`src/agenticsocial/workspace.py`, `src/agenticsocial/video/episode.py`,
`src/agenticsocial/x/publish.py`.

Commit 2 `b379501` (tests):
`tests/test_publish.py`, `tests/test_video_episode.py`, `tests/test_workspace.py`.

Nothing under `docs/` staged. `tests/test_cli.py` needed no change.

## 6. Issues and concerns

### Two brief defects

**(a) Scope count is wrong.** The brief says "`src/`: **5** `set_status` call sites".
There are **4**: `cli.py:160`, `publish.py:46`, `publish.py:55`, `publish.py:58`. The
"3 attribute rebinds" figure is correct. I changed nothing to reach 5.

**(b) The `episode.set_status` code block silently deletes documentation, and I did not
follow it exactly.** The brief's block replaces the whole docstring, dropping the
paragraph recording *why* the gate reads disk (D-045, spec §8.4/§10). That is the
institutional memory for one of the three bypasses this task exists to close. I kept
that paragraph and appended the brief's new sentences. Every line of the block that
affects behaviour I took verbatim; the deviation is docstring prose only. Flagging it
because the rule is "follow the code block", and I chose not to on this one line.

### Did any test fail for a reason other than the API change?

**Yes — one, and it is a genuine finding.**
`test_save_variant_roundtrips_body_edits` failed with
`FrozenInstanceError: cannot assign to field 'body'`. That has nothing to do with status
forgery. `frozen=True` freezes *every* field, and `body` is a field a caller has a
completely legitimate reason to change: editing a variant's text is the normal workflow.
The brief's rationale ("a writable status is a forgeable claim") justifies freezing
`status`; it does not justify freezing `body`, `platform`, or `path`, and the brief never
mentions the collateral. Today the only in-repo body editor is that test — production
code writes bodies through `create_variant` — so the cost is currently zero. But an edit
command, an ingest path, or a rewrite step will hit it, and `replace(v, body=...)` is the
answer they will need to be told. Worth a line in DECISIONS: *the freeze is broader than
the argument for it, and that was accepted.*

No test failed for a reason suggesting a real aliasing bug. I looked specifically: the
`meta` dict is shared by reference across `replace`, which is exactly what
`publish_variant` and `test_set_status_preserves_in_memory_meta` rely on, and both are
green. Nothing surfaced that mutation had been hiding.

**A second thing, weaker but worth naming.** Four tests were failing not because they
consume the API but because they *forge* — they exist to prove a forged object is
rejected. Rewriting `v.status = X` as `v = replace(v, status=X)` keeps them passing and
keeps them meaningful (the disk gate is still the thing under test), but it is worth
noticing that `replace` is now the forgery tool. Freezing did not make a forged `Variant`
unconstructible; it made it *unconstructible by accident*. Someone who wants a lying
Variant can still have one in one line. The defence remains "no gate reads the object" —
`disk_status` — with the freeze demoting the mistake from something you write without
noticing to something you have to mean. That is a real improvement and it is worth being
precise that it is that improvement and not a stronger one.

Also: `tests/test_publish.py::test_publish_resumes_from_stuck_publishing` line 94
(`stuck = replace(stuck, status=Status.PUBLISHING)`, commented "simulate hard-kill
before FAILED was written") is now **inert**. `save_variant` on the next line re-reads
`disk_status` (the D-049 fix), so the forged field never reaches the file; the disk
already says `failed`, and `failed → publishing` is legal, which is the only reason the
test passes. The line has not simulated a hard kill since D-049. Not something I was
authorised to change, and the test's real assertions are still valid, but its comment
now describes something that does not happen.

### Callers now silently holding a stale object

Three, all in `src/`, all deliberate and all currently harmless:

- `publish.py:55` `ws.set_status(variant, Status.FAILED)` — `variant` then goes out of
  scope via `raise`. Never read again.
- `publish.py:58` `ws.set_status(variant, Status.PUBLISHED)` — `variant.status` still says
  `publishing` for the one remaining statement, which reads `variant.meta`, not `status`.
- `cli.py:160` `ws.set_status(v, Status.APPROVED)` — `v.status` still says `in_review`.
  The command echoes only `src.id`, so nothing wrong is printed **today**.

The operator-facing risk you flagged is real but not yet realised: none of these three
prints a status. The one to watch is `cli.py:160` — if anyone adds
`status: {v.status.value}` to that success message it will print `in_review` immediately
after approving, and no test will catch it. That is a one-line change away and it is the
kind of thing a future task will do. Threading the result there costs nothing and
forecloses it; I left it as the brief specified, but I would thread it.

### `Source` and `Series` — defensible, or the fourth instance waiting?

**Half defensible. `Source` yes, `Series` no — and `Series` is the one I would fix.**

The argument for freezing is not "mutable is bad", it is "a field that a decision reads
must not be forgeable". So the test is: does anything gate on a field of this object?

`Source` passes. It carries `id`, `type`, `title`, `dir`, `origin_url`, `created` — pure
identity and description. No transition table consults it, no capability depends on it.
The worst a forged `Source` achieves is a wrong `dir`, and a wrong `dir` fails loudly by
not existing rather than quietly by granting something. Leaving it mutable is not deferred
risk, it is correct scoping. I would not freeze it, and I would not freeze it later either.

`Series` does not pass, and the reason is specific rather than theoretical. It carries
`target_sec`, `tolerance_sec`, `formats`, `acts`, `warm_acts` and `design` — and the video
MVP spec makes duration compliance a **gate**: an episode outside `target_sec ±
tolerance_sec` is supposed to be blocked. The moment Phase 3 writes
`if abs(dur - series.target_sec) > series.tolerance_sec: raise`, `series.tolerance_sec`
becomes exactly what `v.status` was — a writable value that a decision trusts, sitting on
an object the caller has held across a file read. `series.tolerance_sec = 999` is then
D-045 with different nouns, and the pattern you have watched happen three times is that
nobody writes that line maliciously; they write it in a test helper or a retry path and it
leaks.

So my answer is: you have not deferred the fourth instance for `Source`, but for `Series`
you have deferred it by roughly one phase. `Series` is loaded from `series.yaml` and never
written back by the current code, which makes freezing it nearly free right now — no
`set_*` function to convert, no return values to thread. It gets more expensive after
Phase 3 adds a writer, not less. My recommendation: freeze `Series` before the duration
gate lands, and pair it with the rule the three bypasses actually teach — *anything a gate
reads is read from disk at gate time, and the object is never the authority*. The freeze
is what makes that rule enforceable rather than remembered.
