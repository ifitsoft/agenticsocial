# Phase 1 Gate: whole-branch adversarial review

**Branch:** `feat/video-phase-01-scaffolding` vs `main`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

You are reviewing an entire phase, not a task. Nothing here has been merged. Your
verdict decides whether it does.

## What this phase was supposed to deliver

From `docs/superpowers/plans/2026-08-16-phase-01-scaffolding.md`:

> Create the on-disk structure and status machine for video series and episodes,
> so later phases have somewhere to write and a lifecycle to move through.

Four tasks were planned. Nine were run — 1, 1b, 1c, 2, 2b, 2c, 3, 3b, 3c, 3d, 4,
4b, 5. Every extra task came from a defect found by an implementer or a reviewer.

## Read these first

- `docs/superpowers/specs/2026-08-15-agenticsocial-video-mvp-design.md` §§3, 5, 6, 7, 10
- `docs/superpowers/plans/2026-08-16-phase-01-scaffolding.md` — the plan and its exit criteria
- `docs/superpowers/worklog/video/DECISIONS.md` — D-001..D-040, the design intent you review against

**Do NOT read** any `task-*-report.md`. Those are implementers' accounts of their
own work; reading one makes you review the explanation instead of the code.

## Scope

```
git diff main..HEAD -- src tests
git log --oneline main..HEAD
```

Source under review: `src/agenticsocial/video/` (`models.py`, `series.py`,
`episode.py`, `cli.py`), plus the changes to `src/agenticsocial/models.py`,
`src/agenticsocial/workspace.py`, `src/agenticsocial/cli.py`.

## Mandatory coverage — a debt this review is settling

**`series.py` never received a per-task QA review.** Task 2c's changes were
accepted on mutation evidence alone, on the explicit understanding that this
gate would cover them (D-024). That promise comes due now. Give `series.py` at
least as much attention as `episode.py`, which has had four reviews.

## What to attack

**1. The approval gate.** Spec §8.4 and §10 make rendering unreachable without a
human. Try to reach `RENDERING` from any state other than `APPROVED`, through any
public function. Try to reach it via a stale in-memory `Episode`, a hand-edited
`script.yaml`, a status the enum accepts but the table does not, and a
caller-supplied transition table.

**2. Path safety.** A verified escape was fixed in Task 5 (D-038):
`--series ../../outside` wrote outside the workspace. **Assume it is not the only
route.** Try absolute paths, symlinks at every level (`series/`, a series dir,
`episodes/`, an episode dir, `script.yaml` itself), `AGSOC_WORKSPACE` pointing
somewhere hostile, a `series.toml` whose contents reference other paths, and
unicode that normalises to `..` or `/`. Run the **real CLI in a subprocess** —
`CliRunner` has already been shown to hide behaviour (D-035).

**3. Byte preservation.** Spec §10 binds approval to `script_sha256`. Four tasks
went into making `set_status` leave the beats document byte-identical. Break it.
Odd separators, mixed line endings, no trailing newline, a `---` line inside
beats, block scalars, BOM, NUL, astral characters, repeated status cycles.

**4. Harness blindness (D-035).** Three times a green test hid a live bug because
the test's own harness performed the transformation under test. **Audit the test
suite for more of it.** For each negative test, ask: *what would this test do if
the code did nothing at all?* If the answer is "pass", it is a finding. Known
forms: a fixture invalid in the wrong dimension; symmetric encode/decode either
side of an assertion; a runner converting failures into return values.

**5. Sibling asymmetry (D-036).** Three separate defects came from a guard added
to one module and never its sibling. `series.py` and `episode.py` should now be
symmetric wherever they do the same job. List every remaining difference —
error-message shape, guard order, helper structure, `is_file()` vs `exists()`,
cleanup on failure. A long list is more useful than a clean bill of health.

**6. Mutation testing across the phase.** This has found real bugs on every task.
Prioritise `series.py` (the unreviewed module) and the interaction between
modules. Report survivors and say which are equivalent mutants.

**7. Spec coverage.** Walk spec §§5, 6, 10 and the plan's File Structure table.
Is every Phase 1 requirement implemented, and is anything implemented that the
plan did not authorise?

## Known and accepted — do not re-report as new

Recorded in D-040 as deliberately deferred past this gate:

- `%YAML` directive, leading blank line, no leading `---`, and UTF-8 BOM in
  `script.yaml` all raise `EpisodeError` though PyYAML accepts them
- `tolerance_sec`, `name`, `byline`, `register`, `design.*` accept wrong types
- metadata (document 1) comments and block scalars are reflowed by `safe_dump`
- `list_series`/`list_episodes` are strict by design; the CLI uses the
  enumerators (D-018)

Do tell me if you think any of these is *harm* rather than confusion — that is
the line D-040 draws, and it is a judgement I may have got wrong.

## Output

Write to `docs/superpowers/worklog/video/phase-01/phase-gate-review.md`:

- **Verdict:** `merge` / `merge-after-fixes` / `do-not-merge`
- **Findings** ranked by severity, each with file:line, a concrete failure
  scenario, and a suggested fix
- **Harness-blindness audit** — every test you believe cannot fail
- **Sibling asymmetry list** — every remaining difference between the two modules
- **Mutation results** — what you tried, what survived
- **Spec coverage** — anything in Phase 1 scope with no implementation, or
  implemented without authorisation
- **What I verified** and **what I could not verify**

Do NOT commit. Do NOT leave any source or test file modified — restore
everything and confirm the tree is clean. `docs/` may change while you work; that
is the project leader, not interference. Never stage anything under `docs/`.

Final message: the verdict, one line per finding, and — plainly — whether you
would put your name on merging this to `main`.
