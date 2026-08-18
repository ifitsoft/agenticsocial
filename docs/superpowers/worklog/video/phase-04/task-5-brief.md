# Task 5 Brief: `shown` is an unattested arbitrary-JS surface — close it

**Phase:** 4 · **Branch:** `feat/video-phase-04-engine` · **Follows:** `e3f9830`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

The blind gate review found this and I reproduced it before writing this brief.
**Phase 4 does not merge until it is closed.**

## What is true

`jumpChart.rows[].shown` is the documented innerHTML exemption (D-078). But
innerHTML does not only grant *tags* — it grants **inline event handlers**. A
plain `jumpChart` beat, no `custom`, no `attest`:

```
shown: '<img src=x onerror="…">'
```

Leader-verified in a real browser. The handler runs. And it defeats the one
invariant this project has never had to re-fix:

```
load 1, frame t=1.0 : THE BRIEF|T1787015967789
load 2, frame t=1.0 : THE BRIEF|T1787015970251
*** NOT REPRODUCIBLE: same t, same plan, different frame ***
```

Three aggravating facts:

- `script.py`'s `NONDETERMINISTIC` lint only ever inspects `custom.js`. It never
  sees `shown`.
- `custom` at least demands `attest` (D-088). **`shown` demands nothing** — a
  `cited: True` type carries executable content with no attestation at all.
- `beat_summary` shows the approver only the row label. **The field never
  reaches the review screen**, so no human is reading it either.

That is three independent controls — lint, attestation, human review — and
`shown` is outside all of them, on the type spec §7.2 calls strictly verifiable.

**One thing the review reported that I could not reproduce:** it claimed
exfiltration succeeded. It does **not**. My run: `server hits: []`, with
`Content-Security-Policy refused … (connect-src)`. Task 4's policy blocks the
network half — it caught a vector that did not exist when it was written, which
is the strongest argument for it in the record. **Do not fix a leak that is
already closed**; fix execution and determinism.

## Why the fix is a closed vocabulary, not a blocklist

`2026-08-14.js` relies on `shown: '<s>34.4</s> &rarr; 43.6'` — strikethrough and
a named entity. That is the *entire* real requirement, from the only real
episodes that exist.

D-080 settled the shape of this problem once already for prose: **the markup
surface a script can reach must be closed, because a `script.yaml` is written by
an agent against a fetched source.** `shown` is the same threat with the same
answer. A blocklist of `onerror`/`onload`/`<script>` is the wrong shape — it is
the `window['Ma'+'th']` situation from D-088, a lint sold as a boundary.

Allow a small closed set of tags with **no attributes at all**, plus named
entities; escape everything else. Attribute-free is what makes it safe — every
event handler is an attribute. Derive the tag set from what the committed
episodes actually use; if you need a tag they do not use, flag it rather than
adding it quietly.

## Rules, each with its negative half

- **R1** `shown` cannot execute JavaScript. **Negative:** `<s>34.4</s> &rarr;
  43.6` still renders as strikethrough and an arrow — `2026-08-14` is the
  regression test and **must probe clean**.
- **R2** No attribute survives on any tag in `shown`. **Negative:** the tag
  itself survives; this is not a retreat to plain text, which would lose the
  strikethrough the type needs.
- **R3** A `shown` containing anything outside the vocabulary is **refused at
  validation**, in `script.py`, before any render. **Negative:** refusal names
  the beat, the row and what was rejected — a bare "invalid" teaches nobody.
- **R4** `shown` appears in `agsoc video review`. **Negative:** it is the one
  field where the frame and the script legitimately differ (D-081), so the
  approver has to see it; showing only the row label is how this hid.

## The mutants this task must kill

Derive the assertions from these **before** implementing (D-064).

| # | Weaker implementation | Notices |
|---|---|---|
| M1 | `shown` back to raw innerHTML | R1 |
| M2 | attributes stripped from `<img>` but kept on `<s>` | R2 |
| M3 | blocklist of `on*` handlers instead of a whitelist | R1 (`onpointerenter`, `OnErRoR`, `on\terror`) |
| M4 | `<s>` dropped entirely, `shown` rendered as text | R1 negative — **`2026-08-14` regresses** |
| M5 | named entities escaped, so `&rarr;` shows literally | R1 negative |
| M6 | validation permits it and the renderer sanitises | R3 (the plan is the contract) |
| M7 | refusal message names neither beat nor row | R3 negative |
| M8 | `shown` still absent from `review` | R4 |
| M9 | the `NONDETERMINISTIC` lint extended to `shown` **instead of** sanitising | R1 — a lint is not a boundary (D-088) |

M9 is the one I most expect to be got wrong. Extending the lint *as well* is
fine; extending it *instead* re-files the same defect under a new name.

## Ride-alongs from the same review — smaller, and each is one decision

- **F3.** "A dumbbell renders no numbers" is asserted in three docstrings and
  enforced nowhere: `caption`, `footnote` and `label` are unconstrained and put
  `+18 pts` / `4.2 out of 5` on the stage. The existing test checks six literal
  fixture glyphs — the D-035 shape, a test that cannot fail. **Decide and say
  which:** enforce it, or strike the claim from the docstrings. Do not leave a
  guarantee that exists only in prose.
- **F4.** `dumbbellGaps`'s `!==` is untested — the test that claims to cover it
  asserts on dots decided by `engine.js`'s own independent `a!==b` (D-064).
  Mutating `!==` to `>` leaves the suite green. Test `planbuild`'s function.
- **F5/F6.** `decimals: 101` passes validation then throws `RangeError` at
  render; a value ≥ `1e21` renders `1e+21` past both R2 gates. Both are
  validation-time refusals.
- **F7.** Stray `*` pairs silently delete authored characters: `"o3* and o4*"` →
  `o3<em> and o4</em>`. **This is a bytes-diverge-from-script bug** — the same
  class D-078 closed, and it matters more than its LOW rating suggests, because
  Phase 5 verifies the script and the screen would show something else. At
  minimum it must not *delete* authored characters.

## Ground rules

- **Commits: tests first, then implementation.** Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it** — 23 brief defects across five phases against
  zero implementer errors, so finding one is a contribution, not a nuisance.
- No new dependencies. **No new CSS.**
- **Both committed episodes must probe clean** (`--day 2026-08-14 --probe`,
  `--day 2026-08-12 --probe`); `2026-08-14` is the direct regression test for R1.
- `determinism.test.mjs` and `network.test.mjs` stay green.
- **`RENDERABLE == set(BEAT_TYPES)` must still hold** — that is Phase 4's exit
  criterion and this task must not narrow it.
- **Report the mutation score.**

---

- [ ] **Step 1** — tests from the mutant table, including a reproduction of the
      cross-page-load non-reproducibility above. They must fail. Commit.
- [ ] **Step 2** — the closed vocabulary, in `script.py` (validation) and
      wherever `shown` reaches the DOM. Commit.
- [ ] **Step 3** — `review` shows `shown`. Commit.
- [ ] **Step 4** — the ride-alongs. Commit separately.
- [ ] **Step 5** — mutants, both probes, both node suites, full pytest.
- [ ] **Step 6** — **pin it where it will be noticed.** Add a `network.test.mjs`
      case driven from a **non-`custom`** beat. Every vector there today is a
      `custom` beat, which is precisely why this surface was invisible to it.

---

## Your report

`docs/superpowers/worklog/video/phase-04/task-5-report.md`:

1. **The vocabulary you allowed**, and the evidence from the committed episodes
   for each tag in it.
2. **The cross-load reproducibility test**, before and after, pasted.
3. **TDD evidence** and the **mutation score**; all nine mutants plus your sweep.
4. **Your decision on F3**, with reasoning.
5. **Files changed**, all commit SHAs.
6. **Issues or concerns**, including:
   - **Is there any other field on any type that reaches `innerHTML`?** Enumerate
     them from the code rather than from this brief. If `shown` was outside all
     three controls, assume the enumeration was never done properly.
   - What can `shown` still do that nothing prevents?
