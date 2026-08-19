# Task 2 Report: the gated path has exactly one writer

**Phase:** 13 · **Branch:** `fix/render-second-format` · **Spec:** §6, §9, §10
**Baseline:** 2053 tests · **At HEAD:** 2061 tests, **13/13 mutants killed**
**Defect:** D-130 — `preview` is an ungated route to the file `render` gates

---

## 1. The decision, and the argument against the other two

**Chosen: retire `preview` entirely** — the CLI command and the module-level
function. `probe` covers looking; `render` covers producing; there is no third
thing.

The shape the brief proposes is the right one and I did not find a better one:
**looking is free, producing the artifact is gated.** What makes it the right
one is that the two halves are different *kinds* of output, not the same output
with different permissions. `probe` writes PNGs into `probe/` — frames you
inspect and throw away, worth ~5 s. `render` writes an MP4 into `out/` — the
deliverable, the thing that gets uploaded, worth ~13 min. Once the line is drawn
between *frames* and *a shippable file*, `preview` has no side of it to stand
on: it produced the shippable file, and it produced it at the same cost as
`render`, for an operator who had not been asked whether anyone had approved it.

**Its original justification had already expired.** The module docstring said so
in as many words: *"Phase 1.5 ships `preview`, not `render`. §10 makes RENDERING
reachable only from APPROVED, and there is no approve command until Phase 7 — so
a command named `render` today would have to bypass the gate it is named after."*
That is a defensible command in Phase 1.5 and an indefensible one from Phase 7
onward. The gate arrived, the three checks arrived in Phase 8, and the command
built to stand in for them stayed. **Nobody re-asked a command what it wrote
after the thing it substituted for was built** — which is the D-130 lesson in
its procedural form.

### Why not (2) make `preview` write somewhere unmistakable

This is the strongest alternative and it still loses, for three reasons.

- **It keeps a fourteen-minute unapproved encoder in the product.** A file in
  `/tmp/agsoc-preview-…/vertical-1080x1920.mp4` is still a finished, uploadable
  video of an episode no human signed. The path it sits at is a convention;
  `cp` is one command. The gate would then protect a *location* rather than the
  *decision*, which is the exact confusion D-130 names.
- **The name would have to lie or the command would have no users.** If it is
  honestly labelled "unapproved", the operator's next question is why they
  waited thirteen minutes for a file they cannot use. The only workflow it
  serves — *watch the whole thing before signing* — is served by approving
  first: approval is cheap, reversible, and editing anything afterwards is
  caught by `approval_drift`. **Approval is not the irreversible step;
  publishing is.**
- **It doubles the encoder's blast radius for free.** Two output conventions
  means `render`'s existence check (`output_path(...).is_file()`) is no longer
  asking about every file the system can produce.

### Why not (3) gate `preview`

The brief answers this one and the answer is right: a gated `preview` is
`render` under a second name. Two names for one gated operation is the
two-paths-to-one-answer shape Phase 7 spent three tasks eliminating (D-113,
D-059) — two call sites to keep identical, and the one nobody exercises daily is
the one that drifts. It also has no user-visible meaning: an operator who has
passed all three checks has *rendered*.

### The precedent this follows

D-119 retired `render.mjs --day` for this exact reason — *"a second way to
render is a second way past the gate"* — and noted that what it produced *"had
been verified against a corpus [by] nobody and signed by nobody"*. The audit
that retired it was aimed at Node. The Python sibling, calling the same
`_encode` from the same repository, survived it. This closes the other half.

### What retiring it costs, stated plainly

**An operator can no longer watch a full-length video before approving.**
`probe` shows one frame per beat and one frame at any `t`, so composition,
type, colour and overflow are all inspectable — but **motion and pacing are
not**. The honest account of the new workflow is: probe → check → approve →
render → watch → (if wrong) edit, which re-drifts the approval, and approve
again. That is one extra signature, not one extra render, and D-116 already
established that no approval can cover the pixels anyway.

---

## 2. Every writer of the gated path, enumerated from the code

The path is `episode.out_dir / f"{fmt}-{w}x{h}.mp4"` — today
`out/vertical-1080x1920.mp4` and `out/wide-1920x1080.mp4`.

Enumerated the way Phase 7's R5 enumerated status writers (from the AST, not by
grepping for symptoms — D-123's rule), in four questions:

| Question | Answer, from the AST | Pinned by |
|---|---|---|
| Who *builds* the path? | `render.py:output_path` — the only function in `src/` containing an `.mp4` literal | `test_the_mp4_path_is_built_in_exactly_one_place` |
| Who *writes* it? | `render.py:_encode` — hands it to `ffmpeg -y`; the only function that passes a path under `out/` to a writing process | `test_every_caller_of_output_path_is_named` |
| Who calls `_encode`? | `render.py:render_episode`, and nothing else | `test_the_only_encoder_is_reached_from_exactly_one_function` |
| Which CLI commands reach it, transitively? | `video_render`, and nothing else | `test_exactly_one_cli_command_can_reach_the_encoder` |

`render_episode` is the gate: `assert_transition` → `approval_drift` →
`stale_reason`, already pinned off the AST by
`test_the_gate_calls_three_named_checks`. So the chain is closed at both ends —
one path, one writer, one caller, one command, and that command asks all three
checks.

**Before the fix, row 3 read `{preview, render_episode}`.** That single extra
entry is the whole defect.

### Everything else that writes into `out/`

Also enumerated, because the question "what else lives in the deliverable
directory" is a different question from "what writes the mp4":

| Writer | What it writes | Gated? |
|---|---|---|
| `plan.py:write_plan` | `out/plan-<fmt>.json` | No — and correctly so |
| `render.py:output_path` | the `.mp4` path (built, then written by `_encode`) | Yes, via `render_episode` |

`plan-<fmt>.json` is an **input** to a render, regenerated from the script and
`series.toml` on every `probe` and every `render`, and it is not shippable.
Pinned by `test_nothing_else_writes_into_the_out_directory`, which fails if any
new function in `src/` touches `out_dir` — including `probe`, if anyone ever
points its frames there (mutant M6).

### Can a *pre-existing* preview artifact be mistaken for an approved one?

**Yes, and this is the residual risk worth reading twice.** Nothing on disk
distinguishes them: `_encode` is one function, so a preview-made MP4 carries the
same `script_file_sha256` and the same `title` in its container metadata as a
gated one. The only external evidence is `script.yaml`'s `render:` record — and
that record keeps only the **last** render attempt (deliberately, per Task 1),
so on an episode rendered in one format the file of the *other* format cannot be
accounted for from the script at all.

Worse, and worth naming: **a stray file at the gated path suppresses the real
render.** `render_episode` counts a format as done purely from
`output_path(...).is_file()`, so a leftover preview artifact makes `render`
refuse with `already rendered: out/vertical-1080x1920.mp4` and keep it. The
operator then ships the ungated file believing the gate produced it. The remedy
exists (`--replace`) but nothing tells them they need it.

**Measured against the operator's real workspace** (worked on a verified copy;
see §5):

```
2026-08-17    draft       out/ absent
2026-08-17b   in_review   out/plan-vertical.json          (no mp4)
2026-08-17c   in_review   out/plan-vertical.json          (no mp4)
2026-08-18    rendered    out/plan-vertical.json, out/vertical-1080x1920.mp4  18,145,286 B
```

`2026-08-18`'s MP4 is accounted for: `script.yaml` carries an `approval` block
signed by Ali Abdukarim at `2026-08-18T22:27:09-05:00` and a `render` record at
`23:04:32`. **There is no ungated artifact in the operator's workspace** — the
`plan-*.json` files in the two `in_review` episodes are probe/plan residue, not
video. No migration is needed. The hazard above is therefore stated for the
general case, not for this machine.

---

## 3. TDD evidence

Two commits, not squashed.

**RED — `c96c435` `test: reproduce D-130 — preview writes the file render gates`**

`tests/test_video_gated_artifact.py`, committed failing. The reproduction is
asserted **on the file, not on the command**: for every video subcommand that is
not `render`, run it against an episode the gate has just refused and assert
`out/vertical-1080x1920.mp4` does not appear. The message is the defect in one
line:

```
FAILED tests/test_video_gated_artifact.py::test_no_second_command_produces_the_file_the_gate_refused
  AssertionError: `agsoc video preview` wrote the gated artifact (exit 0) on a draft the gate refused
5 failed, 4 passed in 4.85s
```

The four that passed are the control (`render` refuses the draft, status stays
`draft`) and the enumeration rows that were already true.

**GREEN — `e5fa8d9` `fix: retire preview — the encoder has one caller and it is the gate`**

`preview` removed from `render.py` and from the CLI; `_encode`'s docstring now
states the one-caller property as a guarantee rather than describing two
callers as a convenience.

**The harness fake WRITES.** `FakeRun` fabricates the PNG and the MP4 each step
promises, because the thing being detected is *a file appearing on disk*. A fake
that produced nothing would have passed this file green with the bypass wide
open — D-035's pattern, and the reason the reproduction is worth what it is.

### The tests that used to drive `_encode` through `preview`

`preview` was also the cheap handle every toolchain test used (no approval to
arrange). Those tests now drive `render_episode` with an approved fixture, and
that is not cosmetic: **a test reaching the encoder by a route the product does
not have would be testing a harness.** The claims are ordering claims about the
gated path ("ffmpeg is checked before any frame is rendered"), and asserting
them anywhere else asserts them about nothing. What stays on `probe` is what
genuinely does not need an approval — plan errors before any subprocess, and
that looking moves no status.

`tests/test_video_format.py`'s wide end-to-end moved to `output_path` plus the
existing gated `WIDE` assertions in `test_video_render_cmd.py`;
`tests/test_video_cli.py`'s two `preview` CLI tests are gone;
`test_preview_no_longer_takes_probe` became `test_preview_is_gone_entirely`.

### The negative assertions were checked for failability (D-131's finding)

Last task found every `assert "--force" not in result.output` unfailable because
Rich splits flags with ANSI codes. **No assertion in the new file reads a
negative out of `result.output`** — they read the filesystem, the command
registry, or the AST. Verified by restoring `preview` in both files and running
without `-x`: six independent tests go red, including the `exit_code != 0` one.

```
FAILED tests/test_video_gated_artifact.py::test_no_second_command_produces_the_file_the_gate_refused
FAILED tests/test_video_gated_artifact.py::test_the_only_encoder_is_reached_from_exactly_one_function
FAILED tests/test_video_gated_artifact.py::test_exactly_one_cli_command_can_reach_the_encoder
FAILED tests/test_video_gated_artifact.py::test_the_video_command_list_is_closed
FAILED tests/test_video_gated_artifact.py::test_preview_is_retired
FAILED tests/test_video_probe_cmd.py::test_preview_is_gone_entirely - assert 0 != 0
6 failed, 24 passed in 0.71s
```

### Suite

```
2061 passed, 6 warnings in 20.89s
```

Baseline was 2053. **R6 held: no test renders a full episode** — every
subprocess is faked and every fixture script is six seconds long.

---

## 4. Mutation sweep — 13/13

Harness: `docs/superpowers/worklog/video/phase-13/task-2-mutants.py`, run with
`PYTHONDONTWRITEBYTECODE=1` (D-100: consecutive mutants land inside one mtime
second and CPython would otherwise import a stale `.pyc` and report the
*unmutated* module as surviving). Exit codes are read from
`subprocess.run(...).returncode`, never from a pipe (D-105).

```
KILLED   M1 the defect itself: `preview` restored, function and command
         1 failed, 1 passed in 8.21s
KILLED   M2 the module-level function comes back, no CLI command
         1 failed, 3 passed in 1.54s
KILLED   M3 a second caller of `_encode` inside src/
         1 failed, 3 passed in 6.75s
KILLED   M4 a CLI command reaches the encoder directly
         1 failed, 1 passed in 1.21s
KILLED   M5 the mp4 path is spelled a second time, inside the encoder
         1 failed, 2 passed in 1.16s
KILLED   M6 `probe` writes its frames into out/ beside the deliverable
         1 failed, 7 passed in 2.20s
KILLED   M7 the status check goes
         1 failed, 27 passed in 3.96s
KILLED   M8 the drift check goes
         1 failed, 29 passed in 4.11s
KILLED   M9 the ledger check goes
         1 failed, 31 passed in 4.31s
KILLED   M10 the encode happens before the gate is asked
         1 failed in 0.78s
KILLED   M11 ffmpeg is no longer required up front
         1 failed, 16 passed in 3.43s
KILLED   M12 the artifact lands beside the script instead of in out/
         1 failed, 7 passed in 2.40s
KILLED   M13 the mp4 loses the script hash that ties it to an approval
         1 failed, 13 passed in 2.86s

13/13 killed
```

M2–M4 are the ones that matter for this task: they are the three shapes a fourth
writer could take — a library function, a helper beside the encoder, and a CLI
command reaching past it — and each dies on the enumeration rather than on a
behavioural test that happened to notice.

---

## 5. The operator's workspace

Backed up **before any test ran**, to a path verified not to exist, **outside
this repository** (so it cannot be swept up by a `git clean` or committed):

```
/Users/aabdukarim/agsoc-workspace-backups/workspace-phase13-task2-20260819-025407

eff44093eb5c7fbe33666b71a20eeaeeae6184fbda935687cff5b483cf762e1c  workspace/.../2026-08-18/out/vertical-1080x1920.mp4
eff44093eb5c7fbe33666b71a20eeaeeae6184fbda935687cff5b483cf762e1c  <backup>/.../2026-08-18/out/vertical-1080x1920.mp4
```

The 18 MB MP4 is byte-identical in the backup. No test touched `workspace/`
(every test sets `AGSOC_WORKSPACE` to a `tmp_path`), `approve` was never run
against it, and the inspection in §2 was read-only.

---

## 6. Concerns

### 6.1 Does any other gated artifact have a second writer? **Yes — the claim ledger.**

The question the brief asks is the right one to carry forward, and the answer is
not "no". `claims.json` is the artifact `approve` binds itself to — it records
`claims_checked_at` and `corpus_sha` from it, and D-113 was explicit that *"the
ledger is required, not recomputed… computing verdicts inside the gate means
signing verdicts nobody displayed."* **It has two writers:**
`cli.py:video_check` and `verify.py:judge_claim`, both through
`verify.write_ledger`.

`judge` writes *after* approval, and none of `render`'s three checks can see it.
Leader-style verification on a throwaway workspace:

```
$ agsoc video check 2026-08-14 --series the-brief      -> exit 0
$ agsoc video approve 2026-08-14 --series the-brief --by "Ali Abdukarim"  -> exit 0
status on disk        : approved
$ agsoc video judge 2026-08-14 --series the-brief --claim c-001 \
      --verdict refuted --refutation "the source says nothing of the kind" \
      --by "Someone Else"                              -> exit 0
adversarial before    : null
adversarial after     : {"verdict": "refuted", ...}
checked_at moved      : False
approval_drift        : None
stale_reason          : None
status still          : approved
```

**A claim was refuted after the signature and the episode still renders.**
`approval_drift` compares the beats digest, `pace` and the series design;
`stale_reason` compares the corpus and the script. Neither compares the
*verdicts*, and `write_ledger` leaves `checked_at` untouched on a `judge`, so
even a timestamp comparison would not catch it.

It is **not** D-130's severity — it produces no artifact, it requires a named
human, and the direction of the change is somebody arguing *more* carefully, not
less. But it is D-130's *shape*: an artifact a gate binds itself to, with a
second writer that moves it after the binding. The fix is small and I did not
make it, because it is a Phase 7/9 gate question and not this task: either
`approve` records a digest of the ledger's findings and `approval_drift`
compares it, or `judge` refuses to write to an episode that is already
`approved`. **The first is better** — it makes the approval cover what was read,
which is D-115's rule, and it costs one field.

The artifacts I checked that are clean: **episode status** (three writers, all
enumerated and pinned, two gated and the third writes what disk already says —
D-059's fix), the **approval record** itself (written only by `approve.py`
through `set_status`'s metadata merge), and **`posted_ids`** in the text pipeline
(`publish_variant` sets it and `save_variant` preserves it; both are behind the
publishing gate, and save-after-every-tweet is the invariant CLAUDE.md names).

### 6.2 A stray file at the gated path still suppresses the render

Covered in §2. Going forward no command can create one, so the exposure is
historical files and hand-copied ones. If it is worth closing: `render` could
refuse `already rendered` only when `script.yaml` accounts for the file, and say
something different — *"a file is here that no render on record produced"* —
when it does not. I did not change the message, because post-fix its inference
("a file at this path was produced by `render`") is now sound, and widening the
task to per-format render records is Task 1's design decision to revisit, not
mine.

### 6.3 What this fix does not establish

Unchanged from Phase 8, and worth repeating because retiring a command can read
as more than it is: the three checks cover what the operator authored and
nothing the renderer is (D-116). A font substitution changes every frame with
all three green. `probe` is still the only answer to that, and it is now the
*only* ungated way to see anything at all — which raises the stakes on it
staying cheap.

### 6.4 D-056 is still open

`ENGINE_DIR` is still `parents[3]` and `engine/` is still unpackaged: `render`
works from a source checkout and nowhere else. Untouched by this task, recorded
because D-120 asked for it to stop being omitted.
