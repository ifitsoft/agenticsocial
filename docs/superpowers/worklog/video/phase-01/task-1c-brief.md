# Task 1c Brief: Pin both transition tables exactly

**Phase:** 1 · **Branch:** `feat/video-phase-01-scaffolding` · **Follows:** `43799e5`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Why

QA mutation-tested `43799e5` with 12 mutants. Nine were killed. Three survived,
all in the same class — an edge *added* to a table that no test forbids:

| Mutant | Consequence |
|---|---|
| `VIDEO_TRANSITIONS[DRAFT] |= {RENDERING}` | **approval-gate bypass** — an unreviewed draft renders |
| `VIDEO_TRANSITIONS[SCHEDULED] |= {RENDERING}` | same bypass, live once v2 gives `SCHEDULED` an in-edge |
| `VIDEO_TRANSITIONS[PUBLISHING] = {FAILED}` | contradicts spec §10's "unreachable, empty" |

The approval gate is the product's central invariant — the spec's §8.4 and §10
both exist to make rendering unreachable without a human. A table that can grow
an edge silently is the one thing that must not be possible. One exact-equality
test per table kills all three and every future member of the class.

## Note on process — this task has no RED phase

The tables are already correct; nothing about behaviour changes. These are
**guard tests**, and a guard test cannot fail before it is written. So the
two-commit rule (D-009) does not apply here, and the evidence that justifies the
test is **mutation kills**, not RED/GREEN. Step 3 is that evidence. One commit.

## Files

- Modify: `tests/test_video_status.py` (append only)

---

- [ ] **Step 1: Append both tests**

```python
# --- exact table pins ---------------------------------------------------------
# QA mutation testing survived three added edges, two of which bypass the
# approval gate (draft -> rendering, scheduled -> rendering). The behavioural
# tests above say what the tables MEAN and carry the reasoning; these two say
# exactly what they ARE. The redundancy is deliberate: intent and tripwire.
#
# If you are changing a table and one of these fails, that is the point. Read
# the docstrings above before widening either dict.


def test_video_transitions_table_is_exact():
    assert VIDEO_TRANSITIONS == {
        Status.DRAFT: {Status.IN_REVIEW},
        Status.IN_REVIEW: {Status.DRAFT, Status.APPROVED},
        Status.APPROVED: {Status.IN_REVIEW, Status.RENDERING},
        Status.SCHEDULED: set(),
        Status.RENDERING: {Status.RENDERED, Status.FAILED},
        Status.RENDERED: set(),
        Status.PUBLISHING: set(),
        Status.PUBLISHED: set(),
        Status.FAILED: {Status.RENDERING},
    }


def test_text_transitions_table_is_exact():
    assert ALLOWED_TRANSITIONS == {
        Status.DRAFT: {Status.IN_REVIEW},
        Status.IN_REVIEW: {Status.DRAFT, Status.APPROVED},
        Status.APPROVED: {Status.IN_REVIEW, Status.PUBLISHING},
        Status.SCHEDULED: set(),
        Status.RENDERING: set(),
        Status.RENDERED: set(),
        Status.PUBLISHING: {Status.PUBLISHED, Status.FAILED},
        Status.PUBLISHED: set(),
        Status.FAILED: {Status.PUBLISHING},
    }
```

- [ ] **Step 2: Run the suite**

```bash
uv run pytest 2>&1 | tail -5
```

Expected: 114 passed. Both new tests pass immediately — that is expected for a
guard test.

- [ ] **Step 3: Prove the guards work — kill the three survivors**

This step is the justification for the task. For **each** of the three mutants
below: apply it to `src/agenticsocial/models.py`, run `uv run pytest 2>&1 | tail -5`,
record the result, then `git checkout src/agenticsocial/models.py` before the next.

1. `Status.DRAFT: {Status.IN_REVIEW, Status.RENDERING}` in `VIDEO_TRANSITIONS`
2. `Status.SCHEDULED: {Status.RENDERING}` in `VIDEO_TRANSITIONS`
3. `Status.PUBLISHING: {Status.FAILED}` in `VIDEO_TRANSITIONS`

Each must now **fail**. Paste the observed failure line for each into your report.
If any mutant still survives, **stop and report it** — the guard is inadequate
and I need to know before this merges.

Finish with `git status --porcelain` and confirm `models.py` is unmodified.

- [ ] **Step 4: Commit**

```bash
git add tests/test_video_status.py
git commit -m "test: pin both transition tables exactly

QA mutation testing survived three added edges, two of which bypass the
approval gate (draft -> rendering, scheduled -> rendering). Exact-equality
pins kill that whole class."
```

---

## Your report

Write `docs/superpowers/worklog/video/phase-01/task-1c-report.md`:

1. **What I added** and why.
2. **Mutation evidence** — a row per mutant: the mutation, the command, the
   observed pass/fail, and which test caught it. Piped output, not transcribed.
3. **Suite before and after**, and the commit SHA.
4. **Issues or concerns** — in particular: we now have four exact-equality
   assertions across this file. QA flagged that a third or fourth is the point at
   which the pattern deserves reconsideration rather than extension. Do you agree,
   and would you collapse any of them? Argue your view; I will act on it.

Do not update `PROGRESS.md` or `DECISIONS.md`.
