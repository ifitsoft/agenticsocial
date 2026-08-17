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
