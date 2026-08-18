/* The coverage check must not clear a story the series already told.
 *
 * Run: node coverage.test.mjs
 *
 * The defect this file exists for, measured on the real ledger before it was
 * fixed:
 *
 *     node coverage.mjs check gemini-3.7  ->  "NOT COVERED. Safe to run as new."
 *     node coverage.mjs check gemini      ->  4 prior mention(s)
 *
 * The ledger stores product names with spaces (`Gemini 3.7 Flash`) and the
 * check was a raw substring match, so the hyphenated form an author actually
 * writes missed every one of them — and missed in the direction that reads as
 * permission. CLAUDE.md: *the series must never re-tell a story as if it were
 * new.* A blind runner cleared that exact story on that exact output.
 *
 * Two properties, and each one's negative half:
 *
 *   - A separator-insensitive term finds a spaced ledger entry (R1) — and a
 *     genuinely new story still comes back absent (R1 negative). A matcher that
 *     hits on everything would pass the first half and is the mutant M2.
 *   - The message never claims more than the search supports (R2) — and a real
 *     hit still reads as an unambiguous stop (R2 negative).
 *
 * Everything here drives the real `coverage.mjs` as a subprocess, the way an
 * author runs it. Assertions about *matching* run against the real
 * `engine/coverage.json`, read-only — it is the series' actual record and a
 * test that edited it to go green would be destroying the thing under test.
 * Assertions that need a made-up ledger point the binary at a temp file with
 * AGSOC_COVERAGE_JSON.
 */
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';

const HERE = dirname(fileURLToPath(import.meta.url));
const COVERAGE = join(HERE, 'coverage.mjs');

let failures = 0;
const ok = (label, cond, detail = '') => {
  if (!cond) failures++;
  console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${label}${cond ? '' : ` — ${detail}`}`);
};

const run = (args, ledger) => {
  const env = { ...process.env };
  if (ledger) env.AGSOC_COVERAGE_JSON = ledger;
  const r = spawnSync(process.execPath, [COVERAGE, ...args], { encoding: 'utf8', env });
  return { code: r.status, out: (r.stdout || '') + (r.stderr || '') };
};

/* A hit is any line the tool prints as a prior mention. Counting the marker
 * rather than re-implementing the matcher keeps the oracle independent of the
 * code under test. */
const mentions = (out) => (out.match(/prior mention/g) || []).length;
const hitCount = (out) => {
  const m = out.match(/(\d+) hit\(s\)/);
  return m ? Number(m[1]) : 0;
};

console.log('\n  the regression: a hyphenated product term against a spaced ledger entry\n');

{
  const { code, out } = run(['check', 'gemini-3.7']);
  ok('gemini-3.7 is reported as already covered', mentions(out) === 1 && hitCount(out) > 0, out.trim());
  ok(
    'gemini-3.7 names the episode and the story it collides with',
    out.includes('2026-08-14') && /Gemini 3\.7 Flash/i.test(out),
    out.trim(),
  );
  ok('gemini-3.7 never reads as permission', !/safe to run as new/i.test(out), out.trim());
  ok('check exits 0 — a hit is a verdict to read, not a crash', code === 0, `exit ${code}`);
}

{
  /* The bare vendor term is what the runner had to fall back on. It must not
   * regress: whatever the new matcher does, it may not lose an old hit. */
  const { out } = run(['check', 'gemini']);
  ok('gemini still finds its 4 prior mentions', hitCount(out) === 4, out.trim());
}

{
  /* Separators are noise, in every direction an author might type them. */
  const forms = ['gemini-3.7', 'gemini 3.7', 'Gemini_3.7', 'GEMINI-3-7'];
  const counts = forms.map((f) => hitCount(run(['check', f]).out));
  ok(
    'every separator spelling of the same term gives the same answer',
    counts.every((c) => c === counts[0] && c > 0),
    `${JSON.stringify(forms)} -> ${JSON.stringify(counts)}`,
  );
}

console.log('\n  the negative half: a genuinely new story is still absent\n');

{
  /* M2: a matcher loose enough to find gemini-3.7 by accident finds these too.
   * None of them is in the ledger; deepseek and v4-pro are the brief's own
   * examples of a story the series has never run. */
  const cases = ['deepseek', 'v4-pro', 'qwen3.8-max', 'alibaba', 'nothing-like-this-9x'];
  for (const term of cases) {
    const { out } = run(['check', term]);
    ok(`"${term}" is reported absent, not matched`, hitCount(out) === 0 && mentions(out) === 0, out.trim());
  }
}

{
  /* Punctuation normalises to nothing. An empty needle inside a substring
   * match is true of every string — the loosest possible mutant, reached by
   * accident rather than by choice. */
  const { out } = run(['check', '...']);
  ok('a term made only of separators does not match the whole ledger', hitCount(out) === 0, out.trim());
}

{
  /* The old behaviour that must survive: a term that starts mid-token still
   * hits. Tightening to whole-token equality would fix gemini-3.7 and lose
   * these — a fix that trades one silent miss for two. */
  for (const [term, why] of [
    ['watermark', 'watermarking'],
    ['llm', 'LiteLLM / LLM Gateway'],
  ]) {
    const { out } = run(['check', term]);
    ok(`"${term}" still finds ${why}`, hitCount(out) > 0, out.trim());
  }
}

console.log('\n  the message says what it knows, and no more\n');

{
  const { out } = run(['check', 'deepseek']);
  ok('a miss never says "safe"', !/\bsafe\b/i.test(out), out.trim());
  ok('a miss never says "all clear"', !/all clear/i.test(out), out.trim());
  ok('a miss says what was searched', /searched/i.test(out) && /\d+ stor/i.test(out), out.trim());
  ok(
    'a miss states the limit of what absence proves',
    /does not mean|cannot tell you|not proof/i.test(out),
    out.trim(),
  );
}

{
  /* The near miss the runner found by hand: the term is absent, but a piece of
   * it is all over the ledger. Absent must stay absent — this is a pointer,
   * not a hit — and the pointer is the difference between the tool knowing
   * something and the author having to think of it. */
  const { out } = run(['check', 'gemini-9.9']);
  ok('gemini-9.9 is still absent', hitCount(out) === 0, out.trim());
  ok('gemini-9.9 points at the related "gemini" entries', /gemini/i.test(out) && /related/i.test(out), out.trim());
}

{
  /* R2 negative: a hit is not softened. No "maybe", no "possible" — the
   * instruction is unchanged and it is an instruction. */
  const { out } = run(['check', 'gemini-3.7']);
  ok(
    'a hit still reads as a stop',
    /updates|drop them/i.test(out) && !/might be|possibly|maybe/i.test(out),
    out.trim(),
  );
}

console.log('\n  a made-up ledger, so these assertions cannot depend on the real one\n');

const dir = mkdtempSync(join(tmpdir(), 'agsoc-coverage-'));
const fixture = join(dir, 'coverage.json');
writeFileSync(
  fixture,
  JSON.stringify({
    series: 'Fixture',
    episodes: [
      {
        date: '2026-01-01',
        video: 'fixture.mp4',
        runtimeSec: 1,
        stories: [
          {
            id: 'acme-foo-9-9-ultra',
            title: 'Acme ships Foo 9.9 Ultra',
            act: '01 — The headline',
            angle: 'launch',
            entities: ['Acme', 'Foo 9.9 Ultra'],
            sources: ['acme.example'],
            note: 'A spaced product name, the shape the real ledger uses.',
          },
        ],
      },
    ],
  }),
  'utf8',
);

try {
  ok('a hyphenated term finds the fixture entry', hitCount(run(['check', 'foo-9.9'], fixture).out) === 1);
  ok('a neighbouring version does not', hitCount(run(['check', 'foo-9.8'], fixture).out) === 0);
  ok(
    'the fixture is what was read, not the real ledger',
    run(['check', 'gemini'], fixture).out.includes('gemini') &&
      hitCount(run(['check', 'gemini'], fixture).out) === 0,
  );

  /* The other two subcommands must survive the refactor. */
  const list = run(['list'], fixture);
  ok('list still works', list.code === 0 && list.out.includes('Acme ships Foo 9.9 Ultra'), list.out.trim());
  const ep = run(['episode', '2026-01-01'], fixture);
  ok('episode still works', ep.code === 0 && ep.out.includes('01 — The headline'), ep.out.trim());
  const missing = run(['episode', '1999-09-09'], fixture);
  ok('an unknown episode still exits non-zero', missing.code === 1, `exit ${missing.code}`);
  const usage = run(['check'], fixture);
  ok('check with no terms still exits 2', usage.code === 2, `exit ${usage.code}`);
} finally {
  rmSync(dir, { recursive: true, force: true });
}

console.log(failures ? `\n${failures} FAILURES\n` : '\nthe ledger check cannot be talked past\n');
process.exit(failures ? 1 : 0);
