# Task 2 Brief: The engine renders a plan

**Phase:** 1.5 · **Branch:** `feat/video-phase-1.5-vertical-slice` · **Follows:** `3a603b0`
**Repo:** `/Users/aabdukarim/Documents/Code/agenticsocial`

## Ground rules

- **Three commits**, in order: Step 0 (Python fixes), Step 2 (engine), Step 4
  (determinism test). Do not squash.
- **Pipe command output to a file and paste from it.**
- Code blocks are authoritative; prose explains *why*. If they disagree, follow
  the code block **and flag it**. Nine of my briefs have had that defect.
- Do not add dependencies — not to `pyproject.toml`, not to `engine/package.json`.
- Never stage anything under `docs/`. Report observed counts.
- **The existing `?day=` path must keep working.** `node render.mjs --day 2026-08-14 --probe`
  must still render the committed episode. That is an exit criterion, not a nicety.

## Step 0 — two Python fixes carried from Task 1b (its own commit)

**0a. Beat collapse.** `_statement` rejects `hold <= 0`, but a beat whose
*scaled* hold is under one frame renders for **zero frames** — the operator's
beat silently vanishes from the video. Found by the Task 1b implementer with
`hold: 0.01`. In `build_plan`, immediately after computing `hold`:

```python
        if round(hold * FPS) < 1:
            raise PlanError(
                f"{where}: beat {i} lasts {hold}s at pace {pace}, under one frame "
                f"at {FPS}fps — it would not appear in the render"
            )
```

**0b. Unrounded floats reach the artifact.** Task 1b's own mutant 10 survives:
dropping `round(start, 3)` / `round(end, 3)` leaves the suite green and lets
`11.550000000000002` into a file whose stated purpose is diffability. The
byte-stability test cannot see it — the noise is deterministic. Append to
`tests/test_video_plan.py`:

```python
def test_resolved_times_are_rounded_not_raw_floats(series):
    """0.1 + 0.2 arithmetic must not reach a file whose purpose is diffability.
    Kills the mutant that drops round(start/end, 3)."""
    ep = create_episode(series, "2026-08-14")
    _script(ep, THREE, pace=1.1)
    for b in build_plan(series, load_episode(series, "2026-08-14"))["beats"]:
        for key in ("hold", "start", "end"):
            assert b[key] == round(b[key], 3), (key, b[key])


def test_a_beat_shorter_than_one_frame_is_refused(series):
    ep = create_episode(series, "2026-08-14")
    _script(ep, "beats:\n  - type: statement\n    text: blink\n    hold: 0.01\n")
    with pytest.raises(PlanError, match="one frame"):
        build_plan(series, load_episode(series, "2026-08-14"))
```

Also fix the docstring on `test_total_sec_is_the_last_end_not_a_sum` — the Task
1b implementer proved it is **unkillable by construction** while beats cannot
overlap, and an honest docstring is better than a test that claims more than it
delivers:

```python
def test_total_sec_is_the_last_end_not_a_sum(series):
    """Documents shape, and cannot currently fail.

    While beats are contiguous and non-overlapping, `sum(hold)` and
    `beats[-1]["end"]` are provably equal, so no mutant distinguishes them. It
    is kept because deriving the total from the last end is what lets tracks be
    added later without changing the timing contract — see the Phase 1.5 plan.
    """
```

```bash
uv run pytest tests/test_video_plan.py 2>&1 | tail -10
git add src/agenticsocial/video/plan.py tests/test_video_plan.py
git commit -m "fix: refuse sub-frame beats, pin rounded times

A beat whose scaled hold is under one frame rendered for zero frames --
the operator's beat vanished from the video with no error. Dropping the
round() on start/end also survived mutation, letting raw float noise into
an artifact whose purpose is diffability."
```

## Step 1 — how the plan reaches the page

`scene.html` loads its script with `document.write('<script src=…>')`. That is
**not incidental**: `fetch` and ES modules are both CORS-blocked over `file://`.
So the plan cannot be fetched as JSON by the page — it must arrive as a classic
script.

`render.mjs` therefore reads `plan.json` with Node's `JSON.parse` (no dependency)
and writes `engine/.plan.js` containing `window.__PLAN = {…};` next to
`scene.html`, then loads `scene.html?plan=1`.

Add `.plan.js` to `.gitignore` under the engine block:

```
engine/.plan.js
```

- [ ] **Step 2a: `engine/planbuild.js`**

```js
/* Build scenes from a resolved plan.
 *
 * Timing is ALREADY RESOLVED in Python: `hold` is scaled by pace, and `start`,
 * `end`, `start_frame`, `end_frame` are absolute. This file does NO timing
 * arithmetic — that is the whole point of plan.json. Arithmetic here would be
 * arithmetic the determinism test has to police, and it could disagree with the
 * plan's own total.
 *
 * Loaded as a classic script: ES modules are CORS-blocked over file://.
 */

/* plan.design uses spec §6 token names; the stage uses CSS custom properties. */
var PLAN_TOKENS = {
  surface: '--paper',
  ink: '--ink',
  ink_muted: '--ink-2',
  accent: '--blue',
  accent_alt: '--cyan',
  accent_warm: '--warm',
};

function applyPlanDesign(design) {
  if (!design) return;
  var root = document.documentElement;
  for (var key in PLAN_TOKENS) {
    if (typeof design[key] === 'string' && design[key]) {
      root.style.setProperty(PLAN_TOKENS[key], design[key]);
    }
  }
}

function buildStatement(b) {
  return function () {
    if (b.kicker) E('div', 'kicker', P(b.kicker));
    var h = E('h1', null, P(b.text));
    rise(h, 0.22, { stag: 0.045 });
  };
}

function buildFromPlan(plan) {
  if (!plan || !Array.isArray(plan.beats) || !plan.beats.length) {
    throw new Error('plan has no beats');
  }
  applyPlanDesign(plan.design);
  meta({
    date: plan.episode,
    dateShort: plan.episode,
    dateLong: plan.episode,
    byline: plan.byline || '',
    warmActs: [],
    pace: 1, // holds are already scaled in Python; do not scale twice
  });
  for (var i = 0; i < plan.beats.length; i++) {
    var b = plan.beats[i];
    if (b.type !== 'statement') {
      throw new Error('unsupported beat type: ' + b.type);
    }
    scene(b.act || '', b.hold, b.src || '', buildStatement(b));
  }
}
```

`buildStatement` returns a closure so each scene captures its own beat — a bare
`for` loop with `var` would give every scene the last beat.

- [ ] **Step 2b: `engine/scene.html`**

Replace the two loader `<script>` blocks at the end (currently lines ~194–201)
with:

```html
<script src="engine.js"></script>
<script src="planbuild.js"></script>
<script>
  /* Load the script synchronously so scene() calls land before init().
     Classic <script src> works over file://; ES modules would be CORS-blocked.
     ?plan=1 renders a resolved plan.json written by `agsoc video render`;
     ?day=<date> renders content/<date>.js, the hand-written path. */
  var __q = new URLSearchParams(location.search);
  if (__q.get('plan')) {
    document.write('<scr' + 'ipt src=".plan.js"><\/scr' + 'ipt>');
  } else {
    var __day = __q.get('day') || '2026-08-14';
    document.write('<scr' + 'ipt src="content/' + encodeURIComponent(__day) + '.js"><\/scr' + 'ipt>');
  }
</script>
<script>
  if (window.__PLAN) buildFromPlan(window.__PLAN);
  init();
</script>
```

- [ ] **Step 2c: `engine/render.mjs`**

Add `--plan` and `--out`. Insert after the existing `const day = …` line:

```js
const planPath = flag('plan');
const outDir = flag('out');
```

Replace the `const qs = …` block and the `page.goto` line with:

```js
const qs = new URLSearchParams();
if (planPath) {
  const { readFile, writeFile } = await import('node:fs/promises');
  const plan = JSON.parse(await readFile(planPath, 'utf8'));
  await writeFile(
    join(HERE, '.plan.js'),
    'window.__PLAN = ' + JSON.stringify(plan) + ';\n',
    'utf8',
  );
  qs.set('plan', '1');
} else {
  qs.set('day', day);
}
if (pace) qs.set('pace', String(pace));
```

and, where frames are written, honour `--out`:

```js
  const dir = outDir || join(HERE, 'frames');
```

The `no scenes loaded` error message should name the right input:

```js
  console.error(planPath ? `no scenes in ${planPath}` : `no scenes loaded — is content/${day}.js present?`);
```

- [ ] **Step 3: Prove both paths work, then commit**

```bash
cd engine
node render.mjs --day 2026-08-14 --probe 2>&1 | tail -3     # existing path
cd .. && export AGSOC_WORKSPACE=/tmp/slice/workspace && rm -rf /tmp/slice
uv run agsoc init /tmp/slice/workspace && uv run agsoc series new the-brief --name "The Brief"
uv run agsoc video new 2026-08-14 --series the-brief
cat > /tmp/slice/workspace/series/the-brief/episodes/2026-08-14/script.yaml <<'YAML'
---
episode: '2026-08-14'
series: the-brief
status: draft
pace: 1.0
---
beats:
  - type: statement
    act: "01"
    hold: 3.5
    kicker: The vertical slice
    text: This came out of a script.yaml.
    src: agsoc
  - type: statement
    hold: 3.0
    text: Python resolved every frame boundary.
  - type: statement
    hold: 3.5
    text: The engine only looked things up.
YAML
uv run python -c "
from agenticsocial.workspace import Workspace
from agenticsocial.video.series import load_series
from agenticsocial.video.episode import load_episode
from agenticsocial.video.plan import write_plan
ws=Workspace.locate(); s=load_series(ws,'the-brief')
print(write_plan(s, load_episode(s,'2026-08-14')))"
cd engine && node render.mjs --plan /tmp/slice/workspace/series/the-brief/episodes/2026-08-14/out/plan-vertical.json --probe 2>&1 | tail -3
```

Both must succeed. Paste both outputs.

```bash
git add engine/planbuild.js engine/scene.html engine/render.mjs .gitignore
git commit -m "feat: render a resolved plan.json through the existing engine

Python emits plan.json; render.mjs JSON.parses it and writes .plan.js for
the page, because fetch and ES modules are CORS-blocked over file://.
planbuild.js does no timing arithmetic -- holds arrive pre-scaled, so
META.pace is 1 and the engine only looks values up. The ?day= path is
unchanged."
```

- [ ] **Step 4: The determinism test**

`window.__seek(t)` purity is the engine's load-bearing invariant (`CLAUDE.md`).
Create `engine/determinism.test.mjs` — plain Node, no test framework, no
dependency:

```js
/* Determinism: the same t rendered twice must be byte-identical.
 *
 * This is the engine's load-bearing invariant. It is what makes a render
 * reproducible and any single frame re-creatable for inspection months later.
 * Run: node determinism.test.mjs
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { createHash } from 'node:crypto';

const HERE = dirname(fileURLToPath(import.meta.url));
const CASES = [
  { label: 'day path', qs: 'day=2026-08-14', times: [0.5, 3.7, 42.9] },
];
if (process.argv.includes('--plan')) {
  CASES.push({ label: 'plan path', qs: 'plan=1', times: [0.5, 3.7, 8.0] });
}

const browser = await chromium.launch();
let failures = 0;

for (const c of CASES) {
  const page = await browser.newPage({
    viewport: { width: 1080, height: 1920 },
    deviceScaleFactor: 1,
  });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto('file://' + join(HERE, 'scene.html') + '?' + c.qs);
  await page.evaluate(() => document.body.classList.add('render'));
  await page.evaluate(() => document.fonts.ready);

  for (const t of c.times) {
    const shot = async () => {
      await page.evaluate((tt) => window.__seek(tt), t);
      return createHash('sha256').update(await page.screenshot({ type: 'png' })).digest('hex');
    };
    const a = await shot();
    // seek elsewhere and back: __seek(t) must not depend on what came before
    await page.evaluate(() => window.__seek(0));
    await page.evaluate(() => window.__seek(99));
    const b = await shot();
    const ok = a === b;
    if (!ok) failures++;
    console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${c.label} t=${t}  ${a.slice(0, 12)} ${b.slice(0, 12)}`);
  }
  if (errors.length) {
    failures++;
    console.error('  page errors: ' + errors.join('; '));
  }
  await page.close();
}

await browser.close();
console.log(failures ? `${failures} FAILURES` : 'deterministic');
process.exit(failures ? 1 : 0);
```

Seeking away and back is the point: it catches state accumulating across calls,
which a naive same-`t`-twice check would miss entirely.

```bash
cd engine && node determinism.test.mjs 2>&1 | tail -8
git add engine/determinism.test.mjs
git commit -m "test: pin __seek(t) purity, including independence from seek order"
```

---

## Your report

`docs/superpowers/worklog/video/phase-1.5/task-2-report.md`:

1. **What I changed.**
2. **Evidence** — piped output for: the Python suite, `--day` probe, `--plan`
   probe, and the determinism test.
3. **Files changed**, all three commit SHAs.
4. **Vacuity audit** of the tests you wrote. Two implementers before you caught
   vacuous tests of mine by writing a mutant for each rather than reasoning about
   them. Hold yours to that standard.
5. **Issues or concerns**, including:
   - Does the determinism test actually catch impurity? **Prove it** — introduce
     a deliberate `Math.random()` or `Date.now()` into `engine.js`, show the test
     failing, and revert. If it does not catch it, the test is theatre.
   - `.plan.js` is written next to `scene.html`, so two concurrent renders would
     race. Does that matter yet, and what is the right fix if so?
   - The design tokens map six of eight `series.toml` keys onto CSS variables.
     What happens to `type_family` and `type_scale`, and is dropping them
     silently acceptable?
