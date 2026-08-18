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
import { spawn } from 'node:child_process';

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

/* The other direction, and the one a centred column cannot produce on its own:
 * a `custom` beat — the escape hatch, and the only builder that can position
 * its own element — pushed off the TOP. A check that only looks downwards
 * reports this card as fitting. */
const TOO_HIGH = [
  {
    type: 'custom',
    /* `position:relative`, not a negative margin: a flex column that centres
     * its items absorbs the margin into the free space and puts the card back
     * on screen. A relative offset moves the pixels and not the layout, which
     * is exactly the shape of the bug — the box says it fits and the words are
     * somewhere else. */
    js: "E('div','body',{text:'Pushed clean off the top of the card',"
      + "css:{position:'relative',top:'-900px'}});",
    attest: 'One line, positioned by hand. — the test',
  },
];
for (const fmt of ['vertical', 'wide']) {
  const { page, errors } = await open(fmt, TOO_HIGH);
  const said = errors.join(' ; ');
  check(
    /overflow/i.test(said) && /above/.test(said),
    `${fmt}: a beat pushed off the TOP is refused too`,
    said || '(no page error)',
  );
  await page.close();
}

/* R3's negative half, and the one that pins WHEN the measurement is taken.
 * This card is 18 layout px shy of its safe area — it fits, and it fits in both
 * formats because the height is computed from the format's own band. Measured
 * before the entrance animation lands, `fade`'s 26px offset would report it as
 * overflowing, and a check that refuses a card an operator composed to the edge
 * is a check that gets turned off (D-040). */
const nearlyFull = (fmt) => {
  const f = FORMATS[fmt];
  const h = Math.round((f.safe_bottom - f.safe_top) / f.scale) - 18;
  return [
    {
      type: 'custom',
      js: "fade(E('div','body',{text:'Composed right up to the edge of the card',"
        + "css:{height:'" + h + "px'}}), .1);",
      attest: 'A card that fills its safe area. — the test',
    },
  ];
};
for (const fmt of ['vertical', 'wide']) {
  const { page, errors } = await open(fmt, nearlyFull(fmt));
  check(
    errors.length === 0,
    `${fmt}: a card composed to within 18px of its safe area is NOT refused`,
    errors.join(' ; '),
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

/* ---- 5 · through render.mjs, which is what actually shoots a frame -------- */
/* Everything above drives the page directly. render.mjs is the process the CLI
 * runs, it owns the viewport, and it is the only place the refusal has to
 * ARRIVE — spec 9's `--format wide` is a promise about an mp4, not about a
 * DOM. Two single frames, ~1s each (D-119): no test here renders an episode. */
{
  const planPath = join(HERE, '.fmt-test-plan.json');
  const outDir = join(HERE, 'probe-fmt-test');
  const runRender = async (plan) => {
    await writeFile(planPath, JSON.stringify(plan), 'utf8');
    return new Promise((resolve) => {
      const p = spawn(process.execPath, [
        join(HERE, 'render.mjs'), '--plan', planPath, '--at', '1', '--out', outDir,
      ]);
      let err = '';
      p.stderr.on('data', (d) => (err += d));
      p.stdout.on('data', () => {});
      p.on('close', (code) => resolve({ code, err }));
    });
  };

  const wide = await runRender(planFor('wide', BEATS));
  check(wide.code === 0, 'render.mjs renders a wide plan', wide.err);
  /* The PNG's own IHDR, bytes 16..24 — the size of the FILE, not of a page
     object this test could have measured wrong. No dependency, and no golden
     pixels: this reads the header, not the image. */
  const png = await readFile(join(outDir, 'at-1.png')).catch(() => null);
  const size = png && { w: png.readUInt32BE(16), h: png.readUInt32BE(20) };
  check(
    size && size.w === 1920 && size.h === 1080,
    'render.mjs shoots a 1920x1080 frame for a wide plan (M7, end to end)',
    JSON.stringify(size),
  );

  const vert = await runRender(planFor('vertical', BEATS));
  const png2 = await readFile(join(outDir, 'at-1.png')).catch(() => null);
  const size2 = png2 && { w: png2.readUInt32BE(16), h: png2.readUInt32BE(20) };
  check(
    vert.code === 0 && size2 && size2.w === 1080 && size2.h === 1920,
    'render.mjs still shoots 1080x1920 for a vertical plan (M8)',
    JSON.stringify(size2) + vert.err,
  );

  for (const fmt of ['vertical', 'wide']) {
    const bad = await runRender(planFor(fmt, TOO_MUCH));
    check(
      bad.code !== 0 && /overflow/i.test(bad.err),
      `${fmt}: render.mjs EXITS on an overflowing beat, before any frame`,
      `exit ${bad.code}: ${bad.err.trim() || '(silent)'}`,
    );
  }
  await rm(planPath, { force: true });
  await rm(outDir, { recursive: true, force: true });
}

await browser.close();
if (previousPlan === null) await rm(PLAN_JS, { force: true });
else await writeFile(PLAN_JS, previousPlan, 'utf8');
console.log(failures ? `${failures} FAILURES` : 'both formats hold');
process.exit(failures ? 1 : 0);
