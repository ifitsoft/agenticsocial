# Task 3 Report: the coverage check no longer clears what it should catch

**Phase:** 6 · **Branch:** `feat/video-phase-06-storyboard`
**Baseline:** 1611 tests · **Now:** 1612 pytest + 3 node suites, all green.

The defect is fixed at the matcher and at the message, `coverage.mjs` has a
test file where it had none, and the six skill statements the second blind run
falsified are corrected. 21 of 21 mutants killed.

---

## 1. The matching rule, and what it costs

**The rule: strip every non-alphanumeric character from both the term and the
story, then ask whether the ledger contains the term.**

```js
const squashed = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '');
const matches = (story, term) => {
  const t = squashed(term);
  if (!t) return false;                       // nothing matches nothing
  return squashed(haystack(story)).includes(t);
};
```

Four spellings of the same product now converge on one query — the author's
`gemini-3.7`, the ledger's `Gemini 3.7 Flash`, the id's `gemini-3-7-flash`, and
`gemini3.7`, which somebody will type. All four become `gemini37…`.

**Why not tokenise.** Tokenising and matching on whole tokens fixes
`gemini-3.7` and breaks `watermark` → *watermarking* and `llm` → *LiteLLM*,
both of which the old substring match found. In a check whose dangerous failure
is the miss, trading one silent miss for two others is not a fix. Containment
is kept; only the alphabet narrows. The change is therefore **one-directional**:
every match the old code found this one finds too, so nothing that used to warn
has gone quiet. That is the property that matters, and it is why the fix could
be made without re-auditing the two shipped episodes.

**I first shipped two normalisations** — separators collapsed to a space,
separators removed, hit on either — and the mutation sweep flagged the
collapse-to-a-space pass as a survivor. It was an *equivalent* mutant: brute
forcing every word in the ledger plus this task's terms found **0 cases where
the spaced pass hits and the squashed pass does not**. It was dead code reading
as defence in depth, so `d2eb2f7` deleted it. `spaced` survives only as the
tokeniser for the "related" pointer.

**The false-positive cost.** Stripping separators lets a term join across a word
boundary. Measured on the real ledger:

```
node coverage.mjs check aiact
  "aiact"  — 1 prior mention(s):
     2026-08-12  [anthropic-claude-watermarking]  launch
       Anthropic adds invisible watermarks to Claude text and C2PA metadata to files
```

`aiact` finds *EU AI Act*. Nobody writes `aiact`, but the class is real, and
short terms were always over-hitting anyway (`gemini` returns every Google
story the series ever ran — that is documented behaviour, not a regression).
The cost of a false positive is ten seconds spent reading a title that turns
out to be unrelated. The cost of a false negative was the series' one rule. I
took the trade deliberately and said so in the code comment.

**The message.** A miss no longer says *NOT COVERED. Safe to run as new.* — a
claim about the world that a string search cannot support (D-106's class). It
now names what was searched, states the bound on what absence proves, and, when
a word of the term is already in the ledger, points at those entries **without
counting them as hits**. That pointer is the step the second blind runner had
to think of unaided; the tool knew it all along and did not say it.

A real hit is unchanged: same count, same titles, same instruction.

## 2. Before and after, on the real ledger

`engine/coverage.json` was **not modified** (`git status` clean throughout;
`diff` against the pre-task backup identical). Fixtures live in a temp file
reached through `AGSOC_COVERAGE_JSON`.

| term | before | after |
|---|---|---|
| `gemini-3.7` | `NOT COVERED. Safe to run as new.` | **3 prior mention(s)** — the three `Gemini 3.7 Flash` stories of 2026-08-14 |
| `gemini` | 4 prior mention(s) | 4 prior mention(s) — unchanged |
| `v4-pro` | `NOT COVERED. Safe to run as new.` | no entry matches this string (+ the bound) |
| `deepseek` | `NOT COVERED. Safe to run as new.` | no entry matches this string (+ the bound) |

Pasted, after:

```
$ node coverage.mjs check gemini-3.7

  "gemini-3.7"  — 3 prior mention(s):
     2026-08-14  [gemini-3-7-flash-specs]  analysis
       Gemini 3.7 Flash model card: 1,048,576-token input, 65,536 output, built-in tool use
     2026-08-14  [gemini-3-7-flash-github-copilot]  launch
       Gemini 3.7 Flash selectable in GitHub Copilot
       note: Enterprise admins must enable a preview policy first.
     2026-08-14  [gemini-3-7-flash]  launch
       Google launches Gemini 3.7 Flash — agentic workhorse at half the price
       note: $0.75/$3.75 per 1M tokens through 2026, doubling in 2027. Benchmarks charted: FrontierCode 1.1, DeepSWE v1.1, AutomationBench, GDP.pdf.

  → 3 hit(s). Cover these as updates (state what is new) or drop them.

$ node coverage.mjs check deepseek

  "deepseek"  — no entry matches this string.
     searched 18 stories across 2 episodes (id, title, note, entities, sources), separators ignored.
     That is all it proves. It does not mean the story is new: the ledger
     holds only what a person wrote into it after an episode shipped.

  → 0 matches in 18 stories across 2 episodes (id, title, note, entities, sources), separators ignored.
    Nothing in the ledger contains these strings. Whether the stories are
    new is a judgement this check cannot make for you.
```

And the pointer, on a term that is genuinely absent but shares a word with the
ledger — `check gemini-9.9`:

```
     Related, and not a hit: "gemini" appears in 4 story(ies). Run those terms and read the titles
     before you decide this story is a different one.
```

`v4-pro` prints no pointer: the only fragment it could offer was `pro`, which
matches *profiles* and *improve* and points at nothing. Fragments shorter than
four characters are suppressed — a pointer that is usually noise stops being a
pointer.

## 3. TDD evidence, and the mutation score

**Step 1, the failing test** (`7355f9f`), before a line of implementation:

```
$ node coverage.test.mjs
  FAIL gemini-3.7 is reported as already covered — "gemini-3.7"  — NOT COVERED. Safe to run as new.
  FAIL gemini-3.7 names the episode and the story it collides with
  FAIL gemini-3.7 never reads as permission
  ...
  FAIL a miss never says "safe"
  FAIL a miss states the limit of what absence proves
14 FAILURES
```

**Step 2, after the fix** (`f04b7be`): 27 assertions, 0 failures.
The CLI-hint half was the same shape: `851bda7` commits two failing tests —
one of them fails by *executing the hint's own bytes* and tripping the suite's
network guard — and `cde08aa` makes them pass.

Commits are tests-then-implementation throughout, and no skill change shares a
commit with a code change.

**Mutation score: 21 killed / 21 applied (100%).** Each mutant is applied to a
copy of the file, tested, and reverted; the sweeps are `/tmp/mutate.sh` and
`/tmp/mutate_py.sh`, and `PYTHONDONTWRITEBYTECODE=1` is set for the Python one.

`engine/coverage.mjs` — 17 mutants:

```
KILLED   M1 raw substring match (the original defect)
KILLED   M1b separators collapsed to a space instead of removed
KILLED   M1c only hyphens normalised
KILLED   M1d normalise the term but not the ledger
KILLED   M2 everything matches
KILLED   M2b empty-term guard removed
KILLED   M2c whole-token equality instead of containment
KILLED   M3 a miss still says safe
KILLED   M3b a miss stops explaining what it searched
KILLED   M3c a miss drops the bound on what absence proves
KILLED   M4 a hit softened into a maybe
KILLED   M4b the footer goes back to All clear
KILLED   M5 the related pointer is dropped
KILLED   M5b the related pointer is counted as a hit
KILLED   M6 the ledger override is ignored
KILLED   M7 an unknown episode exits 0
KILLED   M8 check with no terms exits 0
```

`src/agenticsocial/video/cli.py` — 4 mutants:

```
KILLED   P1 the hint goes back to --research alone
KILLED   P2 the other two ingest modes go unmentioned
KILLED   P3 --series drops out of the hint again (D-109)
KILLED   P4 the hint names two modes at once
```

**The one that got away first time round, honestly.** The initial sweep against
the two-normalisation implementation reported **15 killed / 17**, with
"spaced pass only" and "squashed pass only" surviving. One survivor was a real
gap in the tests (the `gemini3.7` spelling, now asserted in `9894c7b`); the
other was an equivalent mutant that proved half the matcher was dead. The 100%
above is the score *after* deleting the dead half and adding the missing
assertion — not the score I got on the first run.

**Not covered by any mutant: the skill.** The brief's M6 (beat arithmetic still
yields 19–27) and M7 (skill still vouches for the hint) are statements in a
markdown file, and nothing in this repo tests prose. They are verified by
reading, and by the arithmetic being written out in the skill itself so the next
reader can check it in one line: `2 + 4×5 + 1 = 23`, `2 + 4×6 + 1 = 27`. See §6.

## 4. All three episodes

`workspace/` was copied to `/tmp/workspace-backup-task3` before anything ran,
and all three episodes are present and untouched apart from the `claims.json`
each `check` rewrites identically (`diff -rq` against the backup: identical).

```
=== 2026-08-17    exit=0    7 claims verified, none open
                            holds 37.5s × pace 1.0 = runtime 37.5s
                            target 120s ± 8s · OUT OF TOLERANCE (-82.5s)
=== 2026-08-17b   exit=0    22 claims verified, none open
                            holds 91.6s × pace 1.31 = runtime 120.0s
                            target 120s ± 8s · within tolerance (-0.0s)
=== 2026-08-17c   exit=0    24 claims verified, none open
                            holds 90.4s × pace 1.327 = runtime 120.0s
                            target 120s ± 8s · within tolerance (-0.0s)
```

All three exit 0. `2026-08-17` is out of runtime tolerance and was before this
task — its `pace` is still `1.0`; it is the scaffolded first episode, not a
blind run's output, and `check`'s exit code has never included the runtime
line.

Everything else, run at the end:

```
uv run pytest -q                    1612 passed, 1 warning in 13.38s      exit 0
node determinism.test.mjs           deterministic                          exit 0
node network.test.mjs               no request escapes the page            exit 0
node coverage.test.mjs              the ledger check cannot be talked past exit 0
```

`git status --porcelain -- src tests skills engine` prints nothing.

## 5. Files changed, and the commits

| File | What |
|---|---|
| `engine/coverage.test.mjs` | **new** — 27 assertions, plain node, no dependency |
| `engine/coverage.mjs` | the matcher, the miss message, the related pointer, `AGSOC_COVERAGE_JSON` |
| `src/agenticsocial/video/cli.py` | `video new`'s `next:` hint |
| `tests/test_video_cli.py` | one new hint test; one existing test rewritten |
| `skills/storyboard/SKILL.md` | seven corrections |

```
7355f9f  test: pin that a hyphenated term finds a spaced ledger entry
f04b7be  fix: match the ledger past separators, and stop saying "safe"
851bda7  test: pin the ingest mode `video new` points an author at
cde08aa  fix: `video new` points at --paste, and names the other two modes
e6dc74b  docs(skill): the arithmetic, the hint, and one script instead of 24 steps
9894c7b  test: pin the spelling with no separator at all
d2eb2f7  refactor: one normalisation, not two dressed as a second opinion
```

### What changed in the skill

1. **The arithmetic reconciles.** 22–26 with acts of 4–6 yielded 19–27 and
   matched at neither end. Now **23–27 beats = 2 cold-open + 4 acts of 5–6 + 1
   signoff**, written as the sum. It also agrees with the 80–95s hold band (23
   beats × 3.5s = 80s, 27 × 3.5s = 95s) and contains both committed episodes
   (24 and 25 beats).
2. **The coverage section** no longer quotes the deleted sentence, describes
   separator-insensitive matching, and states what a miss does and does not
   prove — with the `gemini-3.7` incident named, because the sentence that
   cleared the story is the reason the rule exists.
3. **Quote extraction scales.** Step 3.5 prescribed one `index()`+`repr()` round
   trip *per quote*; both blind runners wrote a script instead, and that script
   is what made both first checks green. The script is now in the skill: a list
   of `(src key, anchor)` pairs, every span printed in one pass, `find` rather
   than `index` so one retyped anchor reports itself instead of stopping the
   run. **Verified by running it** against `2026-08-17`'s real corpus, both with
   a good anchor and a deliberately bad one.
4. **Step 8.5 no longer vouches for the hint** and describes it as it now is.
5. **The episode-id date is the brief's, not the clock's** — stated, with the
   midnight-crossing case called out.
6. **`title.sub` and `signoff.text`** are exempt from the checker, not from the
   rule. *Five stories from the last 24 hours* is a sentence a viewer reads and
   nobody downstream verifies it.
7. **A gap in the claim ids is not a lost claim** — the id is the one-based beat
   number (`claims.py:656`), and exempt beats consume their number by design so
   `c-008` is always the eighth row of `review`.

### Why the CLI hint moved rather than the doc

The brief offered either. I fixed the CLI, because the hint is a command people
run and `--research` is both the wrong mode for the documented workflow (the
brief is already a file) and the only mode that reaches the network. It now
reads:

```
next: agsoc video ingest 2026-08-17 --series the-brief --paste <file>
      exactly one ingest mode: --paste <file>, --research "<query>", or --from-source <id>
```

The pre-existing test that *executes* the hint got stronger as a side effect: it
used to swap `--research` for `--paste` to stay offline, and now substitutes only
the `<file>` placeholder — the flag comes from the hint's own bytes.

## 6. Issues and concerns

### A third thing that says more than it knows

`agsoc video check`'s final line, printed in green:

```
demo/ep1 · 2 claims · 1 pass · 1 manual

    c-001   beat  0  statement  pass
    c-002   beat  1  custom     manual

  attested by hand — no machine checked these (D-088), you are approving the sentence:
    c-002    “Draws the words "anything at all" and nothing else. - Ali Abdukarim”

2 claims verified, none open
```

Reproduced just now on a throwaway workspace, not reasoned about. The tool says
*no machine checked these* about `c-002` and then counts it among **2 claims
verified**. `is_blocking` (`cli.py:290`) correctly treats an attested `manual`
as non-blocking, and the tally above is honest — but the last line is the one an
operator reads as the verdict, and "verified" is exactly the word that claim
cannot carry. Same class as the coverage message and the `verify.py` comment
(D-106): the detail is right and the summary rounds it up.

The honest line is `1 verified · 1 attested by hand · none open` — the summary
should not use one word for two different kinds of assurance. I did not change
it: it is outside this task's scope and it sits directly in front of the Phase 7
approval gate, so it wants its own test and its own commit rather than a
drive-by.

Two smaller ones in the same family, both flagged and neither fixed:

- **`agsoc init` ignores `AGSOC_WORKSPACE`.** Every other command resolves the
  workspace through `Workspace.locate()`, which reads the env var; `init` takes
  a positional path defaulting to `workspace`. So `AGSOC_WORKSPACE=/tmp/x agsoc
  init` scaffolds `./workspace` and then every subsequent command says *no
  workspace at /tmp/x*. I hit this while building the reproduction above, from
  the repo root, with the operator's real `workspace/` one directory away.
  `Workspace.init` turned out to be idempotent and the backup diff confirms
  nothing was touched — but the near miss is the report, not the outcome.
- **`check` prints OUT OF TOLERANCE and exits 0.** Known and documented in the
  skill, and `2026-08-17` demonstrates it live (37.5s against a 120s target,
  exit 0, green summary). Deliberate — the runtime is not a claim — but it means
  the green line can sit under a red one.

### Smaller notes

- **The ledger still has no writer.** `coverage.mjs` can only read; there is no
  `add`, so "cover it as an update" cannot be recorded, and the miss message now
  says out loud that absence from the ledger is bounded by a human remembering
  to write in it. Whatever `agsoc coverage check` becomes should ship with the
  write path, or the check will keep getting more careful about a record that
  keeps getting less complete.
- **The `related` threshold is a judgement call.** Four characters, chosen
  because `pro` out of `v4-pro` pointed at *profiles* and *improve*. It is a
  heuristic and it is documented as one in the code.
- **CLAUDE.md's `engine/` tracked-file list** names `coverage.mjs` but no test
  files, though `determinism.test.mjs` and `network.test.mjs` are both tracked
  and `coverage.test.mjs` now joins them. Not touched — it is a doc line outside
  this task — but the list is now three files short of the truth.
- **Nothing tests the skill.** M6 and M7 are prose, and the only defence against
  a skill sentence drifting from the code is a person re-reading both. This task
  fixed six such sentences; the second blind run found them because a fresh
  reader followed them literally. That is currently the only detector there is.
