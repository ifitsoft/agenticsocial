/**
 * Deterministic frame renderer. It renders a PLAN, and nothing else.
 *
 *   node render.mjs --plan <plan.json> --out <dir>            every frame
 *   node render.mjs --plan <plan.json> --out <dir> --probe    one frame per beat
 *   node render.mjs --plan <plan.json> --out <dir> --at 34    one frame at t=34s
 *
 * **You are not expected to run this by hand.** `agsoc video render` writes the
 * plan, invokes this, and encodes the frames; `agsoc video probe` invokes it for
 * the two single-frame modes. Those commands are the supported path because they
 * are the ones that pass the approval gate — spec §6, §9, §10.
 *
 * `--day <date>` used to render `content/<date>.js` directly. It retired in
 * Phase 8: it was a second route from an episode to an MP4 that never passed
 * `check` or `approve`. The two hand-written episodes remain as the engine's
 * regression fixtures and are still loaded by `scene.html?day=…`, which is what
 * `determinism.test.mjs` drives and how the slider is scrubbed in a browser.
 *
 * --plan JSON.parses the plan and writes engine/.plan.js for the page, because
 * fetch and ES modules are both CORS-blocked over file://.
 */
import { chromium } from 'playwright';
import { mkdir, rm } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const flag = (name) => {
  const i = argv.indexOf('--' + name);
  return i > -1 ? argv[i + 1] : null;
};
const probe = argv.includes('--probe');
const at = flag('at') !== null ? Number(flag('at')) : null;
const planPath = flag('plan');
const outDir = flag('out');

/* Refused, not defaulted. The retired `--day` defaulted to today, so a bare
 * `node render.mjs` rendered whatever happened to be lying in content/ — and
 * said nothing about the fact that nobody had approved it. */
if (!planPath) {
  console.error(
    'render.mjs renders a plan: --plan <plan.json> [--out <dir>] [--probe|--at T].\n' +
    'The plan comes from `agsoc video render`, which is the supported path — it is\n' +
    'the one that checks the episode was approved and has not changed since.',
  );
  process.exit(2);
}

const { readFile, writeFile } = await import('node:fs/promises');
const plan = JSON.parse(await readFile(planPath, 'utf8'));

/* Frame count and rate come from the PLAN, never from arithmetic here. Python
 * resolves every time in the episode (D-007) and plan.json already carries
 * `fps` and `total_frames`; recomputing them is a second answer to a question
 * that has one, and the two disagree at the rounding boundary — which reaches a
 * viewer as a video that stops one frame early. Refused rather than defaulted:
 * a plan without a frame count is a plan this cannot render.
 *
 * Before the browser starts, because this is readable from the file and a
 * Chromium launch to learn it is seconds spent on nothing. */
if (!Number.isInteger(plan.total_frames)) {
  console.error(`${planPath}: no integer total_frames — Python resolves the timing, not this file`);
  process.exit(1);
}
const fps = plan.fps;
const frames = plan.total_frames;

/* The viewport is the FORMAT the plan declares, and for the same reason the
 * frame count is: Python resolves it, and a second answer here is a second
 * answer that can disagree. A `--format wide` that rendered 1080x1920 would be
 * an mp4 nobody could tell apart from a correct one without opening it. */
const fmt = plan.format;
if (!fmt || !Number.isInteger(fmt.w) || !Number.isInteger(fmt.h)) {
  console.error(
    `${planPath}: no integer format.w/format.h — the stage is the format the ` +
      'plan declares, and defaulting it here renders the wrong size in silence',
  );
  process.exit(1);
}

await writeFile(
  join(HERE, '.plan.js'),
  'window.__PLAN = ' + JSON.stringify(plan) + ';\n',
  'utf8',
);
const qs = new URLSearchParams({ plan: '1' });

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: fmt.w, height: fmt.h },
  deviceScaleFactor: 1,
});

const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));

await page.goto('file://' + join(HERE, 'scene.html') + '?' + qs.toString());
await page.evaluate(() => document.body.classList.add('render'));
await page.evaluate(() => document.fonts.ready);

if (errors.length) {
  console.error('page errors:\n  ' + errors.join('\n  '));
  await browser.close();
  process.exit(1);
}

const total = await page.evaluate(() => window.__total);
if (!total) {
  console.error(`no scenes in ${planPath}`);
  await browser.close();
  process.exit(1);
}
console.log(
  `${total.toFixed(2)}s · ${frames} frames @ ${fps}fps · ` +
    `${fmt.name || '?'} ${fmt.w}x${fmt.h}`,
);

const shoot = async (t, path) => {
  await page.evaluate((tt) => window.__seek(tt), t);
  await page.screenshot({ path, type: 'png' });
};

if (at !== null) {
  /* --out here too. A single frame belongs to the episode that produced it as
   * much as a sweep does, and engine/ is a gitignored working area — a frame
   * left there is one nobody finds and nobody cleans up. */
  const dir = outDir || join(HERE, 'probe');
  await mkdir(dir, { recursive: true });
  const p = join(dir, `at-${at}.png`);
  await shoot(at, p);
  console.log(p);
} else if (probe) {
  const dir = outDir || join(HERE, 'probe');
  await rm(dir, { recursive: true, force: true });
  await mkdir(dir, { recursive: true });
  // sample past the midpoint of every scene — that is where a layout bug shows
  const mids = await page.evaluate(() => {
    const out = [];
    let a = 0;
    for (const s of window.__scenes) { out.push(a + s.dur * 0.72); a += s.dur; }
    return out;
  });
  for (let i = 0; i < mids.length; i++) {
    await shoot(mids[i], join(dir, `s${String(i).padStart(2, '0')}.png`));
  }
  console.log(`${mids.length} probe frames → ${dir}`);
} else {
  const dir = outDir || join(HERE, 'frames');
  await rm(dir, { recursive: true, force: true });
  await mkdir(dir, { recursive: true });
  const t0 = Date.now();
  for (let i = 0; i < frames; i++) {
    await shoot(i / fps, join(dir, String(i).padStart(5, '0') + '.png'));
    if (i % 150 === 0 && i) {
      const pct = ((i / frames) * 100).toFixed(0);
      const eta = ((Date.now() - t0) / i) * (frames - i) / 1000;
      console.log(`  ${pct}%  (${i}/${frames})  eta ${eta.toFixed(0)}s`);
    }
  }
  console.log(`done in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}

if (errors.length) console.error('page errors during render:\n  ' + errors.join('\n  '));
await browser.close();
