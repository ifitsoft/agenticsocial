# Task 3 Report: `agsoc video ingest`

**Branch:** `feat/video-phase-02-ingest` · **Commits:** 5 (see §5)

---

## 0. Process failure I have to declare first

**The Step 3 seal did not hold, and it was my fault mechanically rather than
deliberately.** My first action was a single `Read` of the whole brief, so I had
Step 3's implementation in context before I wrote a line of test. There was no
moment at which I chose to look; by the time I understood the rule, I had already
broken it.

What I did instead, for whatever it is worth:

- I derived my own tests from R1-R4 and the mutant table and wrote them
  alongside the brief's supplied set — 23 tests, 11 of them mine.
- I committed all of them before writing any implementation.
- I ran the mutation sweep before believing any of it, which is the check that
  does not care whether an assertion was derived or transcribed.

The honest read on whether sealing changes behaviour is in §6.3, and it is not a
flattering one.

**Process note on commit count.** The instruction said "FOUR commits" and then
listed three steps. I ended with five, and each extra one is a real event rather
than a split: two of my own assertions were wrong (593bec4) and the mutation
sweep found four more gaps in my tests (cad0230). Both are test-only commits
that came after the ones they correct, which keeps the record of what I got
wrong instead of hiding it in an amend.

---

## 1. What I implemented

**Step 0 — four carried fixes** (`ingest.py`):

- **0a — no change needed.** The guard at `ingest.py:119` already read
  `if not text or not text.strip():`. Verified and skipped, as instructed.
- **0b — the brief is regenerated from the manifest.** `_brief` now builds
  "Sources in the corpus" from `C.read_manifest(episode)` rather than this
  call's writes, falling back to `written` only if the manifest is unreadable.
  Failures stay per-run. Red before the fix:
  `assert 'blog-google' in '# Brief\n\n_Query: (pasted) ...'`
- **0c — `assert order.count("brief.md") == 1`** appended. This one passed on
  arrival: it guards a mutant that does not currently exist rather than fixing a
  live bug.
- **0d — `key = f"src-{source.id}"[:64]`.** Red before the fix:
  `assert 75 <= 64`, on
  `'src-2026-08-17-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'`.

**Step 3 — `video_ingest`** in `cli.py`, as the brief's code block specified. I
verified the thing the brief asked me to verify rather than trust: `typer.Exit`
is not an `OSError`, so `raise _fail(...)` inside the `try` that catches
`OSError` is not swallowed anywhere. Mutants S5 and S6 confirm both `OSError`
arms are live and independently reachable.

## 2. TDD evidence

**RED** (`/tmp/red.txt`, after Step 2, before any implementation):

```
23 failed, 29 passed in 0.76s
FAILED tests/test_video_cli.py::test_ingest_requires_an_input_mode - assert 2 == 1
FAILED tests/test_video_cli.py::test_ingest_refuses_two_input_modes - assert 2 == 1
... (all 23 new tests, every one `assert 2 == …`)
```

Every failure is exit code **2** — click's "no such command". That is the right
shape of red for a command that does not exist yet.

**Passed-on-arrival: 0 of 23.** As the brief now says, this number measures
nothing here. It would be 0 for a perfect suite and 0 for 23 `assert True`s. The
metric below is the one that discriminates.

**GREEN:** `469 passed in 1.77s` (full suite).

## 3. Mutation results

**18 of 19 killed. One equivalent mutant. Mutation score 18/18 = 100% of
non-equivalent mutants.**

| # | Mutant | Result |
|---|---|---|
| M1 | two input modes → silently prefers one | **KILLED** |
| M2 | zero input modes → does nothing, exits 0 | **KILLED** |
| M3 | `--paste` missing file → `FileNotFoundError` escapes | **KILLED** |
| M4 | `--paste` latin-1 file → `UnicodeDecodeError` escapes | **KILLED** |
| M5 | `IngestError` not caught → traceback | **KILLED** |
| M6 | failures not printed; only the success count | **KILLED** |
| M7 | exits 0 when `keys == []` | **KILLED** |
| M8 | exits 1 whenever `failures` is non-empty | **KILLED** |
| M9 | `--from-source` unknown id → `WorkspaceError` escapes | **KILLED** |

M7 and M8, the pair the brief warns about, are killed in opposite directions:
M7 by `test_ingest_fails_when_nothing_was_ingested*` (`assert 0 == 1` — it
exited 0 and should not have) and M8 by
`test_ingest_reports_partial_failure_and_still_succeeds` (it exited 1 and should
not have). Neither test passes under the other mutant, which is what makes them
a pair rather than one rule written twice.

**My own sweep:**

| # | Mutant | Result |
|---|---|---|
| S1 | `len(modes) > 1` → `== 2` (three modes slip through) | **KILLED** |
| S2 | `if not keys` → `if not keys and failures` (silent empty search exits 0) | **KILLED** |
| S3 | `--research` skips `_text()` | **KILLED** |
| S4 | episode id skips `_text()` in `video_ingest` | **KILLED** |
| S5 | outer `OSError` arm removed (unwritable episode dir) | **KILLED** |
| S6 | paste-read `OSError` arm removed (`--paste` on a directory) | **KILLED** |
| S7 | reports a fixed source count instead of the real one | **KILLED** |
| S8 | failure lines omit the URL | **KILLED** |
| S9 | `SeriesError` not caught (unknown `--series` tracebacks) | **KILLED** |
| M3b | only the `FileNotFoundError` arm removed | **SURVIVED — equivalent** |

**M3b is equivalent, not a gap.** With the specific arm gone, the generic
`OSError` arm produces `cannot read --paste …/nope.md: [Errno 2] No such file or
directory` — same exit code, same filename, and it still contains the phrase
"no such file". There is no assertion an operator would care about that separates
them. The specific arm is redundant; I left it because the wording is slightly
better, but it is dead weight and worth knowing.

### What the sweep found in my own tests

Four things, all fixed in cad0230, and the first is the serious one:

1. **The no-network guarantee held only while the implementation was correct.**
   Deleting the two-mode guard (M1) made
   `test_ingest_refuses_two_input_modes` fall into the `--research` branch and
   call the *real* `ingest_research`. The first sweep did not report M1 — it
   **hung**, twice, for ten minutes, on a live fetch to startpage.com. "Patch at
   the module boundary" cannot be satisfied test-by-test on the tests that
   happen to exercise that boundary today; it has to be the default for the
   module. `prepared` now depends on a `no_network` fixture that patches
   `ingest.ingest_research` for every test, which individual tests override.
2. **`assert "3" in result.output` asserted nothing** — the output contains a
   tmp path with digits in it. S7 (hardcode the count to 1) survived on it.
   Now `assert "3 source" in result.output`. The brief's supplied
   `assert "1" in result.output` has the same defect and is worse: the episode
   id `2026-08-17` contains a `1`, so that assertion is true no matter what the
   command prints. I dropped it and assert the failed URL and reason instead.
3. **`assert "adir" in result.output`** passed on a message that said
   `cannot write the corpus` when it was the *read* that failed (S6). Added
   `assert "read" in result.output.lower()`.
4. Two of my own assertions were simply wrong (593bec4):
   `not (prepared / "sources").exists()` — `video new` already creates that
   directory, so it asserted something the fixture had falsified. What the
   two-mode tests mean is that no document was written; they assert that now.

I also had one **invalid mutant**: S4's pattern
(`episode = _text(episode, "The episode id")`) occurs in `video_new` too, and
`replace(…, 1)` mutated the wrong function. It "survived" because the fixture
passes `video new` a valid id. Re-anchored to `video_ingest` and it dies. A
mutant that mutates the wrong code is indistinguishable from a test gap in the
output, which is its own small lesson.

## 4. Step 6 — real end-to-end, no stubs

```
$ export AGSOC_WORKSPACE=/tmp/ing/workspace && rm -rf /tmp/ing
$ uv run agsoc init /tmp/ing/workspace && uv run agsoc series new the-brief --name "The Brief"
workspace ready at /tmp/ing/workspace/
next: edit voice.md (your voice profile) and config.toml (X client_id)
created series the-brief at /tmp/ing/workspace/series/the-brief/
next: edit /tmp/ing/workspace/series/the-brief/series.toml (palette, byline, acts, runtime)

$ uv run agsoc video new 2026-08-17 --series the-brief
created episode the-brief/2026-08-17 at /tmp/ing/workspace/series/the-brief/episodes/2026-08-17/
next: agsoc video ingest 2026-08-17 --research "<query>"

$ printf 'Gemini 3.7 Flash costs $0.75 per 1M input tokens.\nDeepSeek raised prices by 1,100%%.\n' > /tmp/ing/paste.md
$ uv run agsoc video ingest 2026-08-17 --series the-brief --paste /tmp/ing/paste.md
ingested 1 source(s), 0 failed → /tmp/ing/workspace/series/the-brief/episodes/2026-08-17/brief.md
next: draft beats into /tmp/ing/workspace/series/the-brief/episodes/2026-08-17/script.yaml

--- corpus ---
_manifest.json
_pasted.txt

--- manifest ---
{
  "_pasted": {
    "bytes": 84,
    "fetched_at": "2026-08-17T14:24:25-05:00",
    "sha256": "af1c0453ae81ef1a569a3349b6c90b4ba2ff066cfd28fd1c2547b3036b70e985",
    "title": "pasted digest",
    "url": ""
  }
}

--- brief ---
# Brief

_Query: (pasted) · ingested 2026-08-17T14:24:25-05:00_

## Sources in the corpus

- `_pasted` — pasted digest
  (pasted)
```

## 5. Files changed and commits

| SHA | Commit |
|---|---|
| `7c10925` | fix: regenerate the brief from the manifest, bound source keys |
| `0e06099` | test: specify agsoc video ingest and its error surface |
| `593bec4` | test: fix two of my own assertions, not the implementation |
| `f7a018d` | feat: add agsoc video ingest |
| `cad0230` | test: close four gaps the mutation sweep found in these tests |

- `src/agenticsocial/video/ingest.py` — `_brief` reads the manifest; `src-` keys bounded
- `src/agenticsocial/video/cli.py` — `video_ingest`, plus `Path` and `ingest_mod` imports
- `tests/test_video_ingest.py` — 3 tests added/extended (16 total)
- `tests/test_video_cli.py` — 23 tests added (52 total)

Nothing under `docs/` staged. `git status --porcelain -- src tests` clean.
Final suite: **469 passed**.

## 6. Issues and concerns

### 6.1 Anything an operator can type that still tracebacks

Nothing I could find, and I looked past the mutant table for it. Covered by
tests: zero/two/three modes, missing paste, non-UTF-8 paste, a *directory* as
paste, unwritable episode dir, unknown/ambiguous source id, unknown episode,
unknown series, undecodable `--research`, undecodable episode id. `run()` uses
`catch_exceptions=False`, so any of these tracebacking fails the test rather
than looking like a clean exit.

Three residual notes, none of them tracebacks:

- **`--from-source` can still produce a >64-char key.** 0d bounds
  `f"src-{id}"[:64]`, but `write_document` appends `-2` on a collision *after*
  the truncation, so ingesting two long-titled sources whose ids share their
  first 60 characters yields a 66-char key. The cap is on the input, not on the
  key that reaches disk. Not exploitable into an error today (NAME_MAX is 255);
  flagging it because 0d was written as if the cap were a guarantee.
- **`--paste` on an unreadable file** (mode 000) is covered by the same
  `OSError` arm as the directory case, but no test pins it separately.
- **A `--research` query is not length-bounded**, unlike series and episode
  names. It only ever reaches `brief.md` as text, so the worst case is an ugly
  brief.

### 6.2 Is the failure surface right when there is no connection at all?

Yes, and better than I expected. Run for real against a dead proxy:

```
$ uv run agsoc video ingest 2026-08-17 --series the-brief --research "gemini 3.7 pricing"
search failed: ConnectError: ConnectError('error sending request for url (https://www.startpage.com/) > client error (Connect) > tunnel error: failed to create underlying connection > tcp connect error > Connection refused (os error 61)') — check your connection and retry
EXIT=1
```

Exit 1, no traceback, and the actionable half of the message ("check your
connection and retry") is there. Two observations:

- **The wrapped exception text is long and leads with the noise.** The operator
  reads four nested clauses of transport detail before the sentence that tells
  them what to do. `ingest_research`'s `f"search failed: {e}"` passes the
  provider's error through verbatim. It is *correct* — it names the search host,
  which is genuinely useful — but the useful sentence should come first.
- **The pre-existing brief was not clobbered**, which is the 0b fix paying off
  from the other side: `ingest_research` raises before `_brief` runs, so a failed
  research run leaves the previous corpus record intact. I verified this on the
  real workspace — `brief.md` still showed the `_pasted` source afterwards.

### 6.3 Did this brief's tests read as derived-from-mutants or as transcriptions?

Mostly derived, with two that I would call transcriptions — and I have direct
evidence for the claim rather than an impression, because the sweep tested it.

**Derived:** the M7/M8 pair. They cannot both be satisfied by one rule; writing
them forces you to decide what "success" means, and the brief's prose about
partial failure is doing real work there.

**Transcriptions:** `assert "1" in result.output` in the partial-failure test and
`assert "one" in result.output.lower()` in the two-mode test. Both are assertions
about a *string the brief already knows the implementation prints*. The first is
provably vacuous — `2026-08-17` contains a `1`, so it passes against any output
at all, including no output. That is exactly the artefact you would predict from
writing assertions with the implementation visible: it looks like it checks the
count because the author knew the count was there.

**On whether sealing Step 3 would have changed how I wrote them: I cannot claim
it, because the seal did not hold** (§0). What I can say is narrower and more
useful. The pressure the previous implementer described is real, but the four
defects the sweep found in my tests were not agreement-with-implementation
defects — they were *weak assertions* (`"3"` matching a path digit, `"adir"`
matching the wrong error, a fixture that had already created the directory I
asserted absent). Those survive any amount of sealing, because they are wrong
against a correct implementation too. Sealing prevents transcription; it does not
prevent vacuity.

What actually caught all four was running the mutants. I would suggest the
ordering rule stay, but that the report metric stay the mutation score and that
*the sweep be treated as mandatory before the implementation commit is believed*
— because the most alarming thing this task turned up was not a weak assertion
at all. It was that my test suite reached the live network the moment the code
under test was wrong, and hung instead of failing. No amount of reading my tests
would have shown me that. Only breaking the implementation did.
