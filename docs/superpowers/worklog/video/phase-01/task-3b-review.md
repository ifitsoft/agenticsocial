# Task 3b QA Review — episode scaffolding and the beats-byte guarantee

**Reviewer:** QA (adversarial) · **Date:** 2026-08-16 · **Branch:** `feat/video-phase-01-scaffolding`
**Reviewed:** `98a6c7a`, `512655e`, `4084bbc`, `e0c00da`; final state of
`src/agenticsocial/video/episode.py`; `git diff 2dbf3e9..e0c00da -- src tests`.
I did not read `task-3-report.md` or `task-3b-report.md`.

## Verdict

**changes-required** — but narrowly. The four commits are correct enough to merge
as they stand; what must change is the *record*. **D-029 states the CRLF case is
"not a defect". It is a defect, and it is a defect of exactly the kind this task
exists to prevent: `set_status` rewrites every byte of the beats document when the
file uses CRLF line endings.** The leader's re-verification checked that `_split`
still finds two documents through `_read_meta`; it did not check byte identity,
which is the actual guarantee. The implementer's headline ("CRLF breaks `_split`")
was wrong about the mechanism and right about the outcome.

Everything else is in good shape. 11 of 13 checklist/brief mutants killed, the one
real survivor class is the same whitespace blind spot that lets F1 through, the
error contract holds on every read path, and the textual-split design is sound in
ways I actively tried and failed to break.

---

## Findings

### F1 · Medium-High · `episode.py:66` (`_read_meta`) + `episode.py:73-76` (`_compose`) — CRLF and lone-CR beats bytes are silently rewritten

`path.read_text(encoding="utf-8")` opens in text mode with **universal newlines**.
`\r\n` and lone `\r` are converted to `\n` before `_split` ever runs, and
`_compose` re-emits the converted text. The bytes after the first `\n---\n` are
therefore *not* identical across a status change.

Reproduced through the production path (`create → write_bytes → load_episode → set_status`):

| doc 2 written as | doc 2 after `set_status` | |
|---|---|---|
| `b'beats:\r\n- a: 1\r\n'` | `b'beats:\n- a: 1\n'` | **CHANGED** |
| `b'beats:\r- a: 1\r'` | `b'beats:\n- a: 1\n'` | **CHANGED** |
| whole file CRLF | whole file LF | **CHANGED** |

Concrete failure: an operator opens `script.yaml` in an editor that saves CRLF (or
the repo is ever cloned with `core.autocrlf=true`), then runs `agsoc video approve`.
Every line of the beats block changes on disk. `script_sha256` changes with it, so
spec §10's drift detection fires on churn we caused — the precise scenario D-026
gives as the *reason* for the two-document design. The storyboard skill's
formatting is preserved in content but not in bytes.

Fix (already half-scheduled — Task 5 is slated to replace the literal `find` with
a `^---[ \t]*$` regex; do both in one pass):

```python
text = path.open(encoding="utf-8", newline="").read()   # no newline translation
...
m = re.search(r"\r?\n---[ \t]*\r?\n", text)             # separator, either ending
```

and have `_compose` join document 1 to the remainder with the *file's own*
separator bytes so an all-CRLF file stays all-CRLF. Do not fix by normalising to
LF on write — that is the current behaviour and it is the bug.

**Required now regardless of scheduling:** amend D-029's table. The row
`| CRLF | 2 docs | **OK** | **not a defect** — universal newlines |` is wrong and
will be read later as evidence the guarantee holds.

### F2 · Medium · `tests/test_video_episode.py` — the byte guarantee is only pinned for LF text ending in a newline

Every preservation test writes with `write_text` and compares with `read_text`,
so the suite pins *content* survival, not *byte* survival. Surviving mutants that
prove the gap (full suite, 224 tests, all green under each):

- `_read_meta` returning `beats_text.rstrip() + "\n"` — **survives**
- `_compose` appending a missing trailing newline to the beats body — **survives**
- `_compose` doing `beats_text.replace("\t", "    ")` — **survives**
- `_read_meta` doing an explicit `.replace("\r\n", "\n")` (i.e. F1 made deliberate) — **survives**

Fix: one test written at the byte level.

```python
def test_beats_bytes_survive_exotic_whitespace(series):
    ep = create_episode(series, "2026-08-14")
    beats = b"beats:\t\r\n  - a: 1\r\n\r\n\r\n  - b: 2   "   # CRLF, tabs, blanks, no final \n
    ep.script_path.write_bytes(
        b"---\nepisode: 2026-08-14\nseries: the-brief\nstatus: draft\n---\n" + beats
    )
    set_status(load_episode(series, "2026-08-14"), Status.IN_REVIEW)
    assert ep.script_path.read_bytes().split(b"\n---\n", 1)[1] == beats
```

This test fails today (F1) and kills all four mutants above.

### F3 · Medium · `episode.py:125-132` (`episode_ids`) — the enumerator *can* fail, with a non-`EpisodeError`

The docstring says "Parses nothing, so it cannot fail… Task 4's `except EpisodeError`
depends on this." `iterdir()` still raises. `chmod 000 series/the-brief/episodes`
→ `episode_ids` raises `PermissionError`, which `agsoc video list` will not catch —
the exact traceback D-018 exists to prevent, on the diagnostic command.

Same family, lower value: `create_episode` raises bare `OSError` subclasses from
`mkdir` (`PermissionError` on an unwritable `episodes_dir`; `FileExistsError` when
the episode name is a **dangling symlink**, since `d.exists()` follows the link and
returns `False`). Note this is *inconsistent*: when the name is taken by a regular
file you get a clean `EpisodeError`, by a dangling symlink a raw `FileExistsError`.
The suite deliberately pins `OSError` propagation from `atomic_write`
(`test_failed_create_leaves_no_partial_directory`), so the write path is by design —
but `episode_ids` is not, and its docstring makes a promise it does not keep.

Fix: wrap `iterdir()` in `try/except OSError → EpisodeError` (or return `[]`), and
decide explicitly whether `create_episode` is inside or outside the `EpisodeError`
contract rather than leaving it split.

### F4 · Low · `episode.py:79-84` (`create_episode`) — no id validation; `..` escapes the series

`create_episode(series, "../escape")` succeeds and creates
`series/the-brief/escape/{sources,out,probe,script.yaml}` — outside `episodes_dir`,
invisible to `episode_ids`, unreachable by `resolve_episode`, and it silently
collides with the series' own layout. `"a/b"` behaves the same way. Belongs to
Task 5's widened "input robustness and validation" charter; noting it so it is not
discovered from a CLI bug report.

### F5 · Low · `episode.py:144-161` (`resolve_episode`) — empty query resolves

`resolve_episode(series, "")` → the empty string is a substring of every id, so
with exactly one episode it silently resolves to it, with two it reports
"matches multiple episodes", with none "no episode matching ''". An empty query
should be rejected up front. Otherwise the matching is sane: exact wins over
substring (verified with ids `["08-14", "2026-08-14"]`, query `"08-14"` → exact
`"08-14"`), ambiguity lists candidates. Minor wart: the exact-match test is
case-sensitive while the substring pass is case-insensitive — only observable on a
case-sensitive filesystem, harmless.

### F6 · Low / carry-forward · `episode.py:164-170` (`set_status`) — stale in-memory status is never re-checked

`set_status` validates the transition against `episode.status` (in memory) but
re-reads `meta` from disk and overwrites `status` there unconditionally. Load an
episode as `draft`, let anything else move it to `approved`, then
`set_status(ep, IN_REVIEW)` succeeds and writes `in_review` over `approved` — a
transition that would have been rejected had it been evaluated against disk. Not
exploitable by a single-operator local CLI today; worth one line in the Phase 7
approve gate's requirements next to D-030 #2.

### F7 · Note · a third member of the known "we reject what PyYAML accepts" family

D-029 lists `--- ` (trailing space) and a missing leading `---`. There is a third:
a **`%YAML` directive** before the first `---` (`"%YAML 1.1\n---\nstatus: draft\n---\nbeats: []\n"`)
— PyYAML reads 2 documents, we raise `EpisodeError`. Same root cause (the file must
literally start with `---\n`), same fix, so just add it to the Task 5 item. A blank
line before the first `---` is the same case.

---

## What I verified

### Byte preservation across `set_status` (19 cases, run through the real API)

Method: `write_bytes` the file, `load_episode`, `set_status`, `read_bytes`, compare
everything after the first `\n---\n`.

| Input | Result |
|---|---|
| baseline LF | identical |
| **no trailing newline** | identical |
| doc 2 containing its own `---` | identical |
| **3rd and 4th documents** | identical |
| beats as a bare sequence | identical |
| beats as a bare scalar string | identical |
| doc 2 empty (file ends at the separator) | identical |
| doc 2 syntactically unparseable (`beats: [unclosed`) | identical |
| NUL / `\x01` bytes in doc 2 | identical |
| 200 000-character single line | identical |
| U+2028 line separator, emoji, non-ASCII | identical |
| tabs, trailing spaces in doc 2 | identical |
| form feed / vertical tab in doc 2 | identical |
| **CRLF in doc 2** | **CHANGED → F1** |
| **CRLF whole file** | **CHANGED → F1** |
| **lone CR in doc 2** | **CHANGED → F1** |
| empty file | `beats: []` inserted (known `_compose` default, Task 5) |
| file that is only `---\n` | `beats: []` inserted (same) |
| UTF-8 BOM | `EpisodeError` before any write — no data loss |

**The block-scalar worry raised in the brief is unfounded, and I confirmed it
rather than argued it.** A `---` line inside a block scalar is necessarily indented,
so the literal `"\n---\n"` never occurs; `"---\nnote: |\n  a\n  ---\n  b\n---\nbeats: []\n"`
splits exactly where PyYAML splits it. A top-level multi-line *quoted* scalar whose
continuation reaches column 0 is rejected by PyYAML too.

**Metadata cannot forge a separator.** I round-tripped `note` values of `'---'`,
`'a\n---\nb'`, `'\n---\n'`, `'x\n\n---\n\ny'`, `'  ---  '` through two consecutive
`set_status` calls: `safe_dump` always indents or quotes them, the beats block
survived every time, and the value read back unchanged. `_compose` is not injectable.

### `_split` vs PyYAML (29 constructed files)

Direction that matters most — **`_split` accepting a file PyYAML rejects, and us
then reporting a status for it: no case found.** Because `_parse_meta` runs
`safe_load` over exactly the text `_split` cut, agreement on document 1 follows from
agreement on the boundary, and the boundary only ever disagrees by cutting *early*.
Checked: `...` document-end marker, tab-indented mapping, duplicate keys, anchors
and aliases, `!!str`/`!!python` tags, unclosed flow collections spanning the
separator, `----`, `---` with no newline, `status: draft---`, doc 2 starting with
`---`, comment-only doc 1, empty doc 1, separator at byte 0. In every rejection case
both reject; in every acceptance case both produce the same document 1.
Disagreements found are the two known ones plus F7.

### Error contract (25 probes)

`EpisodeError` correctly raised for: unreadable `script.yaml` (chmod 000, both
`load_episode` and `set_status`), `script.yaml` that is a directory, `script.yaml`
that is a broken symlink, `script.yaml` deleted between load and `set_status`,
episode directory removed between load and `set_status`, episode name taken by a
regular file, `create_episode("")`, `create_episode(".")`, and every non-string
`status` value I tried (`3`, `true`, `null`, `[1]`, `{a: 1}`, a YAML date).
`episode_ids` returned `[]` for a broken-symlink script rather than raising.
Escapes found → F3.

### Mutation testing — 17 mutants, full suite (224 tests) per run

| # | Mutant | Result | Killed by |
|---|---|---|---|
| A | `_split` uses `find` without the leading-`---` check | KILLED | `test_resolving_the_corrupt_episode_itself_still_raises` |
| B | `_compose` drops the trailing newline | KILLED | `test_set_status_preserves_comments_and_formatting_in_beats` |
| C | `set_status` writes before asserting the transition | KILLED | `test_a_rejected_transition_does_not_touch_the_file` |
| D | `create_episode` creates subdirs after the script | **SURVIVED** | equivalent mutant — see below |
| E | `load_episode` loses the `is_file()` check | KILLED | `test_load_missing_episode_is_actionable` |
| F | `resolve_episode` matches over `list_episodes()` | KILLED | `test_resolve_a_healthy_episode_despite_a_corrupt_neighbour` |
| G | `_compose` re-serialises beats via `safe_dump(safe_load(...))` | KILLED | `test_set_status_preserves_comments_and_formatting_in_beats` |
| H | `_parse_meta` lets `yaml.YAMLError` escape | KILLED | `test_unparseable_metadata_raises_episode_error` |
| I | `_parse_meta` drops the non-mapping check | KILLED | `test_non_mapping_metadata_raises_episode_error` |
| J | `episode_ids` `.is_file()` → `.exists()` | KILLED | `test_episode_ids_ignores_a_directory_where_the_script_should_be` |
| K | `create_episode` loses the `rmtree` cleanup | KILLED | `test_failed_create_leaves_no_partial_directory` |
| L | `_split` always returns one document | KILLED | `test_load_returns_status_from_disk` |
| M | `_read_meta` rstrips the beats text | **SURVIVED** | → F2 |
| N | `_compose` appends a missing trailing newline to beats | **SURVIVED** | → F2 |
| O | `_compose` expands tabs in beats | **SURVIVED** | → F2 |
| P | `_compose` collapses blank lines in beats | KILLED | `test_set_status_preserves_comments_and_formatting_in_beats` |
| Q | `_read_meta` normalises CRLF explicitly | **SURVIVED** | → F1/F2 |

**Mutant D is equivalent, not a gap.** Creating `d` then the script then the
subdirectories leaves an identical end state; only the failure-atomicity window
moves, and the `rmtree` still covers it. I am not asking for a test.

**Mutants M/N/O/Q are one gap, not four:** nothing in the suite ever hands a write
path beats bytes that differ from their normalised form. F1 lives in that gap.

`git status --porcelain -- src tests` is **clean** after every mutant; `episode.py`
was restored from an in-memory copy of the committed text after each run and the
full suite is back to **224 passed**.

### Diff hygiene

- TDD order is genuine in history: `98a6c7a` tests only (219 lines), `512655e` impl
  only, `4084bbc` tests only (149 lines, **zero deleted lines** — no existing test
  was edited, confirming Step 1b), `e0c00da` impl only.
- No commit from this task touched `docs/`. (`DECISIONS.md` / the reports arrived in
  the leader's separate `7f6564f`.)
- Every one of the 37 test functions in `tests/test_video_episode.py` appears
  verbatim in one of the two briefs. **Nothing in the diff is unauthorised** — no
  extra helpers, no dependencies, no changes outside the two named files.
- Final `episode.py` matches brief 3b's authoritative code blocks; `_dump`/`_read`
  are gone with no dangling references.

---

## What I could not verify

- **Real Windows / `core.autocrlf` behaviour.** F1 was reproduced on macOS by writing
  CRLF bytes directly. I did not test on Windows, where `atomic_write`'s text-mode
  `os.fdopen(..., "w")` would additionally translate `\n` → `\r\n` on the way *out*,
  which changes the shape of the corruption (and may mask it in the simple case
  while still breaking mixed-ending files).
- **`script_sha256` impact end-to-end.** Spec §10's drift check does not exist yet,
  so F1's consequence is argued from the spec, not observed.
- **Concurrency.** No test of two processes calling `set_status` on one episode;
  `atomic_write` uses `os.replace`, so the file is never torn, but last-writer-wins
  and the F6 stale-status window are untested.
- **Filesystem case sensitivity.** Ran on a case-insensitive volume, so the
  `resolve_episode` case-sensitivity wart in F5 could not be exercised for real.
- Phase 3's actual beats parser does not exist, so "document 2 survives intact for
  Phase 3" is verified only as byte identity, not as parse-equivalence.
