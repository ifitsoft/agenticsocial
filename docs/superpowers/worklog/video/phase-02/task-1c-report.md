# Task 1c Report: Pin the rules, not the outcomes

**Branch:** `feat/video-phase-02-ingest` · **Base:** `39e2993`

## 1. What I changed

**Step 1 — tests only (`f4f3981`).** Replaced the two named vacuous tests and
appended the nine rule pins, all verbatim from the brief. No other existing test
touched.

- `test_document_text_refuses_a_traversing_key` — now `match="unsafe"`, so each
  key must be refused *as unsafe*, not merely as absent.
- `test_verify_reports_everything_missing_when_the_corpus_dir_is_gone` →
  `test_verify_is_silent_when_the_corpus_dir_does_not_exist`. No recreate, no
  manifest restore, so the guarded branch is actually entered.

**Step 2 — source (`742f8a5`).**

- **2a.** `read_manifest` now validates entry shape as well as the top level.
- **2b.** No change — see below. Verified, not assumed.
- **2c.** `verify`'s missing-`sources_dir` branch now `return problems` (an empty
  list by construction) with a comment saying why the old list comprehension was
  provably dead.

### 2b: verified, and the brief's prediction was wrong

The brief asked me to check rather than reason, so I instrumented `key_for` with
a spy and called the empty-key path:

```
$ uv run python /tmp/probe_2b.py
raised: CorpusError | unsafe source key '' — must be a single directory name, not a path
key_for called with: []
```

`key = key if key is not None else key_for(url)` binds `""` (not `None`), so
`key_for` is **never reached** and `assert_safe_name` rejects `""` immediately.
The existing code is correct as the brief said; the consequence is that
`test_an_explicit_empty_key_is_refused_not_replaced` **passed on arrival**, which
contradicts the brief's "expect failures on: the empty-key test". Not a defect in
the code block, only in the prose prediction — flagging it for the count.

## 2. Which new tests failed at RED vs passed on arrival

**Exactly one of the eleven new/replaced tests failed at RED.** Ten passed on
arrival. There was no red-to-green cycle for those ten and I am not going to
imply one.

```
$ uv run pytest tests/test_video_corpus.py   (at f4f3981, before the source fix)
FAILED tests/test_video_corpus.py::test_a_manifest_whose_entries_are_not_objects_is_a_corpus_error
                                                        - Failed: DID NOT RAISE CorpusError
========================= 1 failed, 46 passed in 0.37s =========================
```

| Test | At RED |
|---|---|
| `test_a_manifest_whose_entries_are_not_objects_is_a_corpus_error` | **FAILED** |
| `test_a_manifest_that_is_a_json_array_is_a_corpus_error` | passed on arrival |
| `test_an_explicit_empty_key_is_refused_not_replaced` | passed on arrival (brief predicted a failure) |
| `test_document_text_refuses_a_traversing_key` (7 cases, `match="unsafe"`) | passed on arrival (brief said "possibly") |
| `test_verify_is_silent_when_the_corpus_dir_does_not_exist` | passed on arrival |
| `test_only_a_leading_www_is_stripped` | passed on arrival |
| `test_the_collision_suffix_format_is_stable` | passed on arrival |
| `test_write_creates_the_sources_dir_when_absent` | passed on arrival |
| `test_fetched_at_is_a_plausible_timestamp` | passed on arrival |
| `test_an_explicit_fetched_at_is_recorded_verbatim` | passed on arrival |
| `test_a_subdirectory_is_not_an_orphan` | passed on arrival |

That is the expected shape for this kind of task: these tests pin behaviour the
code already had and nothing checked. Step 3 is the only evidence they bite.

## 3. Mutation results — all nine killed

Each mutant applied to `corpus.py`, full suite run, file restored between.

| # | Mutant | Result | Killed by |
|---|---|---|---|
| 1 | `key_for`: `startswith("www-")` → `"www" in key` | **killed** | `test_only_a_leading_www_is_stripped` |
| 2 | collision counter starts at `1` | **killed** | `test_the_collision_suffix_format_is_stable` |
| 3 | `key if key is not None else …` → `key or key_for(url)` | **killed** | `test_an_explicit_empty_key_is_refused_not_replaced` |
| 4 | drop `sources_dir.mkdir` | **killed** | `test_write_creates_the_sources_dir_when_absent` |
| 5 | `fetched_at` default → `""` | **killed** | `test_fetched_at_is_a_plausible_timestamp` |
| 6 | `verify`: drop the `not entry.is_file()` orphan skip | **killed** | `test_a_subdirectory_is_not_an_orphan` |
| 7 | `read_manifest`: drop the entry-shape loop | **killed** | `test_a_manifest_whose_entries_are_not_objects_is_a_corpus_error` |
| 8 | `read_manifest`: drop the top-level `isinstance` | **killed** | `test_a_manifest_that_is_a_json_array_is_a_corpus_error` |
| 9 | `document_text`: drop `assert_safe_name` | **killed** (8 failures) | all 7 traversal cases + `..._cannot_reach_outside_the_corpus` |

```
MUTANT 1: rc=1 | 1 failed, 429 passed
    FAILED tests/test_video_corpus.py::test_only_a_leading_www_is_stripped
MUTANT 2: rc=1 | 1 failed, 429 passed
    FAILED tests/test_video_corpus.py::test_the_collision_suffix_format_is_stable
MUTANT 3: rc=1 | 1 failed, 429 passed
    FAILED tests/test_video_corpus.py::test_an_explicit_empty_key_is_refused_not_replaced
MUTANT 4: rc=1 | 1 failed, 429 passed
    FAILED tests/test_video_corpus.py::test_write_creates_the_sources_dir_when_absent
MUTANT 5: rc=1 | 1 failed, 429 passed
    FAILED tests/test_video_corpus.py::test_fetched_at_is_a_plausible_timestamp
MUTANT 6: rc=1 | 1 failed, 429 passed
    FAILED tests/test_video_corpus.py::test_a_subdirectory_is_not_an_orphan
MUTANT 7: rc=1 | 1 failed, 429 passed
    FAILED tests/test_video_corpus.py::test_a_manifest_whose_entries_are_not_objects_is_a_corpus_error
MUTANT 8: rc=1 | 1 failed, 429 passed
    FAILED tests/test_video_corpus.py::test_a_manifest_that_is_a_json_array_is_a_corpus_error
MUTANT 9: rc=1 | 8 failed, 422 passed
    FAILED tests/test_video_corpus.py::test_document_text_refuses_a_traversing_key[../../../series]
    FAILED tests/test_video_corpus.py::test_document_text_refuses_a_traversing_key[../secret]
    FAILED tests/test_video_corpus.py::test_document_text_refuses_a_traversing_key[a/b]
    FAILED tests/test_video_corpus.py::test_document_text_refuses_a_traversing_key[..]
    FAILED tests/test_video_corpus.py::test_document_text_refuses_a_traversing_key[.]
    FAILED tests/test_video_corpus.py::test_document_text_refuses_a_traversing_key[]
    FAILED tests/test_video_corpus.py::test_document_text_refuses_a_traversing_key[a\b]
    FAILED tests/test_video_corpus.py::test_document_text_cannot_reach_outside_the_corpus
```

**Bonus — Task 1b's surviving mutant 3 is now dead.** Deleting the whole
missing-`sources_dir` guard (so `iterdir()` raises `FileNotFoundError`):

```
BONUS (Task 1b mutant 3 - drop the missing-sources_dir guard): rc= 1
1 failed, 429 passed
   FAILED tests/test_video_corpus.py::test_verify_is_silent_when_the_corpus_dir_does_not_exist
```

## 4. Files changed and commit SHAs

| Commit | SHA | Files |
|---|---|---|
| 1 — tests | `f4f3981` | `tests/test_video_corpus.py` |
| 2 — source | `742f8a5` | `src/agenticsocial/video/corpus.py` |

Final suite: **430 passed** (was 421 at `39e2993`; +9 = 11 new/replaced tests
minus the 2 replaced originals, one of which was 7 parametrised cases that
carried over unchanged in count).

```
$ uv run pytest
============================= 430 passed in 1.37s ==============================
```

`git status --porcelain -- src tests` is empty. Nothing under `docs/` staged.

## 5. Issues and concerns

### Q1 — Re-run of the 14-mutant sweep: 12 survivors → 5, all cosmetic

Same fourteen mutants as Task 1b, same method, full suite each time:

```
KILLED    A key_for: startswith('www-') -> 'www' in key
KILLED    B read_manifest: drop top-level isinstance(dict)
KILLED    C write_document: collision counter starts at 1
SURVIVES  D manifest json: sort_keys=False
SURVIVES  E manifest json: indent=None
SURVIVES  F manifest json: ensure_ascii=True
KILLED    G write_document: non-atomic document write
KILLED    H verify: drop the not entry.is_file() orphan skip
KILLED    I write_document: key is not None -> key or key_for(url)
SURVIVES  J write_document: drop the post-collision assert_safe_name recheck
KILLED    K write_document: drop sources_dir.mkdir
SURVIVES  L verify: drop sorted() around iterdir
KILLED    M write_document: fetched_at default -> ''
KILLED    N verify: compare recorded byte count instead of sha256

SURVIVORS: 5/14
```

**All seven mutants I classified as *real* in Task 1b (A, B, C, H, I, K, M) are
now killed.** The five survivors are exactly the five I classified as cosmetic,
and I still hold that classification:

- **D, E, F** — manifest JSON formatting. All three round-trip to the same
  `dict`; the weaker version is not observably worse, only noisier in diffs.
  Pinning them would pin *the file's byte layout*, which is a real contract only
  if something outside this module diffs or parses the raw text. Nothing does.
- **J** — the post-collision `assert_safe_name` recheck is genuinely
  unreachable: `base` was already checked, and appending `-{n}` for integer `n`
  cannot introduce `/`, `\`, or turn a name into `.`/`..`/`""`. It is not
  testable because it is not reachable. Worth a comment saying so, or deleting;
  I did neither, since neither is in scope for this task.
- **L** — `sorted()` around `iterdir` is redundant given the final
  `sorted(problems)`. Also not worth pinning.

**Nothing real survives in `corpus.py`.** I would call the module closed, as the
brief intended.

### Q2 — Is "tests pin outcomes, not rules" a property of your briefs, or of example-based testing?

**Of example-based testing generally — but your briefs have a specific habit that
makes it hit every time, and that habit is fixable.**

The general part first. An example is a point; a rule is a function. Any finite
set of points is consistent with infinitely many functions, so example-based
tests *always* underdetermine the rule. That is not a flaw you can write your way
out of by being more careful — it is what examples are. Four phases of the same
finding is not four mistakes, it is the same structural fact showing up four
times.

But the fact that it lands in your briefs *reliably* is not general. It is this:
**your briefs specify tests by writing the assertion, and the assertion is
written after you already know the implementation.** When you write
`assert C.key_for("https://www.reuters.com/x") == "reuters-com"`, you are reading
that value off the code you just designed. The test is a transcription of the
implementation's output on one input. Transcriptions cannot fail to agree with
what they transcribed, which is exactly what "passed on arrival" means — ten of
eleven this task, four of four last task. A test derived from the implementation
can only ever pin what the implementation already does; it can never pin what it
*must* do.

Concretely, four things I would change about how the briefs specify tests:

1. **State the rule in the brief as a sentence, before any assertion, and make
   the test's job to be false if that sentence is false.** "A leading `www-` is
   stripped; `www` elsewhere is not" is a sentence with a negative half. The
   negative half is where the mutant lives, and it is the half examples never
   supply on their own. Every rule pin in this task that killed a mutant had a
   negative half; every test that passed on arrival and killed nothing (D/E/F
   territory) had none. **Write the sentence first, then ask what the cheapest
   input is that separates it from its nearest weaker neighbour.**

2. **Specify the mutant, not the assertion.** You already do this brilliantly in
   Step 3 and then throw the information away. Step 1 asks for a test; Step 3
   asks for a mutant; the two are written independently and the test is only
   accidentally the one that kills the mutant. Invert it: **for each behaviour,
   name the weaker implementation first, and let the assertion be whatever is
   needed to distinguish it.** That is the same discipline as writing the failing
   test first, applied at the level of the brief. It would have caught both
   vacuous tests in this task at authoring time — `match="unsafe"` is *derived*
   from "the mutant drops the guard", it is not something you'd think to add
   while writing a happy-path assertion.

3. **For every test, say what state the fixture must NOT already be in.** Both
   vacuous tests failed for this reason and nothing else: the traversal test
   never created the file it was reaching for, and the deleted-dir test recreated
   the directory. `test_write_creates_the_sources_dir_when_absent` only works
   because it `rmtree`s first. A one-line "precondition:" field per test —
   *"sources_dir must not exist"*, *"a file must exist at the traversal target"* —
   would surface the vacuity while the brief is still text. This is the single
   highest-yield change of the four and it costs a line per test.

4. **Where a rule is genuinely infinite, stop enumerating and use a property.**
   `key_for` is a pure `str -> str` with an invertible-ish rule; three examples
   pin it about as well as three examples ever pin anything. A property —
   *"`key_for(u)` never starts with `www-`, and equals `host.replace('.','-')`
   whenever the host does not start with `www.`"* — is the rule itself, and no
   mutant that changes the rule can pass it. Not everything deserves this; keys,
   collision suffixes, and anything a claim cites by name do, because those are
   the values other subsystems will hard-code against.

One caution against over-correcting: examples are still the right tool for the
*boundaries* of a rule and for anything whose value is a contract with the
outside world (the `-2` suffix format, the `"unsafe"` word in the error). The
change is not "fewer examples". It is that **an example should be chosen because
it discriminates, not because it illustrates.** Right now the briefs choose
illustrative examples — `blog.google`, `venturebeat.com` — which are the examples
a *reader* needs. The discriminating example is `blog.wwwfoo.com`, which no
reader needs and every mutant fears. Those are different sets, and the brief has
been picking from the wrong one.

### Defect count

One new item for the ledger, minor and in prose rather than a code block: the
brief predicted `test_an_explicit_empty_key_is_refused_not_replaced` would fail
at RED. It does not — `assert_safe_name` rejects `""` before `key_for` is ever
consulted, exactly as Step 2b's own prose says. The prediction and the analysis
in the same brief disagree with each other; the analysis is the correct one.
