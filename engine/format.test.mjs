/* The format is a declared context, not a stylesheet fork — spec §9.
 *
 * Run: node format.test.mjs
 *
 * Three properties, and the third is the one this phase exists for:
 *
 *   1. the stage is the size the plan declares, and vertical is unchanged;
 *   2. the same plan says the same WORDS and builds the same DOM in both
 *      formats — one layout system, two contexts. A second copy of a beat
 *      builder shows up here as a different element tree, which is the failure
 *      nobody would otherwise look at;
 *   3. a beat whose content does not fit its safe area is REFUSED, loudly, in
 *      both formats — and a beat that fits is not.
 *
 * No pixel golden files (Phase 4's ruling): every assertion below is on page
 * text or on geometry read out of the live layout. A hash would be bound to a
 * Chromium version and would report "the builder silently did nothing" as an
 * unexplained mismatch.
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { readFile, writeFile, rm } from 'node:fs/promises';

const HERE = dirname(fileURLToPath(import.meta.url));
const PLAN_JS = join(HERE, '.plan.js');
const previousPlan = await readFile(PLAN_JS, 'utf8').catch(() => null);

/* The two contexts, as plan.py emits them. Written out here rather than
 * imported: a plan reaches this page as JSON from anywhere (render.mjs --plan
 * reads any file), so the renderer's half of the contract has to hold on a plan
 * this file wrote by hand. */
const FORMATS = {
  vertical: { name: 'vertical', w: 1080, h: 1920, safe_top: 400, safe_bottom: 1580, measure: 'narrow', scale: 1 },
  wide: { name: 'wide', w: 1920, h: 1080, safe_top: 200, safe_bottom: 900, measure: 'wide', scale: 0.62 },
};

const HOLD = 3;
/* One beat of every type that draws text, with the words checked below. Kept
 * short deliberately: this is the FITTING fixture, and R3's negative half says
 * content that fits must render unremarked (D-040 — do not cry wolf). */
const BEATS = [
  { type: 'statement', kicker: 'Today', text: 'Google shipped its **main** agentic model' },
  { type: 'body', text: 'It is cheaper, faster and available today.' },
  { type: 'list', kicker: 'Live today in', lead: 'Tuned for coding', items: ['Gemini API', 'AI Studio', 'The Spark agent'] },
  { type: 'quote', text: 'Our new workhorse model', attribution: 'Google DeepMind' },
  { type: 'title', sub: 'Five stories from the last 24 hours' },
  { type: 'signoff', text: 'Same time tomorrow' },
  {
    type: 'kpis',
    kicker: 'And it costs half',
    items: [
      { value: 0.75, prefix: '$', label: 'per 1M input tokens', decimals: 2 },
      { value: 3.75, prefix: '$', label: 'per 1M output tokens', decimals: 2 },
    ],
    src: 'venturebeat',
    quote: 'priced at $0.75 per million input tokens and $3.75 per million output',
  },
  {
    type: 'jumpChart',
    rows: [
      { label: 'FrontierCode 1.1', before: 34.4, after: 43.6, shown: '<s>34.4</s> &rarr; 43.6' },
      { label: 'GDP.pdf', before: 22.0, after: 34.0, shown: '<s>22.0</s> &rarr; 34.0' },
    ],
    scale: 70,
    footnote: 'Scores as published by Google.',
    src: 'deepmind',
    quote: 'FrontierCode 1.1 rises from 34.4 to 43.6',
  },
  {
    type: 'dumbbell',
    caption: 'Evaluators rated it on par with physicians',
    series: ['AMIE (video)', 'Primary care physician'],
    rows: [
      { label: 'History-taking', values: [0.72, 0.72], note: 'on par' },
      { label: 'Eliciting physical signs', values: [0.82, 0.58], note: 'rated higher' },
    ],
    footnote: 'Direction only — the source reports ratings.',
  },
  {
    type: 'custom',
    js: "fade(E('div','body',{text:'drawn by the beat itself'}), .2);",
    attest: 'Draws one line and no figures. — the test',
  },
];

const planFor = (fmt, beats) => ({
  episode: '2026-08-16',
  series: 'the-brief',
  series_name: 'The Brief',
  byline: 'Ali Abdukarim',
  format: FORMATS[fmt],
  fps: 30,
  pace: 1,
  total_sec: beats.length * HOLD,
  total_frames: beats.length * HOLD * 30,
  design: {},
  beats: beats.map((b, i) => ({
    act: '',
    act_label: '',
    hold: HOLD,
    start: i * HOLD,
    end: (i + 1) * HOLD,
    kicker: '',
    src: '',
    ...b,
  })),
});

const browser = await chromium.launch();
let failures = 0;
const check = (ok, what, extra) => {
  if (!ok) failures++;
  console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}${ok || !extra ? '' : ` — ${extra}`}`);
  return ok;
};

/* Open a plan in its own format's viewport. Returns the page and the errors it
 * raised — an overflow refusal arrives as an uncaught page error, which is the
 * channel render.mjs already prints and exits on. */
async function open(fmt, beats) {
  const plan = planFor(fmt, beats);
  await writeFile(PLAN_JS, 'window.__PLAN = ' + JSON.stringify(plan) + ';\n', 'utf8');
  const page = await browser.newPage({
    viewport: { width: plan.format.w, height: plan.format.h },
    deviceScaleFactor: 1,
  });
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto('file://' + join(HERE, 'scene.html') + '?plan=1');
  await page.evaluate(() => document.body.classList.add('render'));
  await page.evaluate(() => document.fonts.ready);
  return { page, errors, plan };
}

/* The rendered words, and the element tree they were drawn with. The tree is
 * tags and classes only: geometry differs between formats by design, structure
 * must not. */
const readScene = (page) =>
  page.evaluate(() => {
    const skeleton = (el) =>
      el.tagName.toLowerCase() +
      (el.className ? '.' + String(el.className).trim().split(/\s+/).join('.') : '') +
      (el.children.length ? '[' + [...el.children].map(skeleton).join(',') + ']' : '');
    const sc = document.querySelector('#scenes .sc');
    return {
      text: document.getElementById('scenes').innerText.replace(/\s+/g, ' ').trim(),
      tree: sc ? skeleton(sc) : '(nothing built)',
    };
  });

const stageBox = (page) =>
  page.evaluate(() => {
    const s = document.getElementById('stage').getBoundingClientRect();
    const n = document.getElementById('scenes').getBoundingClientRect();
    return {
      w: Math.round(s.width),
      h: Math.round(s.height),
      measure: document.getElementById('stage').dataset.measure,
      safeTop: Math.round(n.top - s.top),
      safeBottom: Math.round(n.bottom - s.top),
    };
  });

/* ---- 1 · the stage is the size the plan declares -------------------------- */
const seen = {};
for (const fmt of ['vertical', 'wide']) {
  const { page, errors } = await open(fmt, BEATS);
  const box = await stageBox(page);
  const f = FORMATS[fmt];
  check(box.w === f.w && box.h === f.h, `${fmt}: the stage is ${f.w}×${f.h}`, JSON.stringify(box));
  check(box.measure === f.measure, `${fmt}: the stage declares measure=${f.measure}`, box.measure);
  check(
    box.safeTop === f.safe_top && box.safeBottom === f.safe_bottom,
    `${fmt}: the scene area is the declared safe area (${f.safe_top}…${f.safe_bottom})`,
    JSON.stringify(box),
  );
  check(errors.length === 0, `${fmt}: content that fits renders unremarked`, errors.join('; '));

  /* ---- 2 · same words, same tree, at the same t --------------------------- */
  seen[fmt] = [];
  for (let i = 0; i < BEATS.length; i++) {
    await page.evaluate((tt) => window.__seek(tt), i * HOLD + HOLD * 0.95);
    seen[fmt].push(await readScene(page));
  }
  const total = await page.evaluate(() => window.__total);
  check(total === BEATS.length * HOLD, `${fmt}: total runtime is the plan's ${BEATS.length * HOLD}s`, String(total));
  await page.close();
}

for (let i = 0; i < BEATS.length; i++) {
  const a = seen.vertical[i];
  const b = seen.wide[i];
  check(
    a.text === b.text && a.text.length > 0,
    `beat ${i} (${BEATS[i].type}) says the same words in both formats`,
    `\n       vertical: ${a.text}\n       wide:     ${b.text}`,
  );
  check(
    a.tree === b.tree,
    `beat ${i} (${BEATS[i].type}) is built by ONE builder, not two`,
    `\n       vertical: ${a.tree}\n       wide:     ${b.tree}`,
  );
}

/* ---- 3 · overflow is loud, in both formats -------------------------------- */
/* Long enough that no safe area on either stage can hold it. Nothing clips it:
 * the words simply leave the card, and every check this project has built —
 * verification, drift, determinism — is green while it happens. */
const TOO_MUCH = [
  { type: 'body', text: 'It fits.' },
  {
    type: 'list',
    kicker: 'Everything',
    lead: 'Far more rows than any card can hold, and not one of them is clipped — they simply leave the card.',
    items: Array.from({ length: 22 }, (_, i) => `Row ${i + 1} — a line of copy that is long enough to wrap`),
  },
];
for (const fmt of ['vertical', 'wide']) {
  const { page, errors } = await open(fmt, TOO_MUCH);
  const said = errors.join(' ; ');
  check(
    /overflow/i.test(said) && said.includes('beat 1'),
    `${fmt}: a beat that does not fit its safe area is refused, naming the beat`,
    said || '(no page error at all — it was clipped silently)',
  );
  check(
    said.includes(FORMATS[fmt].name),
    `${fmt}: the refusal names the format it was measured in`,
    said,
  );
  await page.close();
}

/* An unbreakable string wider than the measure — the other axis, and the one a
 * line count cannot see. */
const TOO_WIDE = [
  { type: 'statement', text: 'Supercalifragilistic' + 'expialidocious'.repeat(6) },
];
for (const fmt of ['vertical', 'wide']) {
  const { page, errors } = await open(fmt, TOO_WIDE);
  check(
    /overflow/i.test(errors.join(' ; ')),
    `${fmt}: a word wider than the measure is refused too`,
    errors.join(' ; ') || '(no page error)',
  );
  await page.close();
}

/* ---- 4 · type_scale is a knob that turns ---------------------------------- */
/* D-116: `type_family` and `type_scale` were copied into plan.json and the
 * engine ignored both — two knobs an operator would believe control the
 * typography, that controlled nothing, and which the approval nevertheless
 * bound. `type_family` is retired (D-077); `type_scale` is wired, and "wired"
 * is a measurement, not a grep: the same words must be SMALLER on the frame at
 * `compact` and larger at `large`. */
{
  const capHeight = async (scale) => {
    const plan = planFor('vertical', [{ type: 'statement', text: 'One line, three ways' }]);
    plan.design = { type_scale: scale };
    await writeFile(PLAN_JS, 'window.__PLAN = ' + JSON.stringify(plan) + ';\n', 'utf8');
    const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('file://' + join(HERE, 'scene.html') + '?plan=1');
    await page.evaluate(() => document.body.classList.add('render'));
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(() => window.__seek(1.5));
    const h = await page.evaluate(() => {
      const el = document.querySelector('#scenes h1');
      return el ? el.getBoundingClientRect().height : 0;
    });
    await page.close();
    return { h, errors };
  };
  const compact = await capHeight('compact');
  const dflt = await capHeight('default');
  const large = await capHeight('large');
  check(dflt.h > 0, 'type_scale: the statement is on the card at all', JSON.stringify(dflt));
  check(
    compact.h < dflt.h && dflt.h < large.h,
    'type_scale actually scales the type (compact < default < large)',
    `compact=${compact.h} default=${dflt.h} large=${large.h}`,
  );
  const bad = await (async () => {
    const plan = planFor('vertical', [{ type: 'body', text: 'x' }]);
    plan.design = { type_scale: 'enormous' };
    await writeFile(PLAN_JS, 'window.__PLAN = ' + JSON.stringify(plan) + ';\n', 'utf8');
    const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    await page.goto('file://' + join(HERE, 'scene.html') + '?plan=1');
    await page.close();
    return errors.join(' ; ');
  })();
  check(
    /type_scale/.test(bad),
    'an unknown type_scale is refused rather than silently defaulted',
    bad || '(no page error)',
  );
}

await browser.close();
if (previousPlan === null) await rm(PLAN_JS, { force: true });
else await writeFile(PLAN_JS, previousPlan, 'utf8');
console.log(failures ? `${failures} FAILURES` : 'both formats hold');
process.exit(failures ? 1 : 0);
