# Task 3 Report: Episode scaffolding

**Branch:** `feat/video-phase-01-scaffolding` · **Commits:** 2 (RED, GREEN), not squashed

## 1. What I implemented

`src/agenticsocial/video/episode.py`, exactly as the brief's Step 4 code block
specifies — no deviations. It provides `SUBDIRS`, `create_episode`,
`load_episode`, `resolve_episode`, `episode_ids`, `list_episodes`, `set_status`,
plus the two private helpers `_dump` / `_read`.

`Series`, `Episode` and `EpisodeError` were taken from
`src/agenticsocial/video/models.py` (Task 2) and not redefined. `Status`,
`TransitionError`, `VIDEO_TRANSITIONS` and `assert_transition` come from
`src/agenticsocial/models.py`; `atomic_write` from
`src/agenticsocial/workspace.py`. No new dependencies. No existing test touched.

## 2. TDD evidence

### RED

From the test-only commit `98a6c7a`, before `episode.py` existed:

```
$ uv run pytest tests/test_video_episode.py 2>&1 | tail -15
==================================== ERRORS ====================================
_________________ ERROR collecting tests/test_video_episode.py _________________
ImportError while importing test module '/Users/aabdukarim/Documents/Code/agenticsocial/tests/test_video_episode.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/Volumes/.../lib/python3.11/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_video_episode.py:5: in <module>
    from agenticsocial.video.episode import (
E   ModuleNotFoundError: No module named 'agenticsocial.video.episode'
=========================== short test summary info ============================
ERROR tests/test_video_episode.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.06s ===============================
```

Collection error with the exact `ModuleNotFoundError` the brief predicted.

### GREEN

```
$ uv run pytest tests/test_video_episode.py -v 2>&1 | tail -30
collecting ... collected 26 items

tests/test_video_episode.py::test_create_makes_the_full_layout PASSED    [  3%]
tests/test_video_episode.py::test_created_script_is_two_yaml_documents PASSED [  7%]
tests/test_video_episode.py::test_create_is_not_destructive PASSED       [ 11%]
tests/test_video_episode.py::test_load_returns_status_from_disk PASSED   [ 15%]
tests/test_video_episode.py::test_load_missing_episode_is_actionable PASSED [ 19%]
tests/test_video_episode.py::test_invalid_status_names_the_file_and_valid_values PASSED [ 23%]
tests/test_video_episode.py::test_load_tolerates_a_single_document_script PASSED [ 26%]
tests/test_video_episode.py::test_load_tolerates_an_empty_script PASSED  [ 30%]
tests/test_video_episode.py::test_resolve_exact_id_wins PASSED           [ 34%]
tests/test_video_episode.py::test_resolve_by_unique_substring PASSED     [ 38%]
tests/test_video_episode.py::test_resolve_ambiguous_lists_candidates PASSED [ 42%]
tests/test_video_episode.py::test_resolve_no_match_is_actionable PASSED  [ 46%]
tests/test_video_episode.py::test_resolve_a_healthy_episode_despite_a_corrupt_neighbour PASSED [ 50%]
tests/test_video_episode.py::test_resolving_the_corrupt_episode_itself_still_raises PASSED [ 53%]
tests/test_video_episode.py::test_list_episodes_is_sorted PASSED         [ 57%]
tests/test_video_episode.py::test_list_episodes_when_none PASSED         [ 61%]
tests/test_video_episode.py::test_list_episodes_skips_dirs_without_a_script PASSED [ 65%]
tests/test_video_episode.py::test_episode_ids_survives_a_corrupt_episode PASSED [ 69%]
tests/test_video_episode.py::test_list_episodes_is_strict_about_a_corrupt_episode PASSED [ 73%]
tests/test_video_episode.py::test_episode_ids_on_empty_series PASSED     [ 76%]
tests/test_video_episode.py::test_set_status_persists_and_preserves_beats PASSED [ 80%]
tests/test_video_episode.py::test_set_status_updates_the_in_memory_episode PASSED [ 84%]
tests/test_video_episode.py::test_set_status_does_not_lose_beats_written_by_a_later_phase PASSED [ 88%]
tests/test_video_episode.py::test_set_status_enforces_the_video_table PASSED [ 92%]
tests/test_video_episode.py::test_set_status_allows_the_approved_render_path PASSED [ 96%]
tests/test_video_episode.py::test_a_rejected_transition_does_not_touch_the_file PASSED [100%]

============================== 26 passed in 0.17s ==============================
```

```
$ uv run pytest 2>&1 | tail -5
tests/test_video_status.py ....................                          [ 90%]
tests/test_workspace.py .................                                [ 98%]
tests/test_x_client.py ....                                              [100%]

============================= 210 passed in 0.64s ==============================
```

### Counts observed vs. predicted

| | Brief predicted | Observed |
|---|---|---|
| New file | 27 passed | **26 passed** |
| Task 2 baseline | 130 | **184** (`uv run pytest --ignore=tests/test_video_episode.py`) |
| Full suite | 157 | **210 passed** |

The brief's Step 1 code block contains 26 `def test_` functions — I transcribed
it verbatim and counted with `grep -c "^def test_"`. The "27" and the "130"
baseline are both brief arithmetic errors. I did not add a test to reach 27 or
adjust anything to reach a predicted total. 184 + 26 = 210 is internally
consistent.

## 3. Files changed

| File | Commit |
|---|---|
| `tests/test_video_episode.py` (new, 219 lines) | `98a6c7a444a572593808b4bf9896a81e5c279f96` |
| `src/agenticsocial/video/episode.py` (new, 115 lines) | `512655ed3aa707229433142ba4e833064ba9c9f0` |

- RED: `98a6c7a` — `test: specify episode scaffolding and video status persistence`
- GREEN: `512655e` — `feat: add episode scaffolding and video status persistence`

Nothing under `docs/` staged. `PROGRESS.md` and `DECISIONS.md` untouched. No
dependency changes. Working tree otherwise clean.

## 4. Self-review findings

No prose/code-block contradiction that changes behaviour. Two prose–code
mismatches, both cosmetic:

1. The module docstring and the brief's Context both describe document 1 as
   "(episode id, series, status, pace)", but `create_episode` also writes
   `date_long: ""`. Harmless; noting it because the docstring will be read as a
   schema by Phase 3.
2. The brief's Context says the `---` fences "are not the frontmatter used
   elsewhere in this codebase". At the byte level that is false — see Q2 below.

Findings from adversarial probing (each reproduced, not theorised). Ordered by
severity. **None of these are fixed** — the brief's code block is authoritative
and none are pinned by the 26 tests.

### F1 — `load_episode` leaks a raw `yaml.ScannerError`, defeating D-018 (high)

`_read` calls `yaml.safe_load_all(...)` with no `try`. On a script that is not
valid YAML at all — a tab-indented line, an unclosed bracket — the raise is
`yaml.scanner.ScannerError`, **not** `EpisodeError`:

```
=== A: genuinely malformed YAML (tab indent) ===
yaml.scanner.ScannerError: while scanning for the next token
```

This matters specifically because of D-018. Task 4's CLI is specified to iterate
`episode_ids` and load each inside a try/except; every other error path in
`cli.py` catches a named domain error (`except WorkspaceError`,
`except SeriesError`, `except TransitionError`). A `try/except EpisodeError`
around the per-episode load will **not** catch this, so `agsoc video list`
tracebacks on precisely the corrupt file that D-018 exists to survive. The
`status: banana` fixture used throughout the tests is *valid YAML*, so the suite
never exercises this path.

Compare `load_series`, which is careful here — it wraps both
`tomllib.TOMLDecodeError` and `OSError` into `SeriesError`. `load_episode` wraps
neither. It also lacks `OSError` handling (unreadable file, permissions).

Fix is one `try` in `_read`. I would take it in Task 4 at the latest, before the
CLI is written against a contract it cannot honour.

### F2 — `set_status` silently deletes beats that are a bare list (high)

Directly relevant to Q3. `_read` requires document 2 to be a `dict`. If Phase 3
writes the beats document as a top-level *sequence* — a completely natural YAML
shape for a list of beats — the `isinstance(docs[1], dict)` guard fails, the
substitute `{"beats": []}` is used, and `set_status` writes the substitute back:

```
=== B: doc 2 is a LIST of beats, not a mapping ===
input : ---\nepisode: '2026-08-14'\nstatus: draft\n---\n- type: statement\n  text: hello\n
output: "---\nepisode: '2026-08-14'\nstatus: in_review\n---\nbeats: []\n"
```

The beats are gone, silently, on a status change. `test_set_status_does_not_lose_
beats_written_by_a_later_phase` passes because it happens to use the mapping
shape. This is the single most likely way Phase 3 loses data.

### F3 — a third document is silently dropped (medium)

```
=== C: THREE documents ===
input : ---\nstatus: draft\n---\nbeats: []\n---\nextra: keepme\n
after set_status: [{'status': 'in_review'}, {'beats': []}]
```

`_read` returns a 2-tuple and `_dump` emits exactly two documents, so anything
past index 1 is discarded on the next write. If Phase 3 or a later phase adds a
third document (captions, render manifest), `set_status` eats it. Same class as
F2: the read/write pair is lossy for anything it does not model.

### F4 — a partially created episode is invisible and permanently un-creatable (medium)

`create_episode` makes the subdirectories first and `atomic_write`s
`script.yaml` second, with no cleanup on failure. If it dies in between (disk
full, interrupt), the result is a directory that:

```
=== G: partial create ===
episode_ids sees: []
create_episode says: episode already exists: the-brief/2026-08-14
load_episode says: no episode '2026-08-14' in the-brief — create it with `agsoc video new 2026-08-14`
```

Invisible to `video list`, un-creatable, and the two error messages contradict
each other — one says it exists, the other tells you to create it. The operator
is stuck without `rm -rf`.

Its sibling `scaffold_series` handles exactly this case, deliberately, with a
`try/except BaseException: shutil.rmtree(d, ignore_errors=True)` and the comment
"Leave nothing half-written: the operator's obvious next move is to retry, and a
partial directory would fail with 'already exists'." That reasoning applies
verbatim to `create_episode`, which does not do it. I read this as an oversight
in the brief rather than a decision — the two functions should match.

### F5 — `set_status` on a sparse script strips identity fields (low)

Loading a script whose metadata is empty or partial and then changing status
writes back only what was there plus `status`:

```
=== E: empty script -> set_status ===
'---\nstatus: in_review\n---\nbeats: []\n'
```

`episode` and `series` are not repopulated from the known `Episode.id` /
`series.slug`. Tolerated on read (two tests pin that), but the write path then
persists the degraded form. `set_status` has both values available and could
heal the file instead.

### F6 — no cross-check between `meta["episode"]` and the directory name (low)

```
=== H: drift ===
id: 2026-08-14 | meta.episode: 1999-01-01 | series_slug: the-brief | meta.series: other
```

`Episode.id` and `series_slug` come from the path; `meta` comes from the file;
nothing reconciles them. A copied episode directory silently carries the source
episode's identity in its metadata, and whichever of the two Phase 3 reads
decides what happens. Worth a validation error, or at minimum a documented rule
that the path always wins.

### F7 — comments do not survive a status change (low)

```
=== D ===
input : ---\nstatus: draft   # set by hand\n---\n# the beats\nbeats: []\n
output: '---\nstatus: in_review\n---\nbeats: []\n'
```

Inherent to `safe_load` + `safe_dump` round-tripping, and shared with the
existing frontmatter helper, so it is consistent with the codebase. But
`script.yaml` is explicitly a human-edited file (three tests describe hand
edits), and `series.toml` — the other human-edited file — is generated from a
*text template* precisely so its explanatory comments survive. `script.yaml`
gets the opposite treatment. Worth a deliberate decision rather than a default.

### F8 — `episode_ids` uses `.exists()` where `series_slugs` uses `.is_file()` (nit)

`(d / "script.yaml").exists()` is true for a *directory* named `script.yaml`;
`load_episode`'s existence check has the same issue and would then fail with an
`IsADirectoryError` (an `OSError`, so also unwrapped — see F1). `series_slugs`
gets this right with `.is_file()`. The two enumerators are otherwise deliberate
mirrors of each other, so the divergence looks accidental.

## 5. Issues and concerns

### Q1 — Does the D-018 split hold up, or does it move the problem into Task 4?

**The split is right, and it does not move the problem — but the implementation
does not currently deliver it, because of F1.**

The principle is sound and I would keep it. The asymmetry is real, not
bureaucratic: `load_episode("2026-08-14")` is an addressed operation with no
partial answer available, while `agsoc video list` is a diagnostic whose entire
value is being usable when things are broken. A tool that refuses to describe
nine healthy episodes because the tenth is corrupt is worse than useless — it is
useless at exactly the moment it is needed. `resolve_episode` matching over ids
rather than over loaded episodes is the same principle applied correctly, and
`test_resolve_a_healthy_episode_despite_a_corrupt_neighbour` pins it well.

It is not "moving the problem into Task 4" because what lands in Task 4 is
*presentation policy*, and that genuinely belongs there. `episode.py` cannot know
whether a broken episode should be a red row, a skipped row, or a footnote — it
depends on the output format and on whether `--json` was passed. Keeping that out
of the domain module is correct layering, not buck-passing.

The one thing that *is* passed to Task 4 unfairly is F1: `episode.py` implicitly
promises that per-episode failures are `EpisodeError`, and does not keep that
promise. Task 4 will write `except EpisodeError` — the obvious code, matching
every other handler in `cli.py` — and it will be wrong. The fix belongs in
`_read`, not in the CLI. **I would fix F1 before Task 4 is written**, and I would
add a `agsoc video list` test with a genuinely unparseable script, not just a
valid-YAML-invalid-status one. Right now the suite gives false confidence on the
exact scenario D-018 was written for.

**Is `list_episodes` dead weight? Nearly, and I would watch it.** By construction
its only distinguishing behaviour is "raise instead of returning partial
results", and the argument for D-018 is precisely that no user-facing surface
wants that. Today it has no non-test caller. The plausible genuine callers are
batch operations where a partial view would be actively dangerous — "render every
approved episode", "check coverage across the whole series" — where silently
skipping a corrupt episode could mean silently not rendering it, or reporting a
coverage gap that is really a parse error. That is a real category and it
justifies keeping the function. But three of the 26 tests exist only to pin it,
and it is one line. If Phase 2 or 3 arrives with no caller, I would delete it and
let the batch operations build the comprehension inline, rather than keep a
tested-but-unused API implying a contract nobody needs. Flagging it now so the
decision gets made deliberately.

### Q2 — Two-document YAML vs. a single document with a top-level `beats` key

**I would change it now. The stated rationale does not survive contact, and the
one benefit that is real is not being collected.**

Three reasons, in order of how much they moved me.

**1. The rationale is a non-sequitur.** The brief argues: `beats` is structured
data, not a markdown body, so it should be parsed by the YAML parser rather than
by `frontmatter.parse`. That argument is entirely correct and it establishes
*YAML rather than markdown-with-frontmatter*. It says nothing whatsoever about
*two documents*. A single YAML document with `beats:` at the top level is just as
fully parsed by the YAML parser. The reasoning justifies a conclusion adjacent to
the one it is used for.

**2. "They are not frontmatter" is false at the byte level, which is the worst
case.** The claim is that the `---` fences are document separators rather than
the codebase's frontmatter convention. But `_dump(meta, beats_doc)` produces
output byte-identical in shape to `frontmatter.dump(meta, body)` — compare them,
they are the same f-string. And this repo's own `frontmatter.parse` reads a
`script.yaml` *successfully*:

```
=== I: agenticsocial.frontmatter.parse on a two-doc script.yaml ===
meta: {'episode': '2026-08-14', 'status': 'draft'}
body: 'beats:\n- type: statement\n'
```

It does not fail. It returns correct-looking metadata and hands back the beats as
an **unparsed string**. A Phase 3 contributor who reaches for the in-house helper
— which is the natural thing to do in this codebase, `workspace.py` uses it in
five places — gets a plausible, silently wrong result rather than an error. A
format that is indistinguishable from a different format with different semantics
is not a neutral choice; it is a trap, and it is a trap that this codebase is
specifically primed to fall into. The same applies outside Python: `yq '.beats'`
and `yaml.safe_load` both operate on one document by default and will quietly see
only the metadata.

**3. Document identity is positional and unvalidated.** `_read` takes `docs[0]`
and `docs[1]` by index with no check on what they contain beyond `isinstance`
dict. There is no way to tell a metadata document from a beats document except by
guessing at keys, and F2/F3 are both direct consequences of that positional
modelling. A single document with named top-level keys is self-describing: adding
a third section is adding a key, not appending a positional document that the
existing writer then deletes.

**The one real argument in favour, and why it does not currently apply.** Two
documents *can* isolate a syntax error in beats from the metadata, which is very
much in the spirit of D-018 — a script whose beats block is mid-edit and broken
could still report its status to `agsoc video list`. `safe_load_all` is a lazy
generator, so this is genuinely achievable:

```
=== F: doc 2 has a syntax error ===
  list() raises: ParserError
  lazy next() doc1: {'status': 'draft'}
```

But `_read` calls `list(...)`, which drives the generator to completion and
throws the isolation away. Today the format pays the full confusion cost of
multi-document YAML and collects none of its benefit.

So: **either** collapse to a single document with `beats:` at the top level — my
recommendation, and it is cheap right now: one `_dump`, one `_read`, and two test
assertions — **or** keep two documents and commit to the reason for them by
adding a metadata-only read path (`next(iter(safe_load_all(text)), {})`) that
`load_episode` and `episode_ids` use, so a broken beats block genuinely cannot
stop you reading status. What I would not do is keep the current shape, which is
the costs of one design and the benefits of neither. If you keep two documents,
the module docstring should also stop claiming the fences are not frontmatter,
because as bytes they are.

### Q3 — Is `_read`'s `{"beats": []}` substitution tolerance or data loss?

**Data loss, and F2 is not hypothetical — I reproduced it.**

The distinction that matters is between the *read* and the *write*. Substituting
a default on read is defensible: it is what makes
`test_load_tolerates_a_single_document_script` and
`test_load_tolerates_an_empty_script` pass, and being able to read the status out
of a half-written file is exactly the D-018 diagnostic posture. Nothing is
destroyed by a tolerant read.

The problem is that `set_status` then writes the substitute back. Tolerance
becomes destruction the moment the fallback round-trips to disk. And the
`isinstance(docs[1], dict)` guard fires on more than just absence — F2 shows a
perfectly well-formed beats sequence being replaced by `beats: []` and written
out, and F3 shows a third document being dropped the same way. In both cases the
user's data was intact on disk, was parsed successfully, and was deleted by an
operation whose entire job was to change one string in a different document.

There is no error, no warning, no backup. The operator's next `git diff` — if the
workspace is even under git — is the only thing standing between them and a lost
script.

The asymmetry is the tell: `set_status` is scrupulous about not touching the file
when the *transition* is invalid (`assert_transition` runs first, and
`test_a_rejected_transition_does_not_touch_the_file` pins byte-identity), but
entirely relaxed about destroying document 2 when the transition is valid. The
same care should apply to both.

What I would do, in order of preference:

1. Distinguish *absent* from *malformed*. Absent (fewer than two documents, or a
   `None` document from an empty file) → substitute `{"beats": []}`, that is real
   tolerance and it is what the two passing tolerance tests actually describe.
   Malformed or unexpected shape → raise `EpisodeError` naming the file, because
   silently rewriting a document you could not understand is not tolerance.
2. Failing that, preserve on write what you could not parse: keep the raw text of
   document 2 and re-emit it verbatim instead of re-serialising a substitute.
   Lossless, and it makes `set_status` genuinely a document-1-only operation,
   which is what the module docstring already promises: *"document 2 must survive
   every write here untouched"*. As implemented, it does not — that sentence is
   currently aspirational rather than true.

Note that fixing Q2 by collapsing to a single document also dissolves most of
this: with one document there is no positional second document to mis-model, no
third document to drop, and `beats` is just a key you leave alone.
