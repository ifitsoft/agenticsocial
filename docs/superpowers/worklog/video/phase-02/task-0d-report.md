# Task 0d Report: Enforce what Task 0c only declared, and freeze `Series`

**Branch:** `feat/video-phase-02-ingest` · **Follows:** `b379501`

## 1. What I changed

- **Commit 1 (`8bb3d5a`, tests):** appended the four tests from the brief, verbatim.
  - `tests/test_workspace.py`: `test_variant_status_cannot_be_assigned`,
    `test_set_status_returns_a_new_variant_and_leaves_the_argument_alone`
  - `tests/test_video_episode.py`: `test_episode_status_cannot_be_assigned`
  - `tests/test_video_series.py`: `test_series_runtime_targets_cannot_be_assigned`
- **Commit 2 (`e820492`, src):** `Series` → `@dataclass(frozen=True)` in
  `src/agenticsocial/video/models.py`. One line; nothing else needed changing.

No existing assertion was touched, no dependency added, nothing under `docs/`
staged.

## 2. RED results

```
1 failed, 204 passed in 0.77s
FAILED tests/test_video_series.py::test_series_runtime_targets_cannot_be_assigned
    - Failed: DID NOT RAISE FrozenInstanceError
```

Exactly as the brief predicted:

| Test | RED |
|---|---|
| `test_variant_status_cannot_be_assigned` | passed immediately |
| `test_set_status_returns_a_new_variant_and_leaves_the_argument_alone` | passed immediately |
| `test_episode_status_cannot_be_assigned` | passed immediately |
| `test_series_runtime_targets_cannot_be_assigned` | **failed** |

The three that passed immediately pin behaviour Task 0c shipped but left
unverified — that is the whole point of this task, not a finding.

Full suite after Step 2: **383 passed** (was 379).

## 3. Mutation results — all five now killed

| # | Mutant | Result | Killed by |
|---|---|---|---|
| 1 | `Variant` → `@dataclass` | 1 failed, 382 passed | `test_workspace.py::test_variant_status_cannot_be_assigned` |
| 2 | `Episode` → `@dataclass` | 1 failed, 382 passed | `test_video_episode.py::test_episode_status_cannot_be_assigned` |
| 3 | `Series` → `@dataclass` | 1 failed, 382 passed | `test_video_series.py::test_series_runtime_targets_cannot_be_assigned` |
| 4 | `workspace.set_status` → `return v` | 1 failed, 382 passed | `test_workspace.py::test_set_status_returns_a_new_variant_and_leaves_the_argument_alone` |
| 5 | `video.episode.set_status` → `return episode` | 2 failed, 381 passed | `test_set_status_updates_the_in_memory_episode`, `test_set_status_refreshes_the_object_from_disk` |

None survived. Each mutant was `git checkout`-reverted immediately after its
run; `git status --porcelain -- src tests` is clean.

## 4. Files changed

- `tests/test_workspace.py`, `tests/test_video_episode.py`,
  `tests/test_video_series.py` — commit **`8bb3d5a`**
- `src/agenticsocial/video/models.py` — commit **`e820492`**

## 5. Issues and concerns

### 5.1 `replace(v, status=...)` still forges a status. Was freezing symbolic?

**Largely yes, as a security control — and the honest framing is that the
disk-reading gates do all the load-bearing work.** "Unrepresentable" was the
wrong word and should be retracted. But "mostly symbolic" is not the same as
"worthless", and the residual value is real for a reason that has nothing to do
with security. Three separate claims, argued separately:

**(a) Freezing does not make a forged status unrepresentable; it makes an
accidental one impossible.** `replace(v, status=PUBLISHING)` is one line, and
nothing stops it. But look at what freezing actually converts: `v.status =
APPROVED` is a single token change, reads like ordinary bookkeeping, and is
invisible in review — it is precisely the shape of the three historical bypasses
(D-045, D-049, D-059), all of which were *accidents of convenience*, not
attacks. `replace(v, status=APPROVED)` names the module, names the field, and
rebinds — it is greppable and conspicuous, and no one writes it while believing
they are just updating a local variable. Freezing does not close the hole; it
raises the intent floor required to walk through it. That is a genuine but
modest gain.

**(b) The real defence is that no gate reads the object, and it is complete on
its own.** `workspace.set_status` gates on `assert_transition(self.disk_status(v),
target)`. `video.episode.set_status` re-reads `meta` from `script.yaml` and gates
on that. `cli.py::post` calls `assert_transition` before touching the keyring.
Given all three, a forged in-memory status — by assignment, by `replace`, by
`object.__setattr__`, by constructing a `Variant` from scratch — **buys the
forger exactly nothing**. And this property is already pinned by test, not by
convention: `test_disk_status_ignores_the_in_memory_field` forges via `replace`
and asserts `disk_status` still says `draft`. Pinning that a forgery is
*ineffective* is strictly stronger than pinning that a particular syntax for
forging it is unavailable. If I had to keep only one of the two mechanisms, I
would keep the disk read without hesitating.

**(c) So is there a mechanism worth adding? I recommend no.** The candidates:

1. *Custom `__setattr__`/`__replace__` rejecting `status`* — forbidden by the
   brief, and rightly: it is defeated by `object.__setattr__` in one more line,
   so it buys one rung on a ladder with infinite rungs. Python offers no
   in-process enforcement boundary; chasing one is a category error.
2. *Remove `status` from the dataclass; expose it as a property that reads disk*
   — this is the only option that genuinely closes forging, because you cannot
   forge a field that does not exist. I still reject it. It costs an I/O per
   access, it makes `Variant` no longer a snapshot of a file (directly
   contradicting the principle the brief accepted in "What is NOT changing"),
   and it trades a *hypothetical* bypass for a *real* class of bug: values that
   silently change under a caller mid-operation.
3. *A grep-style test banning `replace(..., status=` outside `workspace.py` and
   `episode.py`* — cheap, honest about being a lint rather than a guarantee, and
   the best of the three. But its marginal value over what exists is close to
   zero, because (b) already makes the banned expression harmless, and a lint
   that guards a harmless expression mostly generates future friction.

**The justification I would keep for freezing is the non-security one, and it is
sufficient by itself:** a `Variant`/`Episode`/`Series` is a snapshot of a file,
and mutating any field makes the object lie about the file. That is a
correctness argument, it applies to `body` and `meta` and `target_sec` just as
much as to `status`, and it survives the concession that a determined caller can
still forge anything. I would restate the guarantee to the human as: *forging a
status is no longer something you can do by accident, and doing it deliberately
accomplishes nothing, because every gate re-reads disk.* Not "unrepresentable".

**One thing this task does not defend against, and it is the bigger risk.** The
next bypass will not look like a forged field. It will look like a *new gate in
Phase 3 that reads the in-memory object instead of re-reading disk* — e.g.
`if episode.status is not APPROVED: raise` in the render path, or a duration
check against a `Series` loaded ten minutes and one `series.toml` edit ago.
`frozen=True` is completely inert against that. The durable defence is the rule
"gates read disk" plus the stale-object test pattern already in
`test_workspace.py` and `test_video_episode.py::test_set_status_refreshes_the_object_from_disk`.
When Phase 3 adds the duration gate, that gate deserves the same stale-object
test, and I would rate writing it as higher value than anything in this section.

### 5.2 Is `Source` staying mutable defensible permanently, or deferred?

**Deferred, but on much better ground than `Series` was — and the deciding
question is not mutability, it is whether a gate ever reads it.** Today
`Source` is `id`/`type`/`title`/`dir`/`origin_url`/`created`: identity and
description. No gate reads any of them; the status machine does not touch
`Source` at all. On the argument I used for `Series` (a writable value that a
gate reads is the dangerous shape), `Source` is currently not that shape, so
freezing it now would be hygiene rather than defect prevention.

Two caveats keep this from being "permanently defensible":

- `Source.dir` is a `Path` that *is* consumed by filesystem operations. It is not
  a gate input, but a mutated `dir` is a path-traversal shape, and Phase 2's
  ingest work is the phase most likely to start passing `Source` objects around.
  If ingest ever derives a write target from `source.dir` after handing the
  object to another layer, freezing stops being optional.
- Grep confirms **nothing in `src/` or `tests/` assigns to any `Source` field**
  today, which means freezing it is *free right now* by the same argument that
  made `Series` free. The only reason not to do it in this task is that the brief
  did not ask for it and it is out of scope.

Recommendation: freeze `Source` opportunistically during Phase 2 ingest, before
anything starts mutating it — same reasoning as `Series`, same cost profile.
Right now the cost is one line and zero call-site changes; it rises the moment
ingest wants to rewrite a title in place.

### 5.3 Anything in `src/` that assigns to a `Series` field

**Nothing.** A grep for assignments to every `Series` field name across `src/`
returned no hits, and the full suite passed on the first run after freezing —
no call-site conversion was needed. `Series` is loaded from `series.toml` and
never written back, exactly as the brief described.

### 5.4 Other notes

- No disagreement between the brief's code blocks and its prose. Every code block
  was applied verbatim; nothing needed flagging.
- Counts reported are observed, not adjusted: 204 collected for the three-file
  RED run, 383 for the full suite after Step 2, up from 379.
