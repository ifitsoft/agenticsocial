# Task 3b Report: Never parse, never rewrite, never lose the beats document

**Branch:** `feat/video-phase-01-scaffolding`
**Commits:** `4084bbc` (tests), `e0c00da` (implementation)

## 1. What I changed

Implemented the brief exactly as written. No deviations; the code blocks and the
prose agreed everywhere.

`src/agenticsocial/video/episode.py`:

- New module docstring stating that Phase 1 never parses document 2, why, and
  the `frontmatter.parse` trap warning.
- Deleted `_dump` and `_read`.
- Added `_SEP`, `_split` (purely textual), `_parse_meta` (wraps `yaml.YAMLError`
  in `EpisodeError`, rejects non-mapping metadata), `_read_meta` (wraps `OSError`
  too), `_compose`.
- `create_episode` wraps the `atomic_write` in `try/except BaseException` with
  `shutil.rmtree(d, ignore_errors=True)` then re-raise, mirroring
  `scaffold_series`.
- `load_episode` uses `path.is_file()` and `_read_meta`.
- `episode_ids` uses `.is_file()` and gained the D-018 docstring.
- `set_status` reads metadata + verbatim beats text, mutates only `status`, and
  re-emits via `_compose`.

`grep -rn "_dump\|_read(" src/` returns only `yaml.safe_dump` call sites and the
docstring mention — no dangling references.

`tests/test_video_episode.py`: appended the 12 test functions from Step 1a
(15 test cases including the 4-way parametrize). No existing test edited.

## 2. TDD evidence

### RED — after Step 1a, before implementation

```
FAILED tests/test_video_episode.py::test_set_status_preserves_a_sequence_beats_document_verbatim
FAILED tests/test_video_episode.py::test_set_status_preserves_comments_and_formatting_in_beats
FAILED tests/test_video_episode.py::test_set_status_preserves_a_third_document
FAILED tests/test_video_episode.py::test_beats_bytes_are_identical_across_a_status_change
FAILED tests/test_video_episode.py::test_status_is_readable_even_when_beats_is_unparseable
FAILED tests/test_video_episode.py::test_unparseable_metadata_raises_episode_error[---\n: : :\n  - broken\n---\nbeats: []\n]
FAILED tests/test_video_episode.py::test_unparseable_metadata_raises_episode_error[---\nepisode: [unclosed\n---\nbeats: []\n]
FAILED tests/test_video_episode.py::test_unparseable_metadata_raises_episode_error[\x00\x01 not yaml at all\n]
FAILED tests/test_video_episode.py::test_unparseable_metadata_raises_episode_error[---\n"unterminated\n---\nbeats: []\n]
FAILED tests/test_video_episode.py::test_non_mapping_metadata_raises_episode_error
FAILED tests/test_video_episode.py::test_failed_create_leaves_no_partial_directory
FAILED tests/test_video_episode.py::test_episode_ids_ignores_a_directory_where_the_script_should_be
======================== 12 failed, 28 passed in 0.33s =========================
```

**12 failed, 28 passed.** Two of the new tests passed on the old code and are
therefore not RED evidence: `test_episode_ids_survives_an_unparseable_script`
and `test_resolve_a_healthy_episode_despite_an_unparseable_neighbour`. Both
already held because `episode_ids` never parsed anything. They are regression
guards, not new behaviour — that is correct, not a defect in the brief.

### GREEN — file suite

```
collected 40 items

tests/test_video_episode.py ........................................     [100%]

============================== 40 passed in 0.24s ==============================
```

### GREEN — full suite

```
tests/test_video_status.py ....................                          [ 90%]
tests/test_workspace.py .................                                [ 98%]
tests/test_x_client.py ....                                              [100%]

============================= 224 passed in 0.70s ==============================
```

**224 passed, 0 failed.**

## 3. Mutation results

All six mutants killed. `git checkout -- src/agenticsocial/video/episode.py`
between each; `git diff --stat` confirmed each mutation actually landed before
running.

| # | Mutation | Result | Caught by |
|---|----------|--------|-----------|
| 1 | `_compose` re-serialises beats via `yaml.safe_dump(yaml.safe_load(beats_text))` | **KILLED** (4 failed, 36 passed) | `test_set_status_preserves_a_sequence_beats_document_verbatim`, `..._preserves_comments_and_formatting_in_beats`, `..._preserves_a_third_document`, `test_beats_bytes_are_identical_across_a_status_change` |
| 2 | `_parse_meta` drops the `try`, `yaml.YAMLError` escapes | **KILLED** (4 failed, 36 passed) | all four `test_unparseable_metadata_raises_episode_error` params |
| 3 | `_parse_meta` drops the non-mapping check | **KILLED** (1 failed, 39 passed) | `test_non_mapping_metadata_raises_episode_error` |
| 4 | `episode_ids` `.is_file()` → `.exists()` | **KILLED** (1 failed, 39 passed) | `test_episode_ids_ignores_a_directory_where_the_script_should_be` |
| 5 | `create_episode` loses the `rmtree` cleanup | **KILLED** (1 failed, 39 passed) | `test_failed_create_leaves_no_partial_directory` |
| 6 | `_split` returns `text, None` always | **KILLED** (18 failed, 22 passed) | 18 tests, including all four preservation tests and `test_set_status_persists_and_preserves_beats` |

Mutant 1 and mutant 6 — the two you flagged as load-bearing — are both killed by
multiple independent tests. The preservation guarantee is pinned.

Note on mutant 1: `test_status_is_readable_even_when_beats_is_unparseable` does
**not** catch it, because `load_episode` never calls `_compose`. The unparseable
beats never reach a write path in that test. If you want the write path pinned
against unparseable beats too, that would need a `set_status`-on-broken-beats
test. I am reporting this rather than adding it, per the brief.

## 4. Step 1b confirmation

Both existing tests pass **unmodified**, verified in the `-v` run after the
implementation landed:

```
tests/test_video_episode.py::test_created_script_is_two_yaml_documents PASSED [  5%]
tests/test_video_episode.py::test_set_status_persists_and_preserves_beats PASSED [ 52%]
```

The on-disk format for a freshly created script is unchanged.

## 5. Files changed

- `src/agenticsocial/video/episode.py` — commit `e0c00da`
- `tests/test_video_episode.py` — commit `4084bbc`

Nothing under `docs/` was staged. `git status --porcelain -- src tests` is empty
after the mutation run.

## 6. Issues and concerns

### 6.1 Is textual splitting on `"\n---\n"` safe?

**The block-scalar worry specifically cannot bite. But `_split` diverges from
YAML in the other direction, and that divergence is real.**

I probed eight shapes against both `yaml.safe_load_all` and `_split`.

**Why a block scalar cannot break it.** YAML block scalar content must be
indented strictly more than its parent node. A `---` line *inside* a block
scalar is therefore always preceded by at least one space, so it is `"\n  ---\n"`,
never `"\n---\n"`, and `str.find` cannot see it. Confirmed:

```
'---\nepisode: e1\nnotes: |\n  first\n  ---\n  second\nstatus: draft\n---\nbeats: []\n'
  yaml docs: [{'episode': 'e1', 'notes': 'first\n---\nsecond\n', 'status': 'draft'}, {'beats': []}]
  _split meta: 'episode: e1\nnotes: |\n  first\n  ---\n  second\nstatus: draft'
  _split beats: 'beats: []\n'
```

`_split` and PyYAML agree exactly. The same argument covers a `---` inside a
quoted scalar or a flow collection: a column-0 `---` is a directives-end marker
in every context, so any file where `"\n---\n"` appears at column 0 *not* as a
document boundary is not valid YAML in the first place. I could not construct a
valid `script.yaml` where the block-scalar hazard fires. **That part of the
design is sound and the reasoning is a proof, not a hope.**

**The real breaks are the opposite failure: separators YAML accepts that
`_split` misses.** Three shapes, all valid YAML, all now unreadable:

| Shape | `safe_load_all` | `_split` | Net effect |
|---|---|---|---|
| CRLF line endings (`---\r\nepisode: e1\r\n...`) | 2 docs, fine | whole file → metadata, beats `None` | `_parse_meta` gets a multi-document string → `ComposerError` → `EpisodeError`. Episode unreadable. |
| Separator with trailing space (`--- \n`) | 2 docs, fine | separator missed | same — `EpisodeError` |
| No leading `---`, but a second document present | 2 docs, fine | separator missed (guard returns early) | same — `EpisodeError` |

The third is narrow, but the first is not: a `script.yaml` opened and saved by a
Windows editor becomes an unreadable episode. Old `_read` handled all three.

Damage assessment: **none of these lose data.** `load_episode` raises before
`set_status` can be reached, so no write happens; and the error is loud
(`EpisodeError`, correctly typed for Task 4's handler) rather than silent. But
the message says "cannot parse script metadata" for a file that parses fine,
which will send an operator hunting for a YAML bug that does not exist.

There is also one inverse case — `_split` **accepting** a file YAML rejects:

```
'---\nepisode: e1\nnotes: |\n  first\n---\n  second\nstatus: draft\n---\nbeats: []\n'
  yaml ERROR: ScannerError
  _split meta: 'episode: e1\nnotes: |\n  first'    -> parses to {'episode': 'e1', 'notes': 'first'}
```

A column-0 `---` inside a block scalar makes the whole file invalid YAML, but
`_split` truncates at it and hands `_parse_meta` a fragment that parses cleanly.
We report a status for a file PyYAML would refuse. Everything after the cut is
preserved verbatim as "beats", so nothing is destroyed — but `status: draft` from
that fragment ends up living in the beats bytes. Cosmetically wrong, not lossy.

**Recommendation** (not applied — out of scope for this task): normalise CRLF to
LF before splitting, and match the separator with a small regex
(`^---[ \t]*$`, multiline) rather than a literal `"\n---\n"`. Both keep the
"never parse document 2" guarantee intact.

### 6.2 Should `_compose` write `beats: []` when document 2 is absent?

**It is defensible but I think it is the wrong default, and the current code
hides the asymmetry.**

Today `_compose(meta, None)` emits `beats: []`, so a single-document script that
goes through `set_status` silently *gains* a second document. That is a creation,
not a loss, and it normalises the file to the shape `create_episode` produces.
But it is still us rewriting a part of the file we just declared we do not own —
the same instinct the rest of this task is correcting.

The cleaner shape is to make `create_episode` the only place that knows the
default:

```python
def _compose(meta: dict, beats_text: str | None) -> str:
    head = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{head}\n" if beats_text is None else f"---\n{head}\n---\n{beats_text}"
```

with `create_episode` calling `_compose(meta, "beats: []\n")`. Absence is then
preserved as absence, `test_created_script_is_two_yaml_documents` still passes,
and `_compose` stops having a policy opinion. I did not make this change because
the brief's code block is explicit and authoritative; flagging it for your call.

### 6.3 Does anything still lose data on a write path?

`set_status` is the only mutating write to `script.yaml` in the codebase
(`grep -rn "script.yaml\|script_path" src/` finds only `episode.py` and the
`Episode.script_path` property). It loses:

1. **Document 1's comments and formatting — every time.** `_compose` runs
   `yaml.safe_dump` over the metadata dict, so comments, blank lines, quoting
   style, and block scalars in document 1 are destroyed on any status change.
   This is by design (we own document 1) and the brief accepts it, but it should
   be stated: the "an operator's deliberate formatting survives" guarantee
   applies to beats only. If the storyboard skill ever writes a comment above
   `status:`, it is gone on first approve.
2. **Nothing else.** Unknown metadata keys survive — `_read_meta` returns the
   whole dict and only `status` is reassigned. Key order survives
   (`sort_keys=False`). Documents 2 through N survive byte-for-byte, since
   everything after the first separator is one opaque string. Beats trailing
   newline (or absence of one) survives. `atomic_write` cleans up its temp file
   on any exception, so a failed write leaves the original intact — pinned by
   `test_a_rejected_transition_does_not_touch_the_file`.

One residual sharp edge, not data loss: `set_status` will happily write an
episode whose beats document is syntactically broken, re-emitting the broken
bytes. That is the correct behaviour under this design (we do not validate what
we do not own), but it means `agsoc video approve` can approve an unrenderable
script. Phase 3's beats parser should gate approval, and Task 4 should not
assume `set_status` succeeding implies a valid script.
