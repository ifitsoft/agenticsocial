/* Determinism: the same t rendered twice must be byte-identical.
 *
 * This is the engine's load-bearing invariant. It is what makes a render
 * reproducible and any single frame re-creatable for inspection months later.
 * Run: node determinism.test.mjs
 *
 * The plan-path case also checks that every renderable beat type puts its own
 * words on the stage. That is deliberately NOT a pixel golden file: a hash is
 * bound to a Chromium version (which is why this project pins Playwright) and
 * reports "the builder silently did nothing" as an unexplained mismatch. Read
 * the text instead, and the failure names the beat.
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { createHash } from 'node:crypto';
import { readFile, writeFile, rm } from 'node:fs/promises';

const HERE = dirname(fileURLToPath(import.meta.url));

/* One beat of every type planbuild.js can draw, with the characters that used
 * to vanish. `<thinking>` was parsed as an unknown tag and disappeared from the
 * frame while script.yaml still said it — the verification defect this phase
 * closes — and `&amp;` must stay five characters, not decode to one. */
const HOLD = 3.0;
const FIXTURE = [
  {
    beat: { type: 'statement', text: 'The model is <thinking> about **it**' },
    expect: ['The model is <thinking> about it'],
  },
  {
    beat: { type: 'body', text: 'AT&T raised prices &amp; nobody noticed' },
    expect: ['AT&T raised prices &amp; nobody noticed'],
  },
  {
    beat: {
      type: 'list',
      kicker: 'Live today in',
      lead: 'Tuned for **coding** & agents',
      items: ['Gemini API & AI Studio', '<script> tags', 'The Spark agent'],
    },
    expect: [
      'Live today in',
      'Tuned for coding & agents',
      'Gemini API & AI Studio',
      '<script> tags',
      'The Spark agent',
    ],
  },
  {
    beat: {
      type: 'quote',
      text: 'Gemini 3.7 Flash is our new workhorse model',
      attribution: 'Google DeepMind',
    },
    expect: ['Gemini 3.7 Flash is our new workhorse model', 'Google DeepMind'],
  },
  {
    beat: { type: 'title', sub: 'Five stories from the last 24 hours' },
    expect: ['THE BRIEF', 'Five stories from the last 24 hours'],
  },
  {
    /* R3's negative, and the mutant the browser half missed until this beat
     * existed: `title` has no required fields, so a bare one is legal and must
     * still put a card on screen. */
    beat: { type: 'title' },
    expect: ['THE BRIEF', '2026-08-16'],
  },
  {
    beat: { type: 'signoff', text: 'Same time tomorrow' },
    expect: ['THE BRIEF', 'Same time tomorrow'],
  },
  {
    /* The two strictly verifiable types, with the real 2026-08-14 figures.
     *
     * Read as text, not as pixels, and for the same reason as everything above
     * — but here the text IS the claim. A hash would report "the count-up ended
     * somewhere else" as an unexplained mismatch; this reports the number.
     *
     * `$0.75`, not `0.8`: the symbol and the separator are presentation, and
     * the digits are the plan's own. The `decimals: 2` is what makes 0.75 legal
     * at all — without it the engine's Math.round branch would render `1`, and
     * planbuild.js refuses the beat rather than draw it. */
    beat: {
      type: 'kpis',
      kicker: 'And it costs half of what 3.6 Flash did',
      items: [
        { value: 0.75, prefix: '$', label: 'per 1M input tokens', decimals: 2 },
        { value: 3.75, prefix: '$', label: 'per 1M output tokens', decimals: 2 },
        { value: 50, unit: '%', label: 'cheaper than 3.6 Flash' },
      ],
      src: 'venturebeat',
      quote: 'priced at $0.75 per million input tokens and $3.75 per million output',
    },
    /* Sampled at 0.95 of the hold, not 0.72: the LAST row of a three-row stack
     * starts counting at 1.59s and takes 1.35s, so at 0.72 the frame shows 47%
     * on its way to 50 — a number no one authored. See the report's section 6;
     * this file samples where the count has landed, which is also where a
     * viewer reads it. */
    at: 0.95,
    expect: [
      '$0.75',
      '$3.75',
      'per 1M input tokens',
      'per 1M output tokens',
      '50%',
      'cheaper than 3.6 Flash',
    ],
  },
  {
    /* The real four rows from content/2026-08-14.js. `shown` is the one field
     * rendered as HTML, and both halves of that matter here: `<s>` must strike
     * the old score through rather than print as text, and `&rarr;` must reach
     * the frame as an arrow. The footnote is the opposite case — plain text,
     * required, and the thing that stops the chart being read as something this
     * series measured itself. The footnote fades in after the last bar has
     * grown, which is past 0.72 of a 3s hold — sample where a viewer would
     * actually have it. */
    at: 0.95,
    beat: {
      type: 'jumpChart',
      rows: [
        { label: 'FrontierCode 1.1', before: 34.4, after: 43.6, shown: '<s>34.4</s> &rarr; 43.6' },
        { label: 'DeepSWE v1.1', before: 48.0, after: 65.3, shown: '<s>48–49</s> &rarr; 65.3' },
        { label: 'AutomationBench', before: 17.0, after: 30.4, shown: '<s>17.0</s> &rarr; 30.4' },
        { label: 'GDP.pdf', before: 22.0, after: 34.0, shown: '<s>22.0</s> &rarr; 34.0' },
      ],
      scale: 70,
      footnote:
        'Scores as published by Google, on a common 0–70% scale. The DeepSWE v1.1 baseline is reported as a 48–49% range.',
      src: 'deepmind',
      quote: 'FrontierCode 1.1 rises from 34.4 to 43.6',
    },
    expect: [
      'FrontierCode 1.1',
      '34.4→43.6',
      'DeepSWE v1.1',
      '48–49→65.3',
      'AutomationBench',
      '17.0→30.4',
      'GDP.pdf',
      '22.0→34.0',
      'Scores as published by Google',
    ],
  },
];

const PLAN = {
  episode: '2026-08-16',
  series: 'the-brief',
  series_name: 'The Brief',
  byline: 'Ali Abdukarim',
  format: { name: 'vertical', w: 1080, h: 1920 },
  fps: 30,
  /* Not 1: `hold` in a plan is ALREADY scaled by pace in Python, so a renderer
   * that scales again shifts every beat and this file's seek times land in the
   * wrong scene. With pace 1 that mutant is invisible. */
  pace: 1.293,
  design: {},
  beats: FIXTURE.map((f, i) => ({
    act: '',
    act_label: '',
    hold: HOLD,
    start: i * HOLD,
    end: (i + 1) * HOLD,
    kicker: '',
    src: '',
    ...f.beat,
  })),
};

/* .plan.js is how render.mjs hands a plan to the page — fetch and ES modules
 * are both CORS-blocked over file://. It is a build artifact (gitignored), but
 * restore whatever was there so running the tests never costs someone the plan
 * they were mid-render on. */
const PLAN_JS = join(HERE, '.plan.js');
const previousPlan = await readFile(PLAN_JS, 'utf8').catch(() => null);
await writeFile(PLAN_JS, 'window.__PLAN = ' + JSON.stringify(PLAN) + ';\n', 'utf8');

/* Past the midpoint of each beat, where the text has landed. A fixture may ask
 * for a later fraction: an eased count-up is still moving well past the
 * midpoint, and a frame sampled mid-count shows a number no one authored. */
const sampleAt = (f, i) => i * HOLD + HOLD * (f.at == null ? 0.72 : f.at);

const CASES = [
  { label: 'day path', qs: 'day=2026-08-14', times: [0.5, 3.7, 42.9] },
  {
    label: 'plan path',
    qs: 'plan=1',
    times: FIXTURE.map(sampleAt),
    content: FIXTURE,
  },
];

const browser = await chromium.launch();
let failures = 0;

/* innerText is the RENDERED text, and two presentation details are not the
 * script's business:
 *
 *   - line breaking. A masked word rise wraps every word in its own
 *     inline-block, so compare on the characters, not the spaces.
 *   - case. `.kicker` and `.byline` carry `text-transform:uppercase` in
 *     scene.html, so a kicker written "Live today in" renders — and reads back
 *     from innerText — as "LIVE TODAY IN". The DOM still holds the authored
 *     bytes; only the glyphs are uppercased. Worth knowing in Phase 5: a
 *     verifier that reads innerText must fold case or read textContent, or it
 *     will report every kicker in the series as a divergence.
 *
 * Everything this check exists to catch — a dropped word, a decoded entity, a
 * stray `**` — survives both foldings. */
const squash = (s) => s.replace(/\s+/g, '').toLowerCase();

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

    // The page state must be a pure function of t too, not just the pixels.
    // An element hidden with opacity:0 still holds its text, so a screenshot is
    // structurally blind to a scene inheriting the previous scene's act chip or
    // source tag. Read the text instead.
    //
    // Sweep several predecessors rather than just one: a single detour proves
    // nothing if both arms happen to come from scenes that set the same chrome.
    // Some scene in the episode has an act chip and some does not, and arriving
    // from each must land in the same place.
    const chromeAfter = async (from) => {
      await page.evaluate((f) => window.__seek(f), from);
      await page.evaluate((tt) => window.__seek(tt), t);
      return page.evaluate(() => document.getElementById('stage').innerText);
    };
    const seen = [];
    for (const from of [0, 99, ...c.times]) seen.push([from, await chromeAfter(from)]);
    const odd = seen.find(([, s]) => s !== seen[0][1]);
    if (odd) failures++;
    console.log(
      `  ${odd ? 'FAIL' : 'ok  '} ${c.label} t=${t}  chrome text` +
        (odd ? ` differs when reached via t=${odd[0]}` : ' stable from every predecessor'),
    );
  }

  /* Every beat says on screen what the script said. The negative half matters
   * as much: no `**` markers left over, and no entity decoded on the way. */
  if (c.content) {
    for (let i = 0; i < c.content.length; i++) {
      const { beat, expect } = c.content[i];
      await page.evaluate((tt) => window.__seek(tt), sampleAt(c.content[i], i));
      /* #scenes, not #stage. The stage's chrome carries the brand chip ("THE
       * BRIEF") and the date, so a title card that rendered NOTHING still
       * satisfied both of its expectations when read from #stage — the check
       * passed on an empty scene. Read only what the builder built. */
      const shown = await page.evaluate(() => document.getElementById('scenes').innerText);
      const missing = expect.filter((e) => !squash(shown).includes(squash(e)));
      const leaked = shown.includes('**') ? ' · `**` reached the screen' : '';
      if (missing.length || leaked) failures++;
      console.log(
        `  ${missing.length || leaked ? 'FAIL' : 'ok  '} beat ${i} (${beat.type})` +
          (missing.length ? ` missing ${JSON.stringify(missing)}${leaked}` : ` renders its text${leaked}`),
      );
    }
  }

  if (errors.length) {
    failures++;
    console.error('  page errors: ' + errors.join('; '));
  }
  await page.close();
}

await browser.close();
if (previousPlan === null) await rm(PLAN_JS, { force: true });
else await writeFile(PLAN_JS, previousPlan, 'utf8');
console.log(failures ? `${failures} FAILURES` : 'deterministic');
process.exit(failures ? 1 : 0);
