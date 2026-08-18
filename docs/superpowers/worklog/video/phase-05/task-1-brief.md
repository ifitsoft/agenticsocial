# Task 1 Brief: Claim extraction — deciding what a beat actually asserts

**Phase:** 5 · **Branch:** `feat/video-phase-05-verifier`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`
**Spec:** §8.1 (the record), §8.2.1 (folding), §8.2.2 (claim numbers)

## The sentence this phase makes true

A Phase 4 implementer wrote it plainly, and it is still true today:

> **Nothing anywhere yet checks that a `value` appears in its `quote`.** The
> schema only checks the quote exists.

Phase 2 built the corpus. Phase 3 gave beats `src` and `quote`. Phase 4 made the
rendered bytes equal the verified bytes. This phase closes the loop. **Your task
is the front half: turning a `Script` into claim records.** Task 2 does the
matching, Task 3 the command.

## Why extraction is the hard half

**Extraction is where the false-refusal rate is set.** Too greedy and every
product name becomes a claim the operator must override; too shy and a figure
ships unchecked. D-040's failure mode is a gate that cries wolf until operators
override reflexively — at which point the gate is theatre and the product's
differentiator is gone.

The two rules that prevent this are **already settled** (D-071, spec §8.2.1 and
§8.2.2). Both were found by running a real operator brief through the pipeline
before Phase 5 existed. **Implement them; do not re-litigate them.** If you
believe one is wrong, say so in the report — do not quietly deviate.

## The trap I want you to look for first

`claims.py` must decide **what text a beat renders**. `planbuild.js` already
decided that, in JavaScript, when it built the DOM. **These are two independent
answers to the same question, and nothing makes them agree.**

If Python thinks a `list` beat renders only `lead` while `planbuild.js` renders
`lead` *and* every item, then figures inside `items` are never extracted, never
checked, and ship. `agsoc video check` says pass. The gate is green and wrong.

So: **derive the prose-bearing fields from the catalogue, not from a hand-written
list.** A hand-written list is correct exactly until §7.1 gains a field — and
D-086 records that the catalogue is closed *today*, not forever. Make the
divergence a test failure rather than a silent gap; the shape of that test is
your call, but "a type gains a text field and extraction ignores it" must not
pass. Say in your report what you chose and what it does and does not catch.

Note `title` and `signoff` are **exempt** (§8.2), and `custom` is always `manual`
— its rendered content cannot be statically extracted, which is exactly why D-088
requires `attest`.

## One thing the settled rule does not decide — decide it, do not default

I ran §8.2.2's rule over the real brief before writing this. It produced 18 claim
numbers, and two of them are worth your judgement:

```
'3.7', '1,100%,', '60"', '1.6T', '16', '$1.32', '$3.96', '1M', '2.4',
'95B', '27.8B', '2.0', '14,', '2026,', '98%', '12', '12', '200'
```

`2026` is a **year** and `14` is a **list ordinal**. Both are digits-only, so the
rule makes them claim numbers that must appear in the quote. A year often will
appear; an ordinal from the brief's own numbering will not.

This is the false-refusal end of D-040 arriving in a place the spec did not look.
**Decide it explicitly and say why in the report.** Both answers are defensible —
a date presented as current is a real failure mode §8.3 names, so exempting years
has a cost. What is not acceptable is discovering it at Step 4 and quietly
special-casing it.

## Rules, each with its negative half

- **R1** Every claim number in a beat's rendered text becomes an atom of kind
  `number`. **Negative:** digits *glued to letters* do not — `V4-Pro`,
  `Qwen3.8-Max` and `GPT-5.6` are identifiers.
- **R2** A trailing unit suffix (`%KMBTx`) and a leading currency symbol are
  stripped before the digits-only test. **Negative:** `1M` and `95B` are
  therefore **claim numbers, not identifiers.** A naive "any letters means
  identifier" rule was drafted first and got this backwards, which would let a
  beat claim `95B active` against a source saying `9B`.
- **R3** A standalone number is checked even when it sits beside a product name.
  **Negative:** in `Gemini 3.7 Flash` the token `3.7` stands alone and **is** an
  atom — a beat saying 3.7 when the source says 3.6 is the error this pass
  exists to catch.
- **R4** Folding is applied to the **comparison only**. **Negative:** the corpus
  bytes, the `quote` bytes, and every `sha256` are untouched. Normalising on disk
  breaks §4's integrity guarantee.
- **R5** The fold table is explicit (§8.2.1). **Negative:** `unicodedata.
  normalize("NFKC", …)` is **not** a substitute — U+2011 is not a compatibility
  variant and survives NFKC unchanged. Verified. A test must pin this, or the
  next reader will "simplify" the table away.
- **R6** No digit is ever folded. **Negative:** this is what makes folding safe —
  it can turn a false refusal into a pass, never a false claim into a verified
  one. Assert it over the whole table rather than trusting it.
- **R7** Every record names the **beat index and type** and a claim id.
  **Negative:** a claim with no `src` still produces a record — it is Task 2's
  `no_source`, not a silent omission here.

## The mutants this task must kill

Derive your assertions from this table, **before** writing the implementation
(D-064: assertions written after the code transcribe the code).

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | any token containing a letter treated as an identifier | R2 (`1M`, `95B` slip) |
| M2 | unit suffix stripped from the *front* as well, so `M1` becomes a number | R2 negative |
| M3 | `3.7` in `Gemini 3.7 Flash` exempted as part of a name | R3 |
| M4 | `V4-Pro`'s `4` extracted as a claim number | R1 negative |
| M5 | fold table replaced by `NFKC` | R5 |
| M6 | U+2011 dropped from the hyphen row | R5 |
| M7 | digits added to the fold table (e.g. a full-width digit folding to ASCII) | R6 |
| M8 | folding written back to the corpus / quote on disk | R4 |
| M9 | a prose field of some type omitted from extraction | the §7.1 trap above |
| M10 | `title`/`signoff` extracted as claims | §8.2 exemption |
| M11 | `custom` extracted rather than marked for `manual` | D-088 |
| M12 | beat index or claim id missing from a record | R7 |
| M13 | a beat with no `src` silently produces no record | R7 negative |

## Ground rules

- **Two commits.** Tests first, then the implementation. Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks and the spec tables are authoritative; prose explains *why*. If
  they disagree, follow the code block **and flag it** — 23 brief defects across
  five phases, against zero implementer errors. Finding one is a contribution.
- **No new dependencies. No LLM calls. No network** — `tests/conftest.py` guards
  sockets *and* the `research` seam (D-067: you cannot guard a boundary you do
  not own).
- `script.yaml` is never written by this phase.
- **Include falsy and empty values.** `0` is a legitimate figure and an empty
  atom list is a legitimate outcome; a truthiness check is a live bug here.
- **State a `precondition:` per test** — what must be true for the test to be
  capable of failing. D-035: a test whose own harness performs the transformation
  under test cannot fail. Ask of each test: *what would this do if the code did
  nothing?*
- **Report the mutation score.**

---

- [ ] **Step 1** — tests derived from the mutant table. They must fail. Commit.
- [ ] **Step 2** — `src/agenticsocial/video/claims.py`: the fold, the claim-number
      rule, and extraction producing the §8.1 record shape (`id`, `beat_index`,
      `beat_type`, `text`, `src`, `quote`, `atoms`). Commit.
- [ ] **Step 3** — the mutants, plus your own sweep.
- [ ] **Step 4 — the real brief.** `workspace/inbox/2026-08-17-ai-brief.md` is a
      real operator brief and the regression fixture for D-071. Run your
      extractor over text taken from it and **paste the atoms it produced**. I
      want to see which tokens became claim numbers and which did not, on real
      prose with real typographic punctuation — not on synthetic fixtures, which
      contain neither non-breaking hyphens nor product names.

---

## Your report

`docs/superpowers/worklog/video/phase-05/task-1-report.md`:

1. **What I implemented**, and which decisions were mine rather than the spec's.
2. **How you tied extraction to the catalogue**, and what that does *not* catch.
3. **TDD evidence** and the **mutation score**.
4. **All thirteen mutants** plus your own sweep.
5. **Step 4's atoms**, pasted.
6. **Files changed**, all commit SHAs.
7. **Issues or concerns**, including:
   - **Where is the false-refusal rate now?** Name a realistic beat this
     extractor would refuse wrongly. If you cannot find one, say what you tried
     — that is a stronger result than asserting there are none.
   - **Entity atoms (§8.2 step 3) are the shakiest part of the spec.** "Every
     proper noun" has no mechanical definition without an NLP dependency, and we
     have none. Say what you did, and be honest about its error rate in both
     directions rather than what is comfortable.
   - Anything a beat can render that this extractor cannot see.
