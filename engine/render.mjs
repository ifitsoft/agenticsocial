/**
 * Deterministic frame renderer.
 *   node render.mjs --day 2026-08-14         → render every frame to frames/
 *   node render.mjs --day 2026-08-14 --probe → ~1 frame per scene into probe/
 *   node render.mjs --day 2026-08-14 --at 34 → one frame at t=34s into probe/
 *   node render.mjs --day 2026-08-14 --pace 1.05  → override the read-speed knob
 *   node render.mjs --plan <plan.json>       → render a resolved plan instead
 *   node render.mjs --plan <plan.json> --out <dir>  → frames elsewhere
 *   --out also relocates --probe's frames, so probes land beside their episode
 *
 * --plan JSON.parses the plan and writes engine/.plan.js for the page, because
 * fetch and ES modules are both CORS-blocked over file://.
 *
 * --day defaults to today. Frames are written to frames/; encode with ffmpeg
 * (see README) to the-brief-<day>.mp4.
 */
import { chromium } from 'playwright';
import { mkdir, rm } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const FPS = 30;
const argv = process.argv.slice(2);
const flag = (name) => {
  const i = argv.indexOf('--' + name);
  return i > -1 ? argv[i + 1] : null;
};
const probe = argv.includes('--probe');
const at = flag('at') !== null ? Number(flag('at')) : null;
const pace = flag('pace') !== null ? Number(flag('pace')) : null;
const day = flag('day') || new Date().toISOString().slice(0, 10);
const planPath = flag('plan');
const outDir = flag('out');

const qs = new URLSearchParams();
let plan = null;
if (planPath) {
  const { readFile, writeFile } = await import('node:fs/promises');
  plan = JSON.parse(await readFile(planPath, 'utf8'));
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

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1080, height: 1920 },
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
  console.error(planPath ? `no scenes in ${planPath}` : `no scenes loaded — is content/${day}.js present?`);
  await browser.close();
  process.exit(1);
}
/* Frame count and rate come from the PLAN, never from arithmetic here.
 * Python resolves every time in the episode (D-007) and plan.json already
 * carries `fps` and `total_frames`; recomputing them is a second answer to a
 * question that has one, and the two disagree at the rounding boundary — which
 * reaches a viewer as a video that stops one frame early. Refused rather than
 * defaulted: a plan without a frame count is a plan this cannot render, and a
 * fallback here would be the arithmetic coming straight back. */
if (plan && !Number.isInteger(plan.total_frames)) {
  console.error(`${planPath}: no integer total_frames — Python resolves the timing, not this file`);
  await browser.close();
  process.exit(1);
}
const fps = plan ? plan.fps : FPS;
const frames = plan ? plan.total_frames : Math.round(total * FPS);
console.log(`${day} · ${total.toFixed(2)}s · ${frames} frames @ ${fps}fps`);

const shoot = async (t, path) => {
  await page.evaluate((tt) => window.__seek(tt), t);
  await page.screenshot({ path, type: 'png' });
};

if (at !== null) {
  await mkdir(join(HERE, 'probe'), { recursive: true });
  const p = join(HERE, 'probe', `at-${at}.png`);
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
