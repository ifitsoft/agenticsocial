# Phase 7 · Task 1 — `agsoc video approve`, the gate

**Branch:** `feat/video-phase-07-approve` · **Baseline:** 1612 tests → **1658**
**Mutation score:** **21/21 killed, 0 survivors** (14 from the brief's table, 7 my own)
**Commits:** `7eb3c80` (tests, red) · `c918df1` (the command) · `2e656da` · `fdeff70`

---

## 1. The two decisions

### 1.1 Who is the approver? — `--by` is required, and never inferred

Four candidate sources, and I rejected three:

| Source | Why not |
|---|---|
| `series.byline` | It is a **display credit on the frame** — `plan.py` hands it to the renderer to draw. Reusing it for accountability conflates *who this show is by* with *who signed off on this episode*; they are the same person today and will not be the first time anyone else touches the series. It is also `""` in the real workspace, so the honest fallback is a refusal anyway. |
| `getpass.getuser()` | Whoever's laptop the command ran on. On a single-operator machine it is a constant, which means it records nothing — a field that is always the same value is a field that carries no information, dressed as one that does. |
| `$AGSOC_APPROVER` | Better than the other two, but it makes an unattended process able to sign: an agent inheriting the operator's environment approves under the operator's name, and nothing in the record distinguishes that from a human typing it. |
| **`--by`, required** | **Chosen.** |

The asymmetry §8.4 states for overrides is the argument: *passing verification is
automatic; bypassing it costs you a written sentence with your name on it.* An
approval is the larger of the two acts, so it cannot cost less than the smaller
one. `--by` makes the name something a person types at the moment of deciding,
and the record lands in `script.yaml` — **a visible diff in a file you commit**,
which is the exact property §8.4 demands of an override and the reason I did not
put the record in a sidecar JSON file.

What happens when `byline` is empty: **nothing, because it is never consulted.**
There is a test pinning that a non-empty `byline` does *not* become the approver
(`test_the_byline_is_not_used_as_the_approver`). Blank or whitespace `--by`
refuses with the flag named; omitting it is a usage error from typer.

**The honest limit, stated rather than implied:** this records *a name that was
typed*, not *that a human typed it*. Nothing in a local CLI can distinguish the
two, and CLAUDE.md's "agents must never run `approve`" remains a rule, not a
mechanism. The value of the field is that a forged one is a lie someone told in a
committed diff, not a gap nobody can see.

### 1.2 Re-run `check`, or require a fresh ledger? — **require**

`approve` reads `claims.json` from disk and refuses if it is absent or stale. It
never computes a verdict.

1. **The ledger is the artifact of record, and the screen a human read.** `check`
   prints the attestations you are approving (D-088), the entity misses that are
   recorded and not gated (D-102), the near-miss excerpt, and the fix line
   (D-104). If `approve` computed its own verdicts, the operator would be signing
   verdicts **nobody displayed** — and D-104's own lesson is that the display *is*
   the deliverable.
2. **Two ways to produce a verdict is the D-059 shape.** The defect was two paths
   to one answer with one of them ungated. A gate that re-runs the checker has a
   second verdict path by construction, and the two can disagree the moment
   anything about ordering, error handling or corpus resolution differs between
   them. Requiring the file means there is exactly one producer (`check`) and one
   consumer (`approve`).
3. **A gate should be a gate, not a pipeline.** D-072's property is *one function
   reads the authority and performs the write it gates, with nothing in between*.
   Re-running the verifier puts the entire extraction and comparison pass in that
   gap.
4. **Refusing is cheap and teaches.** The cost is one extra command, and the
   refusal prints the exact command with the episode and series filled in. The
   alternative's cost is silent: an approval of a script the operator never saw
   checked.

Staleness is `verify.stale_reason`, which Phase 5 Task 3 already built for both
halves (corpus **and** script). I wired it; I did not rebuild it — its docstring
says an `approve` that only compared `corpus_sha` "would have approved a ledger
describing sentences nobody wrote."

### 1.3 The third decision I had to make anyway: what `script_sha256` covers

**It covers the beats document's bytes, not the whole file**, and the alternative
is not merely worse, it does not work:

- The metadata document carries `status` **and the approval record itself**, so a
  whole-file digest recorded *into* the file it hashes has no fixed point.
- Recording it after the write only defers the problem: `approved → rendering`
  rewrites `status`, so Phase 8's own transition would invalidate the approval,
  and `failed → rendering` retry would report drift that never happened.
  `episode.py`'s module docstring already names this: *"Re-serialising beats on a
  status change would fire drift detection on churn we caused."*

The cost is stated rather than hidden: **the metadata document is outside the
hash.** `pace` scales every hold and is therefore recorded *beside* the digest in
the approval record, so Task 3 can detect a pace edit without pretending the hash
covered it.

⚠️ **Name collision to resolve in Task 3:** `plan.py` already writes a
`script_sha256` into `plan.json` and it is the **whole-file** digest
(`load_script_with_digest`). Two meanings for one key is the D-036 pattern. I did
not rename it — `plan.json` is consumed by the engine and Phase 8's contract — but
drift detection must not compare the two. My suggestion: rename plan's to
`script_file_sha256` when Task 3 touches drift.

---

## 2. R5 — every status-writing path in `src/`, and how each is gated

This is the section D-059 exists to force. It is **not** a claim; it is an
enumeration, mechanised as a test (`test_only_two_functions_write_a_status_key`)
so it is re-run on every commit rather than done once in a report.

### 2.1 Assignments to a status key

```
$ grep -rn --include='*.py' 'status"\] *=' src/
src/agenticsocial/video/episode.py:302:    meta["status"] = target.value
src/agenticsocial/workspace.py:247:        meta["status"] = self.disk_status(v).value
src/agenticsocial/workspace.py:269:        meta["status"] = target.value
```

| # | Path | Pipeline | Gated? |
|---|---|---|---|
| 1 | `video/episode.py:set_status` | video | **Yes.** Re-reads the status from `script.yaml`, calls `assert_transition(current, target, VIDEO_TRANSITIONS)`, and performs the write itself. The only writer of an episode's status. |
| 2 | `workspace.py:Workspace.set_status` | text | **Yes.** Same shape, `ALLOWED_TRANSITIONS`. |
| 3 | `workspace.py:Workspace.save_variant` | text | **Not a hole.** It writes back `self.disk_status(v)` — the value already on disk — precisely so it cannot stamp a forged one. This line *is* D-059's root cause, post-fix: it used to write what the in-memory object claimed. |

### 2.2 Literal dicts containing a status key

```
$ grep -rn --include='*.py' '"status":' src/
src/agenticsocial/workspace.py:182:   "status": Status.DRAFT.value,    # new_variant
src/agenticsocial/video/episode.py:171: "status": Status.DRAFT.value,   # _new_meta, used by create_episode
```

Both are creation, both are the constant `DRAFT`, neither takes a status from a
caller. `draft` is the initial state in both tables, so neither can skip an edge.

### 2.3 Every writer of `script.yaml` (the file the video status lives in)

```
$ grep -rn --include='*.py' 'atomic_write' src/agenticsocial/video/
episode.py:150   create_episode   -> script.yaml   (status: draft, constant)
episode.py:303   set_status       -> script.yaml   (gated, #1 above)
plan.py:272      write_plan       -> out/plan-*.json
ingest.py:101                     -> brief.md
corpus.py:120,129                 -> sources/*.txt, sources/_manifest.json
series.py:237,238                 -> series.toml, coverage.json
verify.py:831    write_ledger     -> claims.json
```

**Two writers of `script.yaml`, and only one of them writes a status that a
caller chose.** Nothing else in `src/` touches the file.

### 2.4 Every call site of a `set_status`

```
video/approve.py:128   set_status(episode, Status.APPROVED, {"approval": record})   <- this task
cli.py:160             ws.set_status(v, Status.APPROVED)          text approve
x/publish.py:46,55,58  ws.set_status(...) PUBLISHING/FAILED/PUBLISHED
```

The video pipeline has **exactly one** call site, and it is the gate. `render.py`
has none (`preview` is documented as not touching status); the video CLI has none
outside `approve` — pinned by
`test_the_video_cli_never_writes_a_status_outside_the_gate`.

### 2.5 The hole this task created, found by doing the enumeration rather than asserting it

`set_status` gained a third parameter in this task — the extra metadata that
makes the approval record land in the **same write** as the transition (two
writes means a crash between them and an approved episode nobody signed). That
parameter reaches the metadata document, so **it is a status writer unless the
write order forbids it**:

```python
    assert_transition(current, target, VIDEO_TRANSITIONS)
    meta.update(record or {})        # merge FIRST
    meta["status"] = target.value    # then the gated value, which wins
```

Reversed, any caller holding a dict writes any status it likes *through the one
function this project trusts* — D-059 rebuilt inside the fix for D-059. Pinned by
`test_the_extra_record_cannot_smuggle_a_status` and killed as mutant **O4**.

### 2.6 Is `rendering` reachable without approval? — asked past the first "no"

- **No code path sets `RENDERING` at all.** `grep -rn RENDERING src/` outside
  `models.py` returns two *comments*. The state is currently unreachable by any
  command, which is a weaker statement than "gated" and I am making the weaker
  one.
- `agsoc video preview` renders and does not touch status (Phase 1.5, by design).
- **A hand edit reaches it.** Demonstrated on the throwaway workspace:
  `status: approved` → `status: rendering` in `script.yaml`, and
  `agsoc video list` reports `rendering`. The filesystem is the state; a person
  editing their own file is not a bypass, but it is worth naming that the
  approval record is equally hand-writable. D-062's position applies verbatim:
  this raises the floor, it is not a boundary, and **the load-bearing defence is
  that no gate reads anything but the disk.**
- **When Phase 8 lands `render`, the gate must be `assert_transition` from the
  disk status *plus* a `script_sha256` comparison.** Status alone is not enough:
  an approved episode whose beats were edited afterwards still says `approved`.

---

## 3. TDD evidence and the mutation score

**Tests first, red, committed** — `7eb3c80`, 46 tests, before any implementation:

```
tests/test_video_approve.py:30: in <module>
    from agenticsocial.video import approve as approve_mod
E   ImportError: cannot import name 'approve' from 'agenticsocial.video'
```

Then `c918df1`, and the suite went 1612 → 1658 with no regressions.

### The sweep

`PYTHONDONTWRITEBYTECODE=1` (D-100), full suite per mutant, source restored after
each. Harness and raw log:
`/Volumes/…/jobs/9a014c11/tmp/mutate.py`, `mutation-01.txt`.

| # | Mutant | Result |
|---|---|---|
| M1 | `approve` accepts a caller-supplied ledger | killed — signature test |
| M2 | a `fail` claim approves | killed |
| M3 | `no_source` treated as passing | killed |
| M4 | unattested `manual` approves | killed |
| M5 | attested `manual` blocks | killed |
| M6 | an entity miss blocks | killed |
| M7 | stale ledger approves | killed |
| M8 | absent ledger approves | killed |
| M9a | `script_sha256` not recorded | killed |
| M9b | `script_sha256` over the whole file | killed |
| M10 | status written without `assert_transition` | killed |
| M11 | `draft → approved` permitted in `VIDEO_TRANSITIONS` | killed |
| M12 | the refusal names no claim | killed |
| M13 | `check`'s summary calls a `manual` claim verified | killed |
| M14 | summary and gate computed independently | killed |
| O1 | an unknown verdict fails **open** | killed |
| O2 | beats re-read with universal newlines (CRLF) | killed |
| O3 | a blank approver is accepted | killed |
| O4 | the record merged *after* the status is set (§2.5) | killed |
| O5 | `approve` resolves a partial episode id | killed |
| O6 | the record written by a second, ungated writer | killed |

**21/21, zero survivors.** Two caveats on how to read that number:

- **O5 was written before the sweep, for a mutant I expected to survive** — the
  test that kills it (`test_approve_does_not_resolve_a_partial_episode_id`,
  `fdeff70`) is dated after the implementation, not after the sweep. I am
  reporting it as a predicted survivor I closed, not as a survivor the sweep
  found.
- A clean score is a statement about *my* mutants. The one class I could not
  mutate meaningfully is the write's atomicity: I have no harness that crashes
  between two writes, so "the record and the status land together" is argued from
  the code (one `atomic_write`) rather than measured.

### The defect the sweep exposed in existing code

`is_blocking` answered **"not blocking"** for any verdict it did not recognise:
`verdict in ("fail", "no_source")` is False for `supported`, for `ok`, for a
record with no `mechanical` block at all. A hand-edited or future-phase ledger
would have approved with nothing checked. This is D-106's exact shape — *a value
the rule cannot read treated as "nothing to check" rather than "cannot be
checked"* — and it sat in the predicate the gate was about to be built on.

It is now `classify()`, which fails **closed**: `verified` requires `pass`,
`attested` requires `manual` + a non-blank attestation, and **everything else is
`open`.** `is_blocking` is derived from it rather than restating the list.

### The ride-along (D-112), fixed by construction

`check`'s green line no longer calls an attested claim verified. Both halves are
counted through the same `classify` the gate uses, so the count and the decision
**cannot** disagree — M14's mutant (a second, independently-written predicate in
`cli.py`) is killed by an identity assertion, not by a behavioural coincidence.

On the operator's real episode, the exact line D-112 flagged:

```
before:   7 claims verified, none open
after:    6 verified · 1 attested by hand, NOT verified (D-088) · 7 claims, none open
```

---

## 4. Step 5 — end to end, throwaway workspace

`$AGSOC_WORKSPACE=/Volumes/…/jobs/9a014c11/tmp/demo/workspace`. Four beats plus a
`custom`; one KPI figure typed as `$3.99` where the source says `$3.96`.

### An open claim refuses

```
$ agsoc video check 2026-08-18 --series the-brief          # EXIT=1
the-brief/2026-08-18 · 3 claims · 1 pass · 1 fail · 1 manual

    c-002   beat  1  statement  pass
 !  c-003   beat  2  kpis       fail
    c-004   beat  3  custom     manual
...
$ agsoc video approve 2026-08-18 --series the-brief --by "Ali Abdukarim"
EXIT=1
the-brief/2026-08-18 · NOT approved — 1 of 3 claims are open

 !  c-003   beat  2  kpis       fail
      why      the quote does not contain 3.99 by value
      fix      correct the figure, widen `quote:` so it covers it, or write a `claim_override`
               (reason + by) in script.yaml

run `agsoc video check 2026-08-18 --series the-brief` for the full detail. Nothing moved; the episode is still in_review

status on disk:
status: in_review
```

### Fixing the figure without re-checking refuses **differently**

The screen an operator gets for the mistake that matters most — approving against
a ledger that no longer describes the script:

```
$ sed -i '' "s/'3.99'/'3.96'/" script.yaml
$ agsoc video approve 2026-08-18 --series the-brief --by "Ali Abdukarim"
EXIT=1
the-brief/2026-08-18 · NOT approved — the check does not describe this script
      why      the script has changed since this check was written
      fix      run `agsoc video check 2026-08-18 --series the-brief`, read it, then approve
```

### The same episode, checked, approves

```
$ agsoc video check 2026-08-18 --series the-brief          # EXIT=0
...
  attested by hand — no machine checked these (D-088), you are approving the sentence:
    c-004    “Draws the two prices above as a ladder; the figures are the ones in the kpis beat.”

  names not found in the source — recorded, not gated (D-102: ...):
    c-002    DeepSeek 1.6T MoE

2 verified · 1 attested by hand, NOT verified (D-088) · 3 claims, none open

$ agsoc video approve 2026-08-18 --series the-brief --by "Ali Abdukarim"
EXIT=0
the-brief/2026-08-18 · approved
      by       Ali Abdukarim
      at       2026-08-18T00:46:28-05:00
      script   sha256 802c335b609355db37d166dbbcebe726344a14bad4bc5ddac317bfdf28761746 (the beats
               document)
      claims   2 of 3 verified · 1 attested by hand, not verified (D-088), checked
               2026-08-18T00:46:28.656627-05:00
      next     edit the beats and this approval no longer describes them — `script_sha256` is what
               says so
```

and in `script.yaml`, the diff a human commits:

```yaml
status: approved
date_long: August 18, 2026
pace: 1.0
approval:
  by: Ali Abdukarim
  at: '2026-08-18T00:46:28-05:00'
  script_sha256: 802c335b609355db37d166dbbcebe726344a14bad4bc5ddac317bfdf28761746
  pace: 1.0
  claims_checked_at: '2026-08-18T00:46:28.656627-05:00'
  corpus_sha: 227be06e985cf44e1887cebf9317806396dd00aa46e143c4182d8c6f9ad1d176
  claims:
    total: 3
    verified: 2
    attested: 1
```

Three properties confirmed after the approval:

```
$ agsoc video check 2026-08-18 --series the-brief          # EXIT=0  — the approval did
                                                           # not invalidate its own ledger
$ agsoc video approve … --by "Ali Abdukarim"               # EXIT=1
the-brief/2026-08-18 · NOT approved — cannot move approved -> approved; allowed next:
in_review, rendering. Only a script an agent has finished and marked `status: in_review`
can be approved
```

### The operator's workspace

Backed up before anything ran; **never approved, never modified.** All three
episodes still pass, and the tree is byte-identical to the backup:

```
2026-08-17  EXIT=0  ::  6 verified · 1 attested by hand, NOT verified (D-088) · 7 claims, none open
2026-08-17b EXIT=0  ::  22 claims verified, none open
2026-08-17c EXIT=0  ::  24 claims verified, none open

$ diff -rq workspace …/ws-safe  ->  OPERATOR WORKSPACE UNCHANGED
```

`2026-08-17` is D-112's own episode; its summary line is now honest.

---

## 5. Files changed

| File | Change |
|---|---|
| `src/agenticsocial/video/approve.py` | **new** — the gate: `ApprovalRefused`, `approve_episode(ws, series_slug, ep_id, *, by, now)` |
| `src/agenticsocial/video/verify.py` | `classify`, `is_blocking` (moved here, now fail-closed), `claim_records`, `open_claims` |
| `src/agenticsocial/video/episode.py` | `beats_sha256`; `set_status` gains the extra-metadata parameter, merged *before* the status |
| `src/agenticsocial/video/cli.py` | `video approve`; `is_blocking` re-exported as the same object; `_cleared_summary` replaces the overclaiming green line |
| `tests/test_video_approve.py` | **new** — 46 tests |

Commits: `7eb3c80` (tests, red) → `c918df1` (implementation) → `2e656da` (R5's
own hole) → `fdeff70` (exact episode match). Not squashed.
`git status --porcelain -- src tests` is clean.

---

## 6. Issues and concerns

1. **Can you still get an unapproved episode into `rendering`?** Not through any
   command — and the honest reason is that **nothing sets `RENDERING` yet**, not
   that something tried and was refused. A hand edit reaches it and always will;
   see §2.6 for what Phase 8's `render` must therefore check (disk status **and**
   `script_sha256`, because `approved` alone survives an edit).

2. **Is the refusal actionable?** Three shapes, three different actions:
   claim → the claim id, the reason, and D-104's three-remedy `fix` line; ledger
   → the command with episode and series filled in; transition → the current
   status, the allowed next ones, and what an agent is supposed to have done.
   Every refusal also states that nothing moved.

3. **`plan.json`'s `script_sha256` is the whole-file digest; the approval's is
   the beats digest.** One key, two meanings — the D-036 pattern. Task 3 must not
   compare them. Suggest renaming plan's to `script_file_sha256`.

4. **`check`'s override line now overclaims, in the other direction.** It prints
   *"recorded, not applied: `approve` is what reads an override"*. As of Task 1
   `approve` does **not** read it — an override does not clear a `fail`, and there
   is a test pinning that. Task 2 makes the sentence true; until it lands the
   sentence is a promise, not a description. I left the text for Task 2 rather
   than churn it twice.

5. **Nothing un-approves, and a stale `approval:` block will outlive an
   un-approval.** `approved → in_review` exists in the table but no command walks
   it, so today the record cannot go stale that way. The moment Task 3 (or a
   `revoke`) adds that edge, the block must be cleared in the same gated write —
   otherwise a file says `in_review` and carries a signature.

6. **`agsoc init` ignores `$AGSOC_WORKSPACE`** — it takes a positional path
   defaulting to `./workspace`, so `AGSOC_WORKSPACE=… agsoc init` silently
   scaffolds in the current directory. I hit this while building the throwaway
   workspace and it ran against the operator's `workspace/`. **No damage:**
   `Workspace.init` is idempotent (`mkdir(exist_ok=True)`, writes `voice.md` and
   `config.toml` only if absent) and the tree diffed identical to the backup
   afterwards. Still a trap worth closing — the other commands all resolve
   through `Workspace.locate()`.

7. **A pre-existing backup made my first backup misleading.** `cp -a workspace
   <dest>` where `<dest>` already existed from an earlier session nested the copy
   inside it, so the "backup" I diffed against was an older tree with one episode
   instead of three. Caught by inspecting the diff instead of trusting it. Same
   family as D-105: the comfortable reading arrived first and nothing about it
   looked wrong.

8. **Brief defect (cosmetic).** The report section asks for "all twelve mutants";
   the table lists fourteen (M1–M14). I did all fourteen plus seven.

9. **Not gated, deliberately:** runtime tolerance. The demo episode approved at
   22.0s against a 120±8s target, `OUT OF TOLERANCE`, and `check` says so
   loudly. §11 makes runtime a report, not a gate, so `approve` does not read it
   — but an approved episode that cannot meet its own runtime target is a real
   state, and if Phase 8 refuses to render it, the refusal will arrive *after*
   the approval. Worth a decision in Task 3.
