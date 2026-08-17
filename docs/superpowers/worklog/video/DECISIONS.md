# Video MVP — Decisions Log

Every adjudicated QA finding and every deviation from the spec, with reasoning.
Leader-owned. An unrecorded deviation is a defect regardless of whether the code
is correct.

Format: `D-NNN · phase/task · verdict · one-line reasoning`

Verdicts: `fix-now` · `defer` · `reject` · `spec-change`

---

## D-001 · project setup · spec-change
**Worklog is tracked in git**, not left in `.superpowers/sdd/` (whose `.gitignore`
is `*`). v1's audit trail exists only on one machine. Reports carrying RED/GREEN
evidence are the record of how the software was built and belong in history.
`.diff` files remain uncommitted — git already stores every diff.

## D-002 · phase 1 planning · fix-now
Episode functions (`create_episode`, `load_episode`, `list_episodes`,
`resolve_episode`) originally took a `ws: Workspace` parameter none of them used.
`Series` already carries `episodes_dir`, so `Series` is the correct scope. Fixed
in the plan before dispatch rather than costing four QA cycles.

## D-003 · phase 1 / task 1 · defer — SHARPENED 2026-08-16
`VIDEO_TRANSITIONS[Status.FAILED] == {Status.RENDERING}` is intentionally
render-only, even though `FAILED` is also reachable from `PUBLISHING`. Video
publishing is out of MVP scope (spec §3.1).

The Task 1 implementer independently flagged this and stated it more precisely
than I had: because the table also contains `RENDERED → PUBLISHING`, the path
`RENDERED → PUBLISHING → FAILED → RENDERING` is *reachable*, so a video **publish**
failure could only be recovered by re-running the expensive render. `FAILED`
cannot reach `PUBLISHING` at all.

Considered removing `RENDERED → PUBLISHING` to make the MVP table render-only,
which would dissolve the ambiguity. **Rejected for now:** spec §10's diagram
explicitly shows `rendered → published`, and deviating from the spec is not the
leader's unilateral call (roadmap §6). MVP never exercises the edge, so it blocks
nothing. **Must be resolved before video publishing is implemented** — raised
with the human 2026-08-16.

## D-005 · phase 1 / task 1 · fix-now
The original Task 1 brief was internally contradictory: add two `Status` members,
do not modify existing tests, keep the suite green. `test_models.py:7`
(`test_status_values_match_spec`) snapshots the whole enum as an ordered list, so
the three cannot hold together. The implementer implemented as written, refused
to edit the existing test, and stopped without committing — exactly correct.

Resolution: Amendment 1 to the brief grants a scoped exception to update that one
snapshot test to the nine-member list. It is a snapshot of an enum this task
deliberately extends; updating it is not weakening a test.

**Process lesson:** the Phase 1 plan's exit criterion "no existing test file was
modified" is wrong as an absolute. Snapshot/inventory tests legitimately change
when the thing they inventory changes. Criterion reworded to: *no existing test
was modified except where the plan explicitly authorises it, with reasoning.*

## D-004 · phase 1 / task 1 · defer
`ALLOWED_TRANSITIONS` gains `RENDERING`/`RENDERED` as empty sets purely so the
table stays total and `table[current]` cannot raise `KeyError`. A text variant
reaching either state is a bug elsewhere. Accepted as the cheapest option that
keeps one enum; revisit if a third lifecycle ever appears.

## D-006 · phase 1 / task 1b · spec-change — HUMAN DECISION 2026-08-16
**Cut `RENDERED → PUBLISHING` from `VIDEO_TRANSITIONS`.** `rendered` is terminal
for the MVP. Resolves D-003, which had been deferred pending this call.

Reasoning: the edge was reachable but never exercised, and it made `FAILED`
ambiguous — with `FAILED → RENDERING` as the only recovery edge, a *publish*
failure could only be recovered by re-rendering an artifact already on disk. A
state machine whose only exit from a state is the wrong one is worse than one
that declines to model the state.

When video publishing lands, the table gains `rendered → publishing` **and**
`failed → publishing` together. `PUBLISHING`/`PUBLISHED` keys stay as empty sets
so the table remains total. Spec §10 updated.

## D-007 · infrastructure · fix-now — HUMAN DECISION 2026-08-16
**Moved `workspace/brief-video/` → `engine/`.** `workspace/` is gitignored
wholesale, so ~1.5k lines of hand-written engine source had no version history,
and Phase 4 modifies `engine.js` on a branch — impossible for an ignored file.
Moved intact so relative paths keep working. Tracked: 11 files, 1562 lines.
Ignored within it: `node_modules/`, `frames/`, `probe/`, `*.mp4`, `*.png`.
Repo still 7.89 KiB with zero media tracked.

Noted while doing this: **everything under `workspace/` remains unversioned** —
including, from Phase 1 onward, the operator's series, episodes, and scripts.
That is correct for a distributed tool (a user's content is not the tool's repo)
but means the operator needs their own backup. Recorded in `CLAUDE.md`.

## D-008 · phase 1 / task 1 · QA adjudication 2026-08-16
QA verdict on `41ad23e`: **changes-required**. It mutation-tested the table —
broke the render path so a render could only fail, never complete — and all 106
tests passed. Adjudication:

| # | Sev | Finding | Verdict |
|---|---|---|---|
| 1 | major | No test exercises `RENDERING → RENDERED`; mutation survived | **fix-now** → Task 1b |
| 2 | major | `FAILED` has one edge; publish failure forces re-render | **resolved by D-006** |
| 3 | minor | `TransitionError`'s defaulted table silently reports the *text* allowed-set to a video caller | **fix-now** → Task 1b. Verified only one construction site, which always passes a table, so making it required is safe |
| 4 | minor | Unguarded `table[current]` raises `KeyError` on a partial caller-supplied table | **defer.** `test_both_tables_are_total` guards the two real tables; a partial table is a programming error, and `KeyError` is an honest signal for one. Revisit if a caller ever builds a table dynamically |
| 5 | minor | Nothing asserts the text table's render entries stay empty | **fix-now** → Task 1b |

Findings 1 and 5 are the valuable ones and both came from mutation testing rather
than reading. Worth keeping that in the QA brief for later phases.

## D-009 · process · fix-now
**Tasks now produce two commits: tests first (failing), then implementation.**
QA on Task 1 reported it *could not verify the RED phase* — test and
implementation arrived in one commit, so there was no independent evidence the
test ever failed. The implementer's pasted output is a claim; git history is
evidence. Cost is one extra commit per task.

Also: implementers must **pipe** command output into their reports rather than
hand-transcribe. Task 1's implementer disclosed it transcribed by hand and caught
its own error doing so — the honesty is welcome, the method is not.

## D-010 · phase 1 / task 1b · leader error, resolved by implementer
Task 1b's brief contradicted itself: Step 4a's prose said "leave `PUBLISHING` and
`PUBLISHED` entries exactly as they are", while the authoritative code block
below it showed `Status.PUBLISHING: set()` where the code had
`{Status.PUBLISHED, Status.FAILED}`.

The implementer followed the code block and justified it from the test:
`test_no_video_state_reaches_publishing` asserts `PUBLISHED not in targets` for
*every* source, so leaving `PUBLISHING: {PUBLISHED, FAILED}` would have kept that
test red. Correct resolution, correctly reasoned, and flagged rather than
silently absorbed.

**Second brief defect in two tasks, both from me.** Pattern: when a brief states
a rule in prose *and* shows the result in code, the two drift. Fix for Task 2
onward — briefs show the final state of any changed block in code and do not
also narrate what to preserve. Code blocks are authoritative; prose explains
*why*, never *what*.

## D-011 · phase 1 / task 1b · verification
RED reproduced independently from git history rather than from the report:
`git checkout 1016c09 -- src/agenticsocial/models.py` against the new tests gives
`3 failed, 16 passed`, matching the prediction exactly. Restored to `HEAD` →
`112 passed`. D-009's two-commit rule justified itself on first use.

## D-012 · phase 1 / task 1b · QA adjudication 2026-08-16
QA verdict on `1016c09..43799e5`: **approve**. 12 mutants, 9 killed, 3 survived.
The gap Task 1b existed to close *is* closed — "render can only fail, never
complete" is now killed by `test_rendering_may_complete`.

| # | Sev | Finding | Verdict |
|---|---|---|---|
| F1 | medium | `DRAFT → RENDERING` added to `VIDEO_TRANSITIONS` passes all 112 tests — an **approval-gate bypass** with no guard | **fix-now** → Task 1c |
| F2 | low | `SCHEDULED → RENDERING` survives; unreachable today, live once v2 gives `SCHEDULED` an in-edge | **fix-now** → Task 1c (same test) |
| F3 | low | `PUBLISHING: {FAILED}` survives; spec §10 says these stay empty, nothing enforces it | **fix-now** → Task 1c (same test) |
| F4 | info | `test_transition_error_requires_an_explicit_table` asserts only "some `TypeError`" | **reject** — the property that matters is preserved; tightening it would test Python, not us |
| F5 | info | The brief contradicted itself; implementer followed the verbatim table | already recorded as D-010 |

All three survivors are one class — *an edge added to a table that no test
forbids* — so one exact-equality pin per table kills the class, not just the
three instances. That is why Task 1c pins both tables rather than adding three
targeted tests.

Severity capped by a real observation from QA: `VIDEO_TRANSITIONS` has **no
consumer in `src/` yet** (`workspace.set_status` still uses the text table), so
F1 is unreachable at runtime today. It stops being unreachable the moment Phase 3
wires the table in — which is exactly why it gets closed now rather than then.

## D-013 · process · clarification
**Guard tests are exempt from the two-commit rule (D-009).** A test that pins
already-correct behaviour cannot have a red phase. Justifying it with a fake RED
would be theatre. The evidence that earns a guard test its place is **mutation
kills**: apply the mutant, show the test fails, restore. Task 1c is the first
task run this way.

## D-014 · process · QA is not infallible
QA's 1b review stated "the brief names `publish.py`; no such module exists".
`src/agenticsocial/x/publish.py` does exist — I verified it. Its *conclusion* was
still correct (that path reaches the table through `ws.set_status`, which keeps
`assert_transition`'s text-table default, so requiring `TransitionError.table` is
safe).

Recorded because the leader's job includes not rubber-stamping the reviewer. A
QA verdict is evidence, not a ruling. Findings get verified before they are acted
on, and so do non-findings.

## D-015 · phase 1 / task 1c · verified, closed
All three surviving mutants killed; 112 → 114 tests. Leader re-verified the one
that matters independently: applying `DRAFT → RENDERING` to `VIDEO_TRANSITIONS`
now fails `test_video_transitions_table_is_exact` (`1 failed, 113 passed`);
restored → 114 passed, tree clean. **The approval-gate bypass is guarded.**

No separate QA pass. A test-only commit whose entire justification is
reproducible mutation evidence is cheaper for the leader to verify directly than
to hand to a reviewer. Not a precedent for source changes.

## D-016 · phase 1 / task 1c · assertion redundancy — implementer's call adopted
Asked whether four exact-equality assertions is too many. The implementer argued
the smell points at the *old* per-key assertions, not the new pins, but that
three of the four still earn their place: their docstrings carry the reasoning
(D-006, spec §3.1) and their names state the broken invariant in the failure
line, where a whole-table pin only reports "the dict differs". The maintenance
friction of updating two tests is itself the feature — it routes whoever widens a
table past both the tripwire and the rationale.

Its one exception: **delete `test_published_is_terminal_for_video`** — the only
one of the four with no docstring and no decision record, so redundancy without
compensating rationale. **Adopted**; folded into Task 2 Step 0 as its own commit,
because the leader does not edit code.

Ceiling it set, and I am holding us to it: two whole-table pins is the maximum. A
third table gets a parametrised pin over `(table, expected)`, not a third
copy-paste, and no further per-key equality tests go in this file.

## D-017 · process · leader writes during agent runs
Task 1c's implementer noticed `DECISIONS.md` changing mid-session and flagged it
rather than ignoring it — correct instinct, and it was me. Benign: agents never
touch `docs/superpowers/worklog/`, and nothing under `docs/` is ever staged by a
task. Briefs from Task 2 onward say so explicitly, so the next agent does not
spend attention on it.

## D-018 · project-wide policy — raised by the Task 2 implementer
**An addressed operation may raise. An enumerating operation must not die over
one bad member.**

`load_series("the-brief")` / `load_episode("2026-08-14")` name one thing — if it
is corrupt, raise; there is no partial answer. But `agsoc series list` and
`agsoc video list` are the *diagnostic* commands. An operator runs them precisely
when something is broken and they do not know what. A single malformed file must
not make the one tool that could say "the-brief is fine, cardio-weekly has a
syntax error on line 4" refuse to say anything at all. A ten-series workspace
becoming unlistable over one typo is the failure mode.

Shape, with no duplicated directory logic:

```python
def series_slugs(ws) -> list[str]:      # cheap, cannot fail
def list_series(ws) -> list[Series]:    # strict; == [load_series(ws, s) for s in series_slugs(ws)]
```

The CLI iterates the enumerator and loads each item in a try/except, so
presentation policy stays out of `series.py` / `episode.py`. Exit code stays 0 —
the command succeeded at answering the question it was asked.

Applies to: `episode_ids` (Task 3, specified before dispatch) and `series_slugs`
(Task 4, alongside the CLI that needs it).

## D-019 · phase 1 / task 3 · leader caught this while writing the brief
Drafting D-018's question for the Task 3 implementer surfaced a defect in my own
design: `resolve_episode` was written to match over `list_episodes()`, the
*strict* loader — so one corrupt episode would break resolving a **different,
healthy** one. That is exactly the failure D-018 exists to prevent, reintroduced
one function below it.

Fixed before dispatch: `resolve_episode` matches over `episode_ids()` and calls
`load_episode` only on the one it resolves. Resolving the corrupt episode itself
still raises — that is an addressed operation. Two tests pin both halves.

Worth noting the mechanism: the defect surfaced because I was writing a question
for someone else rather than describing my own solution. Asking "is this a
defect?" made me check, and it was.

## D-020 · phase 1 / task 2 · QA adjudication 2026-08-16
QA verdict on Task 2: **changes-required**. 34 mutants, 28 killed, 6 survived.
QA confirmed the implementation was a character-exact transcription of the brief,
so **every finding is a defect in my specification**, not implementer error.

| # | Sev | Finding | Verdict |
|---|---|---|---|
| F1 | high | Hostile `name` corrupts both `series.toml` and `coverage.json`, misreports it as operator error, and leaves a partial dir that blocks retry | **fix-now** → 2b |
| F2 | med | `enabled = [1,2]` raises `TypeError` from `join`; `enabled = "vertical"` iterates characters — both escape the `SeriesError` contract on the *strictly validated* path | **fix-now** → 2b |
| F3 | med | `series = "hello"` → `AttributeError`; `series.toml` as a directory → `IsADirectoryError` | **fix-now** → 2b |
| F4 | med | 4 loader defaults unreachable by tests + the on-disk dir name pinned only tautologically | **fix-now** → 2b |
| F5 | low | `warm_acts` written by the scaffold, silently dropped by the loader | **fix-now** → 2b (one line) |
| F6 | low | No slug validation: `slug="../escape"` writes outside `series_dir` | **fix-now** → 2b |
| F7 | note | `bool`/`int` wart live (`target_sec = true` → a 1-second episode); `list_series` strictness | **fix-now** (bool) / **D-018** (list) |

Everything is fix-now because this is the operator's first contact with the
product, and because the whole set is one cohesive hardening pass over one file.
Splitting it across phases would cost more than doing it now.

**F1 is the important one.** Not because it is hard, but because of its shape: it
corrupts data, then *misattributes the corruption to the operator*, then blocks
the obvious recovery. A bug that lies about whose fault it is costs far more
support than one that simply crashes.

**Root-cause note on F4/mutant 6.** `assert s.dir == ws.series_dir / "the-brief"`
compares an attribute against itself — renaming `series/` to `shows/` passed all
130 tests. Spec §5 fixes that name; a test asserting a value against the same
value it derives from asserts nothing. Watch for this shape in future reviews;
it is invisible to coverage and to reading.

## D-021 · process · the brief is now the main defect source
Four of my briefs have contained defects (D-005, D-010, D-019, D-020) against
zero implementer errors. Every implementation so far has been a faithful
transcription; every bug has been mine, written upstream.

That is the system working as designed — briefs are cheap to fix, and QA plus
implementers have caught all of them before merge. But it locates the bottleneck:
**reviewing my brief is worth more than reviewing the code it produces.**

Consequences adopted: briefs carry the *whole* final file when a rewrite touches
most of it (Task 2b does), rather than prose describing edits; and every brief
now ends with questions that invite attack on the design rather than
confirmation. D-019 was found precisely by writing such a question.

## D-022 · phase 1 / task 2c · my fix for D-020 was itself broken
Task 2b replaced naive interpolation with `json.dumps` as a TOML basic-string
escaper, on my instruction. **That was wrong.** `json.dumps` defaults to
`ensure_ascii=True`, which encodes non-BMP characters as UTF-16 surrogate pairs;
TOML v1.0.0 requires every `\uXXXX` escape to name a Unicode *scalar* value, and
surrogates are not.

Leader-verified end to end — both fail against committed code:

```
--name "The Brief 😀"   → SeriesError: malformed series.toml — Escaped character
--name "北京 𠀋"          is not a Unicode scalar value
```

Any emoji, historic script, or CJK extension-B ideograph makes
`agsoc series new` impossible. **And it fails in the exact D-020 shape it was
written to fix**: we write the file, then blame the operator for it being
malformed. The `rmtree` cleanup from 2b downgrades it from *unrecoverable* to
*permanently impossible*, which is not much of an improvement.

The obvious correction is also wrong: `ensure_ascii=False` fixes non-BMP but
emits raw U+007F, which TOML forbids in a basic string. Neither flag setting is
correct alone. Task 2c writes an explicit escaper: literal UTF-8 for everything
printable, escapes only for the quote, the backslash, C0 controls and U+007F.

**How it was found.** Not by QA and not by me — by the Task 2b implementer
answering the section-5 question *"is `json.dumps` genuinely safe as a TOML
escaper? Name any input where TOML and JSON escaping diverge."* It went and
looked, and found one.

That is the third defect surfaced by an adversarial closing question (D-019,
D-016, this). The questions are now the highest-yield part of the brief format,
and they work because they ask for an attack rather than a confirmation. A brief
ending "let me know if you have concerns" would have caught none of these.

## D-023 · process · scope discipline on hardening chains
Task 2 has now spawned 2b and 2c. That is a chain, and chains are where scope
quietly doubles. Holding the line: 2c fixes the escaper and shape-validates the
last two unvalidated fields, and Task 2 is then **done** regardless of what else
turns up in `series.py`. Anything further becomes a Phase 1 follow-up item, not
a 2d.

Reason to be strict: every one of these findings is real, so there is no natural
stopping point from correctness alone. The stopping point has to come from
scope. `series.py` is 150 lines of config loading — if it needs a fourth pass,
the problem is the design, not the coverage.

## D-024 · phase 1 / task 2c · closed. 184 tests, 6/6 mutants killed
Leader-verified: `--name "The Brief 😀"` and `--name "北京 𠀋"` now scaffold and
round-trip, written as literal UTF-8 with no surrogate escapes. Mutant 2
(`ensure_ascii=False`, the plausible wrong fix a future maintainer reaches for)
dies to three tests — decisively to `test_del_and_control_chars_are_escaped_not_literal`,
which asserts on file bytes rather than the round trip.

First task in the phase with **no brief defect**. The change: the brief carried
the whole final function rather than prose describing an edit (D-021).

**No per-task QA pass on 2c.** Deliberate, and the reasoning matters more than
the saving: 2c is narrow, and its six-mutant sweep is stronger evidence than a
read-through would be. `series.py` still gets a full adversarial review at the
phase gate, which the roadmap requires anyway. Skipping *because a reviewer might
find more* would have been the wrong reason; skipping because the phase gate
covers it is not. Recorded so the phase gate is not quietly skipped too.

## D-025 · phase 1 · Task 5 created — the config validation contract
2c's closing question found four fields still reaching the system unvalidated.
Per D-023 these do **not** become a 2d. They become **Task 5**, run after Task 4
so it is informed by what the CLI actually needs, and covering series *and*
episode validation in one consistent pass:

| Field | Hole | Why it matters |
|---|---|---|
| `tolerance_sec` | accepts `"eight"`, `-99`, `true` | sits one line below `target_sec`, which is strictly validated for exactly this reason; Phase 4 does arithmetic with it |
| `name`, `byline` | accept `5`, `["a"]` | `Series.name` becomes an int; a later `_toml_str(name)` raises `TypeError` far from the cause |
| `register` | accepts `"shouty"` | Phase 4 *branches* on it, so a typo silently selects a default. Unlike `cadence`, which is explicitly advisory |
| `design.*` values | `accent = 5` loads | Phase 4 interpolates these into rendered output — a type hole and an escaping-policy question |

**Lone surrogates go to Task 4 instead**, because that is where they become
reachable. Python decodes `sys.argv` with `surrogateescape`, so any non-UTF-8
byte in a CLI argument arrives as U+DC80–U+DCFF — verified: `$'caf\xe9'` →
`'caf\udce9'`. No escaping can save it; UTF-8 cannot encode a non-scalar. Today
it would surface as a raw `UnicodeEncodeError` traceback from inside
`atomic_write` — the D-020 shape once more. The fix belongs at the boundary where
operator input enters, which is the CLI.

## D-026 · phase 1 / task 3 · two documents CONFIRMED — with a different reason
The Task 3 implementer argued for collapsing `script.yaml` to a single document
and demolished my stated rationale, correctly. I had written: "beats is
structured data, so parse it with YAML rather than `frontmatter.parse`." That
argues *YAML over markdown* and says **nothing** about one document versus two.
It also found my claim "these are not frontmatter" is false at the byte level —
this repo's own `frontmatter.parse` reads a `script.yaml` **successfully**,
returning correct metadata and the beats as an unparsed string.

**Decision: keep two documents. The real reason is byte preservation.**

- Spec §10 binds approval to `script_sha256` and refuses to render a changed
  script. Re-serialising beats on a status write fires drift detection on churn
  we caused ourselves.
- The Phase 2 `storyboard` skill writes deliberate formatting and comments;
  `yaml.safe_dump` destroys both. `agsoc video approve` must not reflow an
  operator's script.
- A beats syntax error must not stop you reading the status — D-018 one level
  down.

None of those held, because `_read` parsed document 2 and `_dump` re-serialised
it. The implementer's diagnosis was exact: **"the current shape has the costs of
one design and the benefits of neither."** Task 3b makes Phase 1 never parse
document 2 — split textually, re-emit verbatim. Simpler than what existed, and
it actually delivers the isolation the form was supposed to buy.

The `frontmatter.parse` trap stays real. Mitigated with a loud module docstring;
Phase 3's brief must name the correct parser explicitly.

## D-027 · phase 1 / task 3 · data loss, reproduced
`_read` substituted `{"beats": []}` whenever document 2 was not a mapping — which
includes beats written as a bare YAML **sequence**, a natural shape — and
`set_status` then wrote the substitute to disk. A third document vanished the
same way. Silently, with no error.

The tell the implementer named: `set_status` guaranteed byte-identity when a
transition was *rejected*, but destroyed document 2 when it was *accepted*. My
docstring claimed document 2 "must survive every write here untouched." It was
aspirational.

Related, and the reason the suite did not catch it: **every corrupt-episode
fixture I wrote used `status: banana`, which is valid YAML.** Nothing in 210
tests ever handed the parser something unparseable, so `_read`'s missing
try/except was invisible — and Task 4's `except EpisodeError` would have
tracebacked on `ScannerError` in `agsoc video list`, the exact command D-018
exists to keep alive.

**Lesson for future briefs: a "corrupt input" fixture that is still
syntactically valid tests the validator, not the parser.** Check that
distinction when writing negative tests.

## D-028 · process · scope cap on Task 3
Task 3 → 3b, and that is where it stops, same rule as D-023. 3b fixes the data
loss, the error contract, `create_episode` cleanup, and the `.exists()`/`.is_file()`
inconsistency. Anything further about `episode.py` joins Task 5's consolidated
validation pass rather than becoming a 3c.

## D-029 · phase 1 / task 3b · verified, closed. 224 tests, 6/6 mutants killed
`_compose` re-serialising beats and `_split` collapsing to one document are each
killed by multiple independent tests. Document 2 is now split textually and
re-emitted byte-for-byte; Phase 1 never parses it.

**One reported finding is wrong, and checking it mattered.** The implementer
reported that CRLF line endings break `_split` — "a Windows editor save bricks
the episode". Leader-verified through the production path: it works.
`Path.read_text()` opens in text mode with universal newlines, so `\r\n` becomes
`\n` before `_split` sees anything. It presumably tested `_split` in isolation
rather than through `_read_meta`.

| Case | PyYAML | Ours | Verdict |
|---|---|---|---|
| LF | 2 docs | OK | — |
| CRLF | 2 docs | **OK** | **not a defect** — universal newlines |
| `--- ` trailing space | 2 docs | `EpisodeError` | real, → Task 5 |
| no leading `---` | 2 docs | `EpisodeError` | real, → Task 5 |

Second time a subagent's headline claim did not survive verification (D-014 was
the first). Both times the *conclusion* was partly right and the *reasoning* was
not. The rule holds: run it before acting on it, including — especially — when
the finding is alarming and the agent sounds certain.

The two genuine cases are "we reject a file PyYAML accepts". No data loss (the
read fails before any write), but the error blames the operator's file for a
YAML bug that does not exist — the D-020 shape yet again. Fix is a multiline
`^---[ \t]*$` regex instead of a literal `find`.

**Routed to Task 5, not a 3c** (D-028). Task 5's charter widens from "config
validation" to **"input robustness and validation"**, covering: the four
unvalidated `series.toml` fields (D-025), lone surrogates if Task 4 does not
close them, these two separator cases, and `_compose`'s `beats: []` default.

## D-030 · phase 1 / task 3b · two accepted design costs, stated plainly
Both are consequences of the D-026 design, not defects, but they should be
written down rather than discovered later:

1. **Document 1's comments and formatting are destroyed on every status change.**
   `_compose` runs `safe_dump` over the metadata dict. The "operator formatting
   survives" guarantee covers *beats only*. Acceptable: document 1 is
   machine-written (episode id, series, status, pace); document 2 is the human
   and agent artefact. Worth saying because the docstring could be read as
   promising more than it delivers.
2. **`set_status` will approve an episode whose beats are syntactically broken**,
   re-emitting the broken bytes unchanged. Correct under this design — Phase 1
   does not own beats — but it means *`set_status` succeeding does not imply a
   renderable script*. The approve gate in Phase 7 must validate the script
   itself, not infer validity from a successful transition. Carried forward as a
   Phase 7 requirement.

The implementer also flagged that
`test_status_is_readable_even_when_beats_is_unparseable` does not kill mutant 1,
because unparseable beats never reach a write path anywhere in the suite. True,
and honest of it to report a gap in its own evidence rather than let the mutant
table look cleaner than it is.

---

## Open risks carried from the spec

- Mechanical verifier too strict → operators override reflexively → gate becomes
  theatre. Track override rate from Phase 5 onward.
- `custom` beat ratio above ~15% means the declarative type catalogue is wrong.
  Track from Phase 4.
- ~~Engine source untracked~~ — **resolved 2026-08-16, see D-007.**
- The operator's `workspace/` content (series, episodes, scripts, claims) is
  unversioned by design. No backup story yet. Not a code risk; is a data risk.
