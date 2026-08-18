# Task 4 Brief: the extractor fails open — close it

**Phase:** 5 · **Branch:** `feat/video-phase-05-verifier` · **Follows:** `57b9e2f`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

The blind gate found two ways to display a fabricated number and pass. I
reproduced both before writing this. **Phase 5 does not merge until they close.**

## F1 — an unparseable numeric token is silently exempt

```
atoms('about 95B active')   -> (number '95', entity '95B')
atoms('about 950bn active') -> ()          <- nothing. no atom, no check.
```

§8.2.2 strips exactly one trailing suffix character, so `950bn` fails the
digits-only test, is classified an identifier, is *also* rejected as a name (no
capital), and **yields no atom at all.** Verified end to end by the reviewer on
your own episode: `about 95B active` → `about 950bn active`, source unchanged,
and `check` prints `c-005 beat 4 list pass`. **A 10× fabrication, verified clean.**

This is exactly the "`95B` against a source saying `9B`" case §8.2.2 was written
to prevent, arriving through the spelling the rule does not know.

Same root cause silently exempts `1e9`, `3/4`, `0-70`, `12:30` and non-ASCII
digits.

**Aggravating: `verify.py:233-234` asserts the opposite as fact** — *"'bn' and
'mn' … a beat using them is refused rather than guessed at."* It is not refused.
A comment that states a guarantee the code does not provide is worse than no
comment, because it stops the next reader from checking.

## F2 — the sign is discarded before comparison

```
_bare('-18') -> '18'
'-18' matches 'Revenue rose 18%'?  True
```

`-` is `Pd` and U+2212 is `Sm`, so both are stripped as "decoration". **A beat
saying revenue fell 18% verifies against a source saying it rose 18%** — a
reversal of meaning, passing.

§8.2.1's safety argument ("no digit is ever folded") does not cover this: the
loss happens in `_bare`, *before* folding. **The argument was sound and its scope
was wrong**, which is worth more attention than the bug.

## The design rule this task establishes

Both defects are one decision made wrongly, in two places: **a token the rule
cannot parse is currently treated as "not a claim" instead of "cannot be
checked".** That is failing open, in the one component whose entire job is to
notice.

**Invert it. A token that looks numeric and cannot be parsed must refuse, not be
exempted.** "I do not understand this figure" and "this figure is fine" must
never produce the same verdict — the operator can act on the first and is misled
by the second.

Design the boundary between "looks numeric" and "is an identifier" and defend it:
`V4-Pro` must stay exempt (D-071, non-negotiable — it is the false-refusal rule
validated twice on real prose), while `950bn`, `1e9` and `3/4` must not pass
unchecked. **If you cannot make a case decidable, refuse it and say so** — a
named refusal is a fixable problem, a silent exemption is not.

## Rules, each with its negative half

- **R1** A numeric-looking token the rule cannot parse **refuses**, naming the
  token. **Negative:** `V4-Pro`, `Qwen3.8-Max`, `GPT-5.6` stay exempt.
- **R2** Two-letter magnitudes (`bn`, `mn`, `bps`, `tn`) are handled — parsed or
  refused, your call, argued. **Negative:** whatever you choose, `950bn` cannot
  pass against a source saying `95B`.
- **R3** Sign is significant. `-18` does not match `18`. **Negative:** a hyphen
  that is punctuation, not a sign (`the 18% figure`, `2010-2011`), still folds
  as before — do not break D-071.
- **R4** Comments state what the code does. **Negative:** fix `verify.py:233-234`
  and sweep for others claiming guarantees that do not exist.
- **R5** Every fix is reachable from `agsoc video check` on a real episode, not
  only from a unit test.

## The mutants this task must kill

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | `950bn` yields no atom | R1 |
| M2 | `950bn` parsed but as `950` | R2 |
| M3 | `V4-Pro` now demands its `4` | R1 negative — **false refusals return** |
| M4 | `1e9` / `3/4` / `12:30` silently exempt | R1 |
| M5 | non-ASCII digits silently exempt | R1 |
| M6 | `-18` matches `18` | R3 |
| M7 | `2010-2011` or `the 18% figure` refused | R3 negative |
| M8 | refusal names no token | R1 |
| M9 | unparseable refused in `claims.py` but not visible in `check` | R5 |

## Ride-alongs from the same review

- **F3 (before Phase 7).** `verify.stale_reason`'s docstring promises `approve`
  an answer it does not give: edit a figure in `script.yaml` and it returns
  `None`. The script half exists only as `_script_drift`, a display helper in
  `cli.py`. Not live today; **a loaded gun for Phase 7's gate.** Either move it
  behind `stale_reason` or correct the docstring — decide and say which.
- **F4 (test debt).** **D-081's `shown` guarantee has no test that can fail** —
  deleting the `shown` extraction survives all 1524 tests. The covering test
  asserts markup absence (true when nothing is appended) and figures
  `before`/`after` produce anyway. Textbook D-035. Add the symmetric test.
- **F5.** Four more prose guarantees with no test behind them: kpi `prefix`, kpi
  `unit`, the edge-elision rule, unparseable-number-fails.
- **F6.** Record as accepted risk, do not fix: unit blindness (`50%` = `$50`),
  European separators (`1,5` → 15), act labels.

## Ground rules

- **Commits: tests first, then implementation.** Do not squash.
- **`PYTHONDONTWRITEBYTECODE=1` in any mutation sweep** (D-100).
- **Never quote a piped exit code** — `cmd | head` reports `head`'s status. It
  produced a false reading twice in this phase, for two different actors (D-105).
- **Pipe command output to a file and paste from it.**
- Code blocks and spec tables are authoritative; if they disagree with prose,
  follow the code and **flag it** — 24 brief defects, zero implementer errors.
- **If `workspace/` is modified, back it up first and restore it.** It is the
  operator's own content and is not version controlled.
- No new dependencies, no network, no LLM.
- **Report the mutation score.**

---

- [ ] **Step 1** — tests from the mutant table, including the two reproductions
      above. Failing. Commit.
- [ ] **Step 2** — F1. Commit.
- [ ] **Step 3** — F2. Commit.
- [ ] **Step 4** — the ride-alongs, F4 especially. Commit.
- [ ] **Step 5** — mutants plus your own sweep.
- [ ] **Step 6 — re-run the real episode.** `check` and `review` on
      `the-brief/2026-08-17`. It must still verify clean, and **`950bn` against a
      source saying `95B` must now fail.** Paste both, and paste the
      false-refusal count on the operator's brief — if the fix costs false
      refusals, that number is the cost and I want it stated, not discovered.

---

## Your report

`docs/superpowers/worklog/video/phase-05/task-4-report.md`:

1. **Where you drew the numeric/identifier boundary**, and why it is defensible.
2. **The two reproductions, before and after**, pasted.
3. **TDD evidence**, the **mutation score**, all nine mutants plus your sweep.
4. **Step 6's screens and the false-refusal count.**
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **What numeric spelling still slips through?** Try harder than the brief
     did — the gate found `bn` because it looked; assume there is another.
   - Did closing F1 raise the false-refusal rate, and by how much?
   - Any other comment in the codebase claiming a guarantee the code lacks.
