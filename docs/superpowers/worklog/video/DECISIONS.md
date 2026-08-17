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
| CRLF | 2 docs | parses OK | **RETRACTED — it IS a defect, see D-031** |
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

## D-031 · phase 1 / task 3c · I RETRACT D-029's CRLF verdict. QA was right.
D-029 declared the CRLF finding "not a defect". **That was wrong.** QA disproved
it and I reproduced the disproof:

```
beats before: b'beats:\r\n  # a comment\r\n  - type: statement\r\n'
beats after : b'beats:\n  # a comment\n  - type: statement\n'
BYTE-IDENTICAL: False
```

`set_status` rewrites every byte of a CRLF beats document — the exact
`script_sha256` drift (spec §10) that D-026 gives as *the reason* for the
two-document design.

**The error was mine and it is worth naming precisely: I verified a proxy.** The
guarantee is *byte identity*. I tested that the file *still parses* and that the
status *still loads*, saw green, and declared the finding closed. Both of those
can be true while every byte changes. A confident correction built on the wrong
property is worse than no correction, because it closes the question.

The chain, in full, because each link is instructive:

1. The Task 3 implementer flagged CRLF — right instinct, wrong mechanism (it
   blamed `_split`; the real cause is `read_text`'s universal newlines).
2. I "corrected" it by testing parseability — wrong property, confidently stated.
3. QA tested byte identity and caught both of us.

D-014 said a reviewer's verdict is evidence, not a ruling. The symmetric half now
also holds: **the leader's verification is evidence, not a ruling.** What makes
it evidence is testing the property under contract, not a property nearby.

QA also found *why* the suite missed it: every preservation test uses
`write_text`/`read_text`, so newline translation happens on both sides and
cancels out. **The tests pinned content, not bytes** — and four whitespace
mutants lived in that gap. Same family as D-027's "corrupt fixture that is still
valid YAML": a test whose setup and assertion share a transformation cannot see
that transformation.

**Task 3c fixes it, and this is not a D-028 breach.** D-028 caps *additional*
scope on `episode.py`; 3b's own stated contract is not met. Finishing a task is
not extending it.

## D-032 · phase 1 / task 3b · QA findings adjudicated
| # | Sev | Finding | Verdict |
|---|---|---|---|
| F1 | med-high | CRLF beats rewritten on every status change | **fix-now** → 3c (D-031) |
| F2 | med | Preservation tests pin content, not bytes; 4 mutants survive there | **fix-now** → 3c |
| F3 | med | `episode_ids` raises `PermissionError`; `create_episode` raises `FileExistsError` on a dangling symlink — both escape `except EpisodeError` | **fix-now** → 3c. Task 4 depends on this contract |
| F4 | low | `create_episode(series, "../escape")` writes outside `episodes_dir` | **Task 5** — mirrors series slug validation, same fix shape |
| F5 | low | `resolve_episode(series, "")` resolves the only episode | **fix-now** → 3c (two lines) |
| F6 | low | Stale `Episode` can regress `approved` → `in_review`; no disk re-check | **Phase 7** — the approve gate owns freshness |
| F7 | note | `%YAML` directive / leading blank line accepted by PyYAML, rejected by us | **Task 5** — third member of the separator family |

QA verified a large amount that did *not* break, which is worth recording: block
scalars containing `---`, metadata forging a separator, 3rd/4th documents,
bare-sequence and scalar beats, NUL bytes, 200KB lines, U+2028, missing trailing
newline. It found no case where `_split` accepts a file PyYAML rejects. It also
identified one *equivalent* mutant (subdirs created after the script) and said so
rather than counting it as a survivor.

---

## Open risks carried from the spec

- Mechanical verifier too strict → operators override reflexively → gate becomes
  theatre. Track override rate from Phase 5 onward.
- `custom` beat ratio above ~15% means the declarative type catalogue is wrong.
  Track from Phase 4.
- ~~Engine source untracked~~ — **resolved 2026-08-16, see D-007.**
- The operator's `workspace/` content (series, episodes, scripts, claims) is
  unversioned by design. No backup story yet. Not a code risk; is a data risk.

## D-035 · process · THE pattern of this phase: harnesses that hide the bug
Three times now a test has been green while the bug it targeted was live, and
every time for the same reason: **the test's own harness performed the
transformation the test was meant to detect.**

| Decision | Harness | What it hid |
|---|---|---|
| D-027 | corrupt fixture was still valid YAML | the missing parser guard |
| D-031 | `write_text`/`read_text` translated newlines on *both* sides | `set_status` rewriting every byte |
| D-035 | `CliRunner` catches exceptions by default | uncaught tracebacks reaching operators |

Leader-verified for the third:

```
exit_code = 1        output = ''        exception = ValueError: uncaught crash
  assert exit_code == 1              -> True   (passes)
  assert "traceback" not in output   -> True   (passes)
```

An uncaught crash is byte-identical, from the test's view, to a clean `_fail`.
That is why the Task 4 mutant disabling UTF-8 validation survived.

**The check to run on every negative test from here on:** *what would this test
do if the code did nothing at all?* If the answer is "pass", the harness is
neutralising the thing under test. Three concrete forms to watch: a fixture that
is invalid in the wrong dimension; a symmetric encode/decode on both sides of an
assertion; and a runner that converts failures into return values.

This is worth more than any single bug found in Phase 1.

## D-036 · phase 1 / task 4 · fixed one module, forgot its sibling
Task 4 Step 0 added a `UnicodeDecodeError` guard to `episode.py`. `series.py` has
the identical hole and I never looked. Leader-verified: one cp1252-saved
`series.toml` makes `agsoc series list` die with a raw traceback — the exact
D-018 failure this phase exists to prevent, in the command it exists to protect.

Same shape: `series_slugs` lacks the `OSError` guard `episode_ids` has, with the
sibling's explicit comment sitting right there explaining why it needs one.

**Sibling asymmetry is now a standing review question.** Task 4b's brief asks
its implementer to compare the two modules function by function on the
assumption I made this mistake elsewhere too. When a fix lands in one of a
matched pair, checking the other is not optional.

## D-037 · phase 1 / task 4 · QA adjudication
Task 4: 272 tests, 3 commits, 4 of 5 mutants killed.

| # | Finding | Verdict |
|---|---|---|
| Mutant 3 survived — the D-025 surrogate test is vacuous | **fix-now** → 4b (D-035) |
| (a) slug/id > 255 chars → uncaught `OSError` | **fix-now** → 4b. Reachable by pasting a URL |
| (b) non-UTF-8 `series.toml` kills `series list` | **fix-now** → 4b (D-036) |
| (c) `series_slugs` lacks the `OSError` guard | **fix-now** → 4b |
| (d) write-path `OSError` in both `new` commands | **fix-now** → 4b |
| Q1: `series list` prints `0 episodes` when the count is unreadable | **fix-now** → 4b. `0` is a claim; `?` is the truth, and still satisfies D-018 at exit 0 |
| Q2: `--series` autocreates only `default` | **keep.** The implementer's reasoning is right: `default` is a name the operator never typed, `nope` is one they did — auto-creating `--series the-breif` would silently misplace an episode. Only the `--series` help text needs to mention it |

The implementer found these by running the real CLI in a subprocess, having
discovered that rich interleaves ANSI escapes *inside* the literal string
`Traceback (most recent call last)`, which defeated its first detector. It said
so rather than trusting its own tooling — the same instinct that makes the rest
of its report worth reading.

## D-038 · phase 1 / task 5 · workspace escape, verified. Naming ≠ path safety
Leader-verified against the real CLI:

```
$ agsoc video new 2026-08-14 --series ../../outside
created episode ../../outside/2026-08-14 …
*** ESCAPED WORKSPACE *** /private/tmp/t5c/outside/episodes/2026-08-14/script.yaml
```

`scaffold_series` calls `_validate_slug`; **`load_series` does not** — and
`video new --series` reaches `create_episode` through `load_series`. It escapes
only when the traversal target is itself a valid series directory, which is why
my first probe reported it safe: the OS returns ENOENT through a missing
component. I reproduced the implementer's exact condition rather than trusting
either result.

**24 traceback probes missed it because it is not a crash. It succeeds.** A
correctness sweep that only looks for exceptions cannot see a function doing the
wrong thing calmly.

**The fix introduces a distinction that was missing:**

- **Naming rules** govern what agsoc will *create* — lowercase, digits, hyphens,
  length cap. `scaffold_series` only.
- **Path safety** governs what agsoc will *touch* — every function turning a
  caller-supplied name into a path: `load_series`, `load_episode`,
  `resolve_episode`, both creators.

Kept separate deliberately. A directory a human named `My-Show` must stay
loadable; `../../outside` must not, whoever made it. Folding path safety into
`_validate_slug` would have broken the first case to fix the second.

**Third instance of D-036.** `episode.py` has had three tasks of attention;
`series.py` receives each fix late or never. Task 5 ends with a mandatory
function-by-function sweep of both modules, and I asked for a long list rather
than a clean bill of health.

## D-039 · phase 1 / task 4b · adjudication, including two of my own errors
279 tests. 3 of 5 mutants killed, and **both survivors were my specification
errors, not gaps in the work**:

- **Mutant 1 (`catch_exceptions=False`) is mis-specified.** It only matters when
  something raises; against fixed code it is a semantic no-op no test can kill.
  It is a mutant of the *detector*, so it must be run combined with a code
  mutant. The implementer ran my version as written, then constructed the correct
  combination itself using Task 4's actual survivor: killed under the new
  harness, **passes under the old one**. Same test, same code, different harness.
  That is the proof I asked for, obtained despite my brief rather than because
  of it.
- **Mutant 4 (length cap) survived for a subtle reason.** My own Step 2d masks
  Step 2c: with the cap removed, the errno string `[Errno 63] File name too long`
  contains the literal `"too long"`, so my assertion passes through the `OSError`
  path. The cap was unpinned. Fixed in Task 5 Step 1b by asserting `"limit 64"`.

Notable non-finding: **zero** pre-existing tests changed behaviour under
`catch_exceptions=False`. The harness was not hiding a live bug in covered code —
it was hiding the *absence* of coverage. Worth recording, because it means D-035
cost us missing tests, not silent breakage.

`MAX_NAME_LEN = 64` confirmed reasonable: `textutils.slugify` already truncates
at 60, real ids run 10–35 characters, and `NAME_MAX` is 255 — so the cap is
validation-time rather than platform-derived, which was the point.

## D-040 · phase 1 · scope: what does NOT get fixed before the gate
Verified still-broken, and deliberately **not** in Task 5:

| Case | Behaviour |
|---|---|
| no leading `---` | `EpisodeError` — PyYAML accepts it |
| `%YAML` directive first | `EpisodeError` |
| leading blank line | `EpisodeError` |
| UTF-8 BOM | `EpisodeError` |
| `tolerance_sec`, `name`, `byline`, `register`, `design.*` unvalidated | wrong types load silently |
| metadata block scalars reflowed by `safe_dump` | semantic loss in document 1 |

All produce a clear error or affect only machine-written data. None loses
operator work, none escapes the workspace, none reaches a traceback. They are
robustness gaps, not harm.

**These become Phase 2/3 follow-ups, carried in `PROGRESS.md`.** The separator
cases belong with Phase 3's real script parser, which will rewrite `_split`
anyway; the field validation belongs with Phase 4, which owns what those fields
mean. Fixing them now means specifying behaviour for consumers that do not exist.

The line I am drawing: **before the gate, fix what causes harm — escapes,
tracebacks, silent data loss. After the gate, fix what causes confusion.**
Without a stated line this phase does not end, because every finding so far has
been real and there is no natural stopping point from correctness alone.

## D-041 · phase 1 / task 5 · symlinks are an operator affordance, not an escape
Leader-verified after Task 5's fix:

```
--series ../../outside   -> refused: "unsafe series slug ... not a path"   ✓
--series link            -> created /private/tmp/t5sym/outside/episodes/…  (still escapes)
```

A symlinked series directory — or a symlinked `episodes/` inside a legitimate
series — still writes outside the workspace. Name-based guards are structurally
blind to it; only `Path.resolve()` + `is_relative_to(ws.root)` would catch it.

**Decision: accept it. Do not add resolve-based containment.**

Three reasons:

1. **It grants no capability.** Planting the symlink requires write access to
   `workspace/series/` already. Anyone with that can write wherever their
   permissions allow, with or without agsoc.
2. **It is a legitimate operator action.** Renders run ~27 MB per episode.
   Symlinking `episodes/` or `out/` to another volume is exactly what a person
   with a small SSD does, and spec §5 does not forbid it.
3. **The contrast with D-038 is the whole point.** `--series ../../outside`
   escapes through an *argument*: you type a series name and get a path. That is
   surprising, and surprise is the harm. A symlink is the operator's own prior,
   explicit act on their own filesystem. Nothing is misrepresented.

Per D-040 this is not harm, so it does not block the gate. **What it needs is
disclosure, not prevention** — Phase 8 (render) should say plainly when output
lands outside the workspace, since that is where large files and real surprise
would meet. Recorded as a Phase 8 requirement.

A `series.toml` whose own `slug` key says `../../../far` does **not** escape:
`load_series` ignores the file's `slug` entirely. The implementer noted this
holds "only by accident and with no test saying so" — correct, and it goes on
the post-gate list.

## D-042 · phase 1 / task 5 · adjudication. Phase 1 implementation is COMPLETE
311 tests, 7/7 mutants killed — including the length-cap survivor from Task 4b,
which my own error message had been masking.

**One code deviation, correctly made and flagged.** The brief specified
`_assert_safe_name(slug, "series name", ...)`, which broke six pre-existing
assertions requiring the word `slug` — the new guard runs before `_validate_slug`
and now owns that message. Told not to weaken assertions, the implementer changed
the *code* to say `"series slug"`, matching the episode side's existing
`"episode id"`. Right call: the tests encoded a real contract and my brief did
not know it.

**It also reported a weakness in its own evidence:** the Step 1c CLI escape test
was green at RED, because the escape needs `<ws>/series/` to already exist and
`Workspace.init` never creates it. A correct end-state assertion, but not a
red-to-green witness — mutants 1 and 2 carry that proof instead. Reported rather
than left to look better than it was.

**Remaining asymmetries — 12, all post-gate (D-040):** two separate `64`
constants that will drift exactly as D-036 predicts; `--name` capped nowhere
while the slug is capped at 64; naming rules callable in `series.py` and inlined
in `episode.py` (the structural cause of D-038); symlink checks symmetric in the
creators but absent from both readers and enumerators; `scaffold_series`'s
`episodes/` mkdir sitting outside its cleanup `try` where `create_episode`'s sits
inside; and `video new ../../../pwned` autocreating the `default` series before
refusing the id.

None causes harm. All are recorded for Phase 2. **No Task 5b — the phase gate
runs next.**

## D-043 · roadmap · Phase 1.5 vertical slice — HUMAN DECISION 2026-08-16
Added a vertical slice between Phases 1 and 2: a hand-written three-beat
`script.yaml` rendered to a watchable ~10s MP4.

**Why, in the human's own framing:** they asked at what point they could validate
progress by testing it manually. Honest answer was "Phase 1 today, but nothing
visual until Phase 8." Phases 2–7 all build toward a render nobody has seen work
— a long time to carry an unvalidated assumption, and Phase 4 is already the
project's highest-uncertainty work (retrofitting a declarative layer onto a
working hand-written engine).

**Scope is a proof, not a product.** One beat type (`statement`), vertical only,
no ingest, no verification, no approve gate, three beats, ~10 seconds.

**The real deliverable is an architectural decision, not the video.**
`script.yaml` is two-document YAML and Node has no YAML parser without a new
dependency. Rather than add one, **Python parses and emits `plan.json`; Node
consumes it.** That holds the D-007 boundary exactly where it was argued to
belong — Python orchestrates, Node stays a pure renderer, the handoff is a file,
which is this project's existing idea of state. Phase 4 inherits that format, so
settling it against a real render now is most of the value.

**Non-negotiable:** `window.__seek(t)` purity. The determinism test ships green
in the same commit as any engine change, or the phase does not gate.

Cost: roughly one phase. Buys: the human sees output after Phase 1 instead of
Phase 8, and the riskiest integration in the project gets exercised while it is
still cheap to change.

## D-044 · PHASE GATE · verdict merge-after-fixes. 87 mutants, 4 blocking findings
The whole-branch review ran 87 mutants across four modules. **`series.py`: 34
mutants, 30 killed** — the D-024 debt is honoured by the code. Every
`_assert_safe_name` weakening, both limits, the symlink guard, `rmtree`,
`_table`, all format validation, and *every* `_toml_str` escaping branch died.
It found **no way to escape the workspace with any string an operator can type**.

Blocking findings, all leader-verified:

| # | Sev | Finding | Verdict |
|---|---|---|---|
| F1 | high | `--series` is the one operator input never passed through `_text()` — a traceback on non-UTF-8 | **fix-now** → Task 6. Fourth D-036 instance |
| F2 | high | **The approval gate can be walked past with a stale object** | **fix-now** → Task 6 |
| F3 | med | A `script.yaml` with no separator has operator beats reflowed into document 1 and replaced with a fabricated `beats: []` | **fix-now** → Task 6 |
| F4 | med | The tripwire for the 3d mutant does not fire | **fix-now** → Task 6 |
| F5 | med-low | Concurrent `video new`: the loser's cleanup deletes the winner's episode | **fix-now** → Task 6 (cheap, and it is data loss) |
| F6–F10 | low | `list_series` leniency unpinned, two vacuous location assertions, `is_file()`→`exists()` survives in both modules, untested error branches, cosmetic asymmetries | **Phase 2** — none is harm |

## D-045 · phase 1 · I MIS-ADJUDICATED THE APPROVAL GATE
Leader-verified:

```
on disk now      : draft
stale object says: approved
after set_status : rendering        *** GATE BYPASSED ***
```

`set_status` gates on `episode.status` (memory) and writes against the file it
reads two lines later.

**D-032 recorded a weaker form of this (F6: "stale Episode can regress
approved → in_review") and I sent it to Phase 7.** That was wrong twice over:

1. It understated the consequence. The bug is not a status regression, it is
   **reaching `RENDERING` from a file that says `draft`** — the single invariant
   spec §8.4 and §10 exist to guarantee.
2. It assigned the fix to a component that would *call* the broken function.
   Phase 7's approve gate would have been built on top of a `set_status` that
   does not actually gate.

The fix is three lines and `_read_meta` was already reading the file two lines
later. I deferred a free fix to the wrong phase because I filed it under
"freshness" rather than "the gate".

**Lesson: when a finding touches the product's central invariant, severity is not
inherited from how the reporter phrased it.** D-032 took the reviewer's framing
("stale object") and adjudicated that, instead of asking what the stale object
could reach.

## D-046 · phase 1 · D-035 reappeared inside the fix for D-035
`test_empty_metadata_document_keeps_its_beats` was added in Task 4 Step 0
specifically to pin the 3d mutant that survived. **Leader-verified: applying that
mutant leaves all 311 tests green.** Its substring-anywhere assertion is
satisfied by the corrupted output too.

So the test written to close D-035's third instance is itself a fourth instance.
That is not irony, it is evidence the failure mode is genuinely hard to see: I
wrote it *while thinking about this exact problem* and still reached for
`in raw` instead of `raw.endswith(...)`.

**Strengthened rule:** a test written to kill a specific mutant must be *run
against that mutant* before it is committed. Asserting the right property is not
enough; the assertion has to be tight enough to distinguish. Task 6's brief
requires its implementer to audit its own new tests by this standard.

## D-047 · phase 1 · reviewer's challenge to D-040 — ACCEPTED
The gate review argued my D-040 deferral list was right except in one place:
"document 1 comments and block scalars reflowed by `safe_dump`" is correctly
deferred *for metadata the tool writes itself*, but the same `safe_dump` reaches
**operator-written beats** whenever the separator is missing — and there it is
not cosmetic.

Correct, and I accept it. That case is F3, now fixed in Task 6 rather than
deferred. The deferral stands only for document 1, which is machine-written.

Worth noting the reviewer volunteered this: it was asked whether anything on the
deferred list was harm rather than confusion, and rather than answering "no" it
found the one seam where my own rule had been applied too broadly.

## D-048 · phase 1 / task 6 · gate closed. 319 tests, 5/5 mutants
Leader-verified:

```
on disk: draft | stale object: approved
REFUSED: cannot move draft -> rendering; allowed next: in_review
disk after: draft
```

**The implementer caught a vacuous test in my own brief and handled it exactly
right.** My briefed F5 test (`test_create_over_an_existing_dir_does_not_delete_it`)
is vacuous: the `d.exists()` precheck the brief insists on keeping raises before
control reaches the `mkdir` that F5 is actually about, so it passes with the fix,
without it, and with the mutant applied. Told the code block is authoritative, it
left mine byte-for-byte, **added** a test that monkeypatches `Path.exists` to
simulate what a concurrent winner actually does, and flagged the disagreement.
That added test is what kills mutant 5.

It also went further than asked: mutant 2 alone now dies at the *new* F3 refusal,
which would have left F4 unproven — so it applied mutants 2+3 together to strip
the refusal, and showed the **old** substring assertion still passing on the
corrupted bytes while the new one fails. That is the proof that D-046 is closed,
and I did not ask for it.

## D-049 · TEXT PIPELINE · fifth D-036 instance, in v1 code
`workspace.py:206` — `Workspace.set_status` for text variants has the identical
shape as the video gate bypass:

```python
    def set_status(self, v: Variant, target: Status) -> None:
        assert_transition(v.status, target)      # in-memory, not disk
```

Found by the Task 6 implementer while answering "is there any other route to
RENDERING", and flagged unprompted as out of scope. Correct on both counts.

**Not fixed in Phase 1**, deliberately: it is pre-existing v1 behaviour, not a
regression from this phase; the gate that protects posting to X sits in
`cli.py::post` *before* the keyring is touched; and `cli.py` loads variants fresh
on every invocation, so it is not reachable through the CLI today. Fixing it means
touching the text pipeline's tests, which Phase 1 committed not to do.

**Carried to Phase 2 as the first item.** The reason it matters is not today's
reachability — it is that the video gate had exactly this shape and I defended
it for two tasks before a reviewer broke it.

Fifth instance of "a guard in one of a matched pair and not the other", and the
first found in code this project did not write during these phases. The pattern
predates the phase; the phase just taught us to look.

## D-050 · phase 1.5 / task 2 · THE PIPELINE PRODUCED A VIDEO
Leader-verified end to end: hand-written `script.yaml` → `plan.json` → 300
Playwright frames → ffmpeg → `vertical-1080x1920.mp4`, `duration=10.000000`,
1080×1920, `nb_frames=300`. Sent to the human.

Resolved timing came out exactly as designed — contiguous, Python-owned:

```
  0.0–3.5 s   f  0–105
  3.5–6.5 s   f105–195
  6.5–10.0s   f195–300
```

**The architectural bet paid off.** `render.mjs` performed no timing arithmetic;
it looked up pre-resolved values. That is the property that makes `__seek(t)`
policeable, and it is the format Phase 4 inherits. Deciding it against a real
render — rather than in the abstract at Phase 4 — was the entire point of this
phase.

## D-051 · phase 1.5 / task 2 · the determinism test was committed RED, correctly
The implementer found `day path t=3.7` failing on the **existing** `?day=` path
and committed it red rather than narrowing the sampled times to hide it. That is
the right instinct and the opposite of what a green-dashboard reflex produces.

It then separated two defects that present as one red line:

**A · a genuine `__seek(t)` impurity.** With no `act`/`src` on a scene, the
previous scene's text and transform stay in the DOM, hidden only by `opacity: 0`.
Byte-identical pixels today; a visible wrong-label bug the moment that chip fades
instead of snapping. `CLAUDE.md` calls this invariant load-bearing.

**B · Chromium rasterises `filter: blur()` differently** on a reused `.sc` layer
versus a fresh one. Max delta 9/255 over ~1.4% of pixels, confined to blurred
`<h1>` glyphs in exit tails. **This is what makes the test red.**

**It proved the test is not theatre**, unprompted by results: baseline 1/3 fail →
`Math.random()` injected → 3/3 fail → `Date.now()` injected → 3/3 fail → reverted
clean. After four tests in this project that could not fail, a determinism test
that cannot detect non-determinism would have been the fifth.

**Human decision:** determinism over render speed. Task 2b works a cheap→expensive
ladder (layer-promotion hints first) with per-frame rebuild as the authorised
fallback, because the cause is a compositing inconsistency rather than something
that inherently needs 3,600 rebuilds.

**A is being fixed on its own terms, with a page-state check added to the test.**
A pixel-only determinism test is structurally blind to A — the same lesson as
D-035 in a new costume: the harness could observe one dimension and the bug lived
in the other.

## D-052 · phase 1.5 / task 3 · spec deviation — `preview`, not `render`
Spec §11 names this command `agsoc video render`. **Phase 1.5 ships
`agsoc video preview` instead.**

`render` is gated: spec §10 makes `RENDERING` reachable only from `APPROVED`, and
Phase 1 built that gate. Phase 1.5 has no `approve` command — that is Phase 7 —
so a `render` today would either be blocked for every episode or bypass the gate
it is named after.

**Shipping a gate-bypassing command under the name the gated one will later take
is how a gate quietly stops meaning anything.** `preview` never touches status
and says so in its help text. Phase 8 adds `render` on top of the same
implementation.

Two tests pin the distinction: `preview` leaves status at `draft`, and never
rewrites `script.yaml`.

## D-053 · phase 1.5 · tenth brief defect, and it was a vacuous test again
`test_resolved_times_are_rounded_not_raw_floats`, which I wrote in Task 2's brief
*specifically* to kill a mutant the previous implementer found surviving, does
not kill it. At the `pace=1.1` I chose, `hold` is rounded before accumulation, so
every running sum is exactly representable — there is no float noise to catch.

The implementer kept my code block verbatim, flagged it, and added a sibling at
`pace=1.15` where `4.025 + 3.45 = 7.4750000000000005` actually kills the mutant.

Sixth instance of the D-035 family, and the second time I have written a vacuous
test *while explicitly thinking about vacuous tests*. The rule from D-046 —
run the test against the mutant before committing it — is one I keep prescribing
to implementers and failing to apply to my own briefs. **From here, any test I
write in a brief that names a specific mutant must come with the pace/values that
demonstrably produce the condition, or say plainly that I have not verified it.**

## D-054 · phase 1.5 / task 2b · determinism green, and my premise was false
Fixed at rung 3 of the ladder: `stageScenes.appendChild(SC)` on every seek —
re-inserting the existing node discards its paint layer without rebuilding the
DOM or re-running the word-rise walk. Leader-verified: `deterministic`, exit 0,
pixel and page-state checks green on both paths.

**The trade-off I put to the human did not exist.** I framed "25 rebuilds vs
3,600" as a performance decision. Measured: rebuild-every-frame costs **0.6%**,
because rendering is dominated by `page.screenshot()` at ~230 ms/frame. The real
objection to that option was architectural — `if(true)` deletes the caching
mechanism and strands a dead `CUR` — and I presented it as speed. The chosen fix
is free within noise (229.86 vs 229.94 ms/frame).

Same error class as my vacuous tests, one level up: **I passed along a number
without checking it, and asked for a decision on it.**

The diagnostic that found the fix: arriving at `t=3.7` from any predecessor gives
the same frame *unless a screenshot was taken in between*. The trigger is raster
cache reuse — one level below anything a CSS declaration reaches, which is why
all three of my suggested hints failed. It tried each and reported each failure
rather than jumping to the authorised fallback.

**Also fixed: a real `__seek(t)` impurity** (act chip and source tag were hidden,
not cleared) — invisible in pixels, which is why the test now carries a
page-state check. My page-state snippet in the brief was itself vacuous: both
arms arrived from scenes that also had no act, so both inherited the same stale
label and it printed "stable" with the bug present.

## D-055 · phase 1.5 · playwright pinned; reproducibility was per-machine
`engine/package.json` declared `"playwright": "^1.62.1"`. Chromium's blur
rasterisation is version-dependent, so under a caret range **two operators could
render different MP4s from one `script.yaml`** — and the determinism test cannot
see it, because it compares two hashes within one session and both move together
on upgrade. `CLAUDE.md` calls reproducibility load-bearing; a caret range quietly
made it a property of the machine. Pinned exactly, with the reasoning in
`engine/README.md`.

## D-056 · phase 1.5 / task 3 · the engine is not in the wheel
Asked whether `ENGINE_DIR = parents[3]` breaks under pip install. The implementer
built an actual wheel rather than reasoning about it: **`engine/` is not packaged
at all.** `pyproject.toml` ships only `src/agenticsocial`. In a clean venv the
path resolves to a directory that has never existed, and the installed CLI
reports `could not start the renderer: [Errno 2]`.

So no `parents[N]` is correct — fixing the arithmetic points at something that
was never shipped. **Required before Phase 8**, in three parts: ship the engine
inside the package; anchor it with `importlib.resources.files("agenticsocial")`
rather than a parent count (a parent count encodes repo depth in an unrelated
module and breaks silently); and add `$AGSOC_ENGINE` plus a fail-fast check in
`_require_tools`, so it fails up front with an actionable message.

Not fixed in Phase 1.5: it moves a tracked Node subproject and edits packaging.

## D-057 · phase 1.5 · a test hazard the mutation audit exposed
`test_missing_node_is_a_clean_error` and `test_missing_ffmpeg_is_a_clean_error`
patch `shutil.which` but not `subprocess.run`. They pass only because
`_require_tools` raises first. **Remove that check and those two tests launch
real Chromium and real ffmpeg** — violating the offline-suite rule and turning a
1-second suite into a minutes-long one.

Found by an implementer's own mutation audit, not by anything failing. Recorded
as a Phase 2 cleanup: give both tests the `fake` fixture so they cannot reach a
real subprocess whatever the code does.

## D-058 · phase 1.5 · brief defect count: 14, implementer errors: 0
Across Phases 1 and 1.5, every implementation has been a faithful transcription
of its brief, and every defect has been mine, written upstream. Task 3 alone
found three: a `--probe` path whose implementation could not have passed my own
test, an `ffprobe` command that printed nothing and **read exactly like the
feature failing**, and a misplaced import.

The `ffprobe` one is the instructive one — a verification command that fails
*closed* teaches the operator their working feature is broken. I have now written
two of those (this, and the zsh word-splitting probe that reported four working
commands as MISSING).

**The leverage in this process is reviewing briefs, not reviewing code.**

## D-059 · PHASE 2 · a draft could be published. Fixed. v1 shipped with this.
Leader-verified before the fix:

```
status on disk : draft
tweets posted  : 2 ['tweet one', 'tweet two']
status after   : published
*** A DRAFT WAS PUBLISHED ***
```

The README's central promise — "Nothing goes live without you running
`agsoc approve`" — was breakable. **This is the most serious defect the project
has found, and it shipped in v1.**

**The bypass laundered itself**, in three individually-defensible steps:

1. `publish_variant` decided *whether to run the gate* from the in-memory object,
   so a stale `Variant` claiming `PUBLISHING` skipped it entirely.
2. The posting loop's `save_variant` stamped `status: publishing` onto the draft.
3. The closing `set_status(PUBLISHED)` then passed **legitimately** — disk really
   did say `publishing` by then.

The final file state is indistinguishable from a properly approved publish. No
trace.

**Root cause, named by the Task 0 implementer:** `save_variant` was an *ungated
status writer*. The video pipeline has exactly one writer of episode status and
it is gated; the text pipeline had two, one of which wrote whatever the object
claimed. That asymmetry was the bug — and my Task 0 fix hardened one writer while
the other quietly undid it.

Fixed: `set_status` is now the only writer of the status key; `save_variant`
preserves what is on disk; both gate-skip decisions read the file. Verified by
hand — refused before the first network call, zero tweets, status untouched.
Both pipelines now have exactly one gated status writer each.

## D-060 · phase 2 / task 0b · an existing test was using the defect as an API
`test_post_stuck_publishing_requires_resume` forged its state with
`v.status = PUBLISHING; ws.save_variant(v)` — precisely the ungated writer this
task removed — so it broke.

The implementer **did not edit it**. It analysed it, verified the asserted
behaviour is intact when the state is reached legitimately by driving the real
CLI, and corroborated the causal link by showing the test passes again under the
mutant that restores the ungated writer. That is what "a failing test is a
finding" is supposed to produce.

Leader applied the two-line setup fix (`ws.set_status(v, Status.PUBLISHING)`, a
legal approved→publishing move) rather than dispatching an agent for it, since
the diagnosis was complete and a red suite blocks everything. Verified the test
still earns its place: disabling the CLI's interrupted branch still fails it.

**Worth recording as a category.** When a defect is removed, tests that *used*
that defect to set up their fixtures break — and they break in a way that looks
like the fix is wrong. The tell is that the test's *setup* touches the thing that
was fixed, while its assertion is unrelated.

## D-061 · OPEN DESIGN QUESTION · should `Variant.status` be mutable at all?
The Task 0b implementer argued it should not, and the argument is strong enough
to record verbatim in substance:

> Three bypasses, one identical root cause — that's not three mistakes, it's a
> design where the mistake is the natural thing to write. `v.status` and
> `ws.disk_status(v)` look interchangeable at the call site; nothing in either
> name says which one is a guess, and the security-relevant distinction is
> invisible in the code. Worse, writability means it isn't a stale cache — it's a
> **forgeable claim**, and until this commit `save_variant` persisted the forgery.

Its conclusion: `disk_status` is the right mechanism and the **wrong stopping
point** — it removes the third instance without removing the ability to write a
fourth. The proposal is a frozen `Variant` (or a property with no setter) with
`set_status` returning a fresh object, making all three bypasses *unrepresentable*
rather than merely fixed — the same property the engine gets from `__seek(t)`
being pure in `t`.

`Episode.status` in the video pipeline has the identical shape, so a full fix
spans both pipelines.

**Raised with the human; not yet decided.** Also open, flagged by the same
report: `set_status(FAILED)` inside `publish_variant`'s error handler can itself
raise while reading the file, **masking the original exception** and leaving
`posted_ids` one tweet behind reality. Pre-existing, fails in the safe direction
(a duplicate on resume, never a lost tweet), and worth its own task.

Also noted: mutant 3 (`cli.py` deciding from `v.status`) **survives** — equivalent
under today's CLI, where `_load` always returns a fresh variant. Kept as defence
in depth, recorded as unkilled rather than papered over.

## D-062 · phase 2 · "unrepresentable" RETRACTED. Freezing is a correctness fix, not a security one.
I told the human that freezing `Variant`/`Episode` would make a forged status
*unrepresentable*. **That was wrong, and I verified it myself:**

```
frozen=True deleted from Variant  ->  379 passed        (nothing enforced it)
replace(v, status=PUBLISHING)     ->  forged: publishing | disk says: draft
```

The Task 0c implementer said so before I checked, unprompted, rather than letting
my framing stand: *"freezing did not make a forged Variant unconstructible, it
made it unconstructible by accident — `replace` is now the forgery tool, one
line."*

**The accurate position**, argued by the Task 0d implementer when asked to
disagree with me rather than agree:

- Freezing stops **accidental** forging. `v.status = APPROVED` is one invisible
  token and is the exact shape of all three historical bypasses — every one an
  accident of convenience. `replace(v, status=...)` names the module and the
  field and is greppable. It raises the intent floor; it is not a boundary.
- **The load-bearing defence is that no gate reads the object.** A forged status
  buys nothing regardless of how it was forged. If only one mechanism could be
  kept, keep the disk read.
- **Add no further mechanism.** A custom `__setattr__` is defeated by
  `object.__setattr__` one line later; a disk-reading property costs I/O per
  access and trades a hypothetical bypass for real staleness bugs. Python has no
  in-process boundary and pretending otherwise is a category error.

**Freezing stays, on the correctness argument rather than the security one:** a
snapshot that mutates lies about its file. That applies to `body` and
`target_sec` as much as to `status`, and it survives the concession.

Task 0d made the guarantee actually enforced — five mutants, five kills, 383
tests. Before it, deleting the decorator passed everything.

## D-063 · FORWARD WARNING · where the fourth instance will come from
The Task 0d implementer's most useful output was not about this task:

> The next bypass probably won't be a forged field. It'll be a Phase 3 gate that
> reads `episode.status` or a stale `series.target_sec` instead of re-reading
> disk — and `frozen=True` is completely inert against that.

Correct, and it reframes the whole family. All three bypasses were *writes* to a
trusted object; the next is likelier to be a *read* of a stale one. Freezing
prevents the former and does nothing about the latter.

**Standing requirement: every new gate gets a stale-object test.** Phase 3's
duration gate (`abs(dur - target_sec) > tolerance_sec`) is the first one due, and
it must have a test that loads an object, changes the file underneath it, and
asserts the gate follows the file. Rated by its author above anything else in
that report, and I agree.

`Source` stays mutable — no gate reads it, and grep confirms nothing assigns to
it. Recommended to freeze opportunistically during ingest, since Phase 2 is the
phase most likely to start passing `Source` around and `Source.dir` is a `Path`
consumed by filesystem operations.

## D-064 · PROCESS · why my briefs keep producing tests that cannot fail
Vacuous tests have now appeared in **four separate phases**, always in briefs I
wrote. Seventeen brief defects against zero implementer errors. Asked to diagnose
my process rather than the code, the Task 1c implementer gave the answer:

> An example is a point, a rule is a function, and any finite set of points
> admits infinitely many functions. But the half that is yours, and is fixable:
> **your briefs write the assertion after you already know the implementation.**
> `assert key_for(...) == "reuters-com"` is a value read off code you had just
> designed — a transcription, and transcriptions cannot disagree with what they
> transcribed.

**"Passed on arrival" is the transcription rate.** 10 of 11 in Task 1c, 4 of 4 in
Task 1b. I had been reporting that number for three phases without understanding
it was the diagnosis.

### The four changes, adopted

1. **State the rule as a sentence with a negative half, before writing any
   assertion.** "A leading `www-` is stripped; `www` elsewhere is not." Every pin
   that killed a mutant had a negative half; every one that killed nothing had
   none.
2. **Specify the mutant first, derive the assertion from it.** I already write
   good mutants — in Step 3, *after* the tests, independently. That ordering is
   the bug. `match="unsafe"` is derivable from "the mutant drops the guard"; it
   is not something anyone adds while writing a happy-path assertion. This alone
   would have caught both vacuous tests at authoring time.
3. **Give each test a one-line `precondition:` naming what the fixture must NOT
   already be in.** Both vacuous tests failed for exactly this and nothing else.
   Highest yield per character.
4. **Use properties where the rule is infinite and the value is cited
   elsewhere** — keys, collision suffixes, anything a claim hard-codes.

### The line worth keeping

> An example should be chosen because it **discriminates**, not because it
> **illustrates**. `blog.google` is what a reader needs; `blog.wwwfoo.com` is
> what the mutant fears. Your briefs have been picking from the reader's set.

This is the most valuable process finding of the project, and it came from asking
an implementer to critique my briefs rather than the code.

## D-065 · phase 2 / task 1c · corpus.py is closed
430 tests. Nine mutants, nine kills. The 14-mutant sweep went 12 survivors → 5,
and **all seven previously called real are dead**; every survivor is cosmetic
(`sort_keys`/`indent`/`ensure_ascii` round-trip identical, a redundant `sorted()`,
and one genuinely unreachable recheck).

Task 1b's surviving mutant — deleting `verify`'s empty-dir guard — is also now
killed.

Chain capped at 1c per D-023. Anything further in this module goes to Phase 3.

**Carried to Task 2, unchanged in importance:** the `-2` collision key is
fetch-order-dependent, so a corpus rebuild can silently re-point `blog-google-2`
at the *other* article. That is the one failure mode in this module that yields a
**wrong fact-check rather than a loud one**, and the fix belongs in ingestion —
look the URL up in the manifest, reuse its key or refuse, never re-derive.

## D-066 · PHASE 2 GATE · merge-after-fixes → fixed. The gate itself held.
Thirteen forgery attacks, every one refused: `replace()` to APPROVED and to
PUBLISHING, a mutated `meta` laundered through `save_variant`, stale objects over
reverted files, the video equivalents, and the real CLI in a subprocess. The four
bypasses closed in this phase stay closed under attack.

**F1 — the verifier trusted its own manifest.** Leader-reproduced: a manifest key
of `../../../../../../outside` made `verify()` report a corpus **SOUND** while
`sources/` held no documents at all, having hashed a file outside the workspace
to say so. `document_text` refused the identical key. Fixed; now
`[('unsafe', ...)]`.

*My first probe of F1 used the wrong traversal depth and came back clean.* I
nearly filed it as not-reproducing — the same error as D-031, dismissing a real
finding on a bad probe of my own. Re-ran with the depth computed rather than
guessed and it reproduced immediately. **A failed probe is not a refutation.**

Also fixed: hostless hrefs recorded rather than aborting the run (F2); symlinked
documents flagged (F4); `document_text` returns the bytes its hash covers, not
newline-translated text (F5, the same defect `c47236b` fixed for beats); a
*missing* `sha256` no longer compares equal to itself (F8); padded bytes are a
modification (F9); `disk_status`'s fallback is pinned to DRAFT — flipping it to
APPROVED had passed all 469 tests (F10); and **publishing can no longer grant
itself** (F11).

Deferred with reasons: F18 (post-approval body swap) belongs to Phase 7, which
owns the approve gate and whose contract it changes. Hardlinked documents still
verify sound — weaker than the symlink case, since edits through the other name
still change the hash, and `st_nlink > 1` would flag innocent files.

## D-067 · you cannot guard a boundary you do not own
Task 4 added an autouse socket guard. It half worked. Leader-verified:

```
urllib : blocked (RuntimeError)
ddgs   : *** REACHED NETWORK *** 2 results
```

`ddgs` fetches through **`primp`, a Rust HTTP client that opens sockets in native
code and never touches Python's `socket` module.** The guard is invisible to it.
`trafilatura` uses urllib3 — pure Python — so extraction was guarded and search
was not. Two mutants ran **90 seconds to timeout** against duckduckgo rather than
failing.

**The fix is to guard the seam we own.** `research.search` and `research.extract`
are this project's only two fetch calls; a guard there cannot be bypassed by a
dependency's choice of HTTP stack. Measured after: those two mutants now fail in
**0.80s and 1.26s** — ~70× faster and deterministic rather than DNS-dependent.
Full suite 482 passed in ~2s, no test broken, all eight respx tests unaffected
(respx patches the httpx transport, so a mocked request never descends to
`create_connection`).

The socket patches stay: `x/client.py` and `x/auth.py` use httpx, which is pure
Python all the way down, and they were measured blocked in 0.06s.

**The honest remaining hole**, reported rather than hidden: `video/render.py`'s
`subprocess.run` of node. A child process inherits no monkeypatch. Every render
test patches `R.subprocess.run`, but that is *convention* — exactly where
`research` was before this task. Phase 8's gated `render` should guard
`render._run` by the same logic.

**Generalisable:** an isolation guarantee must sit on a boundary you control. A
guard on someone else's abstraction holds only until they change how they reach
the network — and it fails silently, which is the worst way to learn.
