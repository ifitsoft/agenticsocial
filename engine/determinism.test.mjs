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

const CASES = [
  { label: 'day path', qs: 'day=2026-08-14', times: [0.5, 3.7, 42.9] },
  {
    label: 'plan path',
    qs: 'plan=1',
    // past the midpoint of each beat, where the text has landed
    times: FIXTURE.map((_, i) => i * HOLD + HOLD * 0.72),
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
      await page.evaluate((tt) => window.__seek(tt), i * HOLD + HOLD * 0.72);
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
