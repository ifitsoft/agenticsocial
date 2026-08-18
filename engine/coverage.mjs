#!/usr/bin/env node
/**
 * Coverage ledger for The Brief.
 *
 *   node coverage.mjs check gemini spark 911     → has any of this been covered?
 *   node coverage.mjs list                       → every story, newest first
 *   node coverage.mjs list --id                  → just the ids
 *   node coverage.mjs episode 2026-08-14         → one episode's rundown
 *
 * Run `check` against a new day's candidate stories BEFORE writing the script.
 * A hit is not automatically a veto — it means: skip it, or cover it as an
 * explicit update and say what changed.
 *
 * The ledger read is `coverage.json` beside this file. `AGSOC_COVERAGE_JSON`
 * points it somewhere else; that exists so `coverage.test.mjs` can assert
 * against an invented ledger instead of editing the series' real record.
 */
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const LEDGER = process.env.AGSOC_COVERAGE_JSON || join(HERE, 'coverage.json');
const db = JSON.parse(await readFile(LEDGER, 'utf8'));
const [cmd, ...rest] = process.argv.slice(2);

const all = db.episodes.flatMap((e) => e.stories.map((s) => ({ ...s, date: e.date })));
all.sort((a, b) => (a.date < b.date ? 1 : -1));

const haystack = (s) =>
  [s.id, s.title, s.note || '', ...(s.entities || []), ...(s.sources || [])]
    .join(' ')
    .toLowerCase();

/* Separators carry no meaning here and they are the one thing an author and a
 * ledger reliably disagree about. The ledger says `Gemini 3.7 Flash`; a person
 * writing a candidate story says `gemini-3.7`; the id says `gemini-3-7-flash`;
 * and somebody will write `gemini3.7`. A raw substring match made those four
 * different queries, and three of them silently came back empty — a false
 * negative on a check whose entire job is to say "we already told this story".
 *
 * So strip every non-alphanumeric character from BOTH sides and compare what is
 * left. All four spellings become `gemini37…` and find each other.
 *
 * Two things this deliberately is not:
 *
 *   - It is not token equality. Containment is kept, so `watermark` still finds
 *     *watermarking* and `llm` still finds *LiteLLM*. Matching whole tokens
 *     would have fixed `gemini-3.7` and lost those — one silent miss traded for
 *     others, in a check where a miss is the dangerous outcome.
 *   - It is not two comparisons. Collapsing separators to a single space was
 *     tried first, alongside this one; every match it finds this one finds too
 *     (verified by brute force over the whole ledger), so it was dead code
 *     dressed as a second opinion.
 *
 * The cost is false positives, and stripping separators can join across a word
 * boundary: `aiact` now finds *EU AI Act*. That is the direction to be wrong
 * in. A false positive costs the author ten seconds of reading a title that
 * turns out to be unrelated; a false negative costs the series its one rule.
 *
 * `spaced` survives as a TOKENISER — it is how a term is split up for the
 * "related, and not a hit" pointer below — and not as a matcher.
 */
const spaced = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
const squashed = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '');

const matches = (story, term) => {
  const t = squashed(term);
  /* A term of pure punctuation normalises to nothing, and an empty needle is a
   * substring of every string — the loosest possible matcher, arrived at by
   * accident. Nothing matches nothing. */
  if (!t) return false;
  return squashed(haystack(story)).includes(t);
};

if (cmd === 'check') {
  const terms = rest.filter((t) => !t.startsWith('--'));
  if (!terms.length) {
    console.error('usage: node coverage.mjs check <keyword> [keyword...]');
    process.exit(2);
  }
  const scope =
    `${all.length} stories across ${db.episodes.length} episodes ` +
    '(id, title, note, entities, sources), separators ignored';
  let hits = 0;
  for (const term of terms) {
    const found = all.filter((s) => matches(s, term));
    if (!found.length) {
      /* What a miss is allowed to say. The old line was "NOT COVERED. Safe to
       * run as new." — a claim about the world that a string search cannot
       * support, and the exact sentence a blind runner acted on to clear a
       * story this series had run three days earlier. A search that finds
       * nothing knows one thing: the string is not there. The ledger is also
       * hand-written after each episode ships, so absence is bounded twice
       * over. Say both, and do not say "safe". */
      console.log(`\n  "${term}"  — no entry matches this string.`);
      console.log(`     searched ${scope}.`);
      console.log('     That is all it proves. It does not mean the story is new: the ledger');
      console.log('     holds only what a person wrote into it after an episode shipped.');
      /* The step the runner who caught this had to think of unaided: re-run the
       * bare vendor or product word. If a piece of the term is already in the
       * ledger, the tool knows it, so the tool says it. It is a pointer, not a
       * hit — the count below does not move. */
      const parts = [...new Set(spaced(term).split(' '))].filter(
        /* Four characters, not three: a fragment like `pro` out of `v4-pro`
         * matches *profiles* and *improve* and points at nothing. A pointer
         * that is usually noise gets skipped, and then it is not a pointer. */
        (w) => w.length >= 4 && !/^\d+$/.test(w) && spaced(term) !== w,
      );
      const related = parts
        .map((w) => [w, all.filter((s) => matches(s, w)).length])
        .filter(([, n]) => n > 0);
      if (related.length) {
        console.log(
          `     Related, and not a hit: ${related
            .map(([w, n]) => `"${w}" appears in ${n} story(ies)`)
            .join(', ')}. Run those terms and read the titles`,
        );
        console.log('     before you decide this story is a different one.');
      }
      continue;
    }
    hits += found.length;
    console.log(`\n  "${term}"  — ${found.length} prior mention(s):`);
    for (const s of found) {
      console.log(`     ${s.date}  [${s.id}]  ${s.angle}`);
      console.log(`       ${s.title}`);
      if (s.note) console.log(`       note: ${s.note}`);
    }
  }
  console.log(
    hits
      ? `\n  → ${hits} hit(s). Cover these as updates (state what is new) or drop them.\n`
      : `\n  → 0 matches in ${scope}.\n` +
          '    Nothing in the ledger contains these strings. Whether the stories are\n' +
          '    new is a judgement this check cannot make for you.\n'
  );
} else if (cmd === 'episode') {
  const ep = db.episodes.find((e) => e.date === rest[0]);
  if (!ep) {
    console.error(`no episode for ${rest[0]}. Known: ${db.episodes.map((e) => e.date).join(', ')}`);
    process.exit(1);
  }
  console.log(`\n  ${ep.date} · ${ep.video} · ${ep.runtimeSec}s`);
  if (ep.note) console.log(`  ${ep.note}`);
  for (const s of ep.stories) {
    console.log(`\n   [${s.id}]  ${s.act}  (${s.angle})`);
    console.log(`   ${s.title}`);
    console.log(`   sources: ${(s.sources || []).join(', ')}`);
  }
  console.log('');
} else if (cmd === 'list') {
  if (rest.includes('--id')) {
    for (const s of all) console.log(s.id);
  } else {
    let day = '';
    for (const s of all) {
      if (s.date !== day) { day = s.date; console.log(`\n  ${day}`); }
      console.log(`    ${s.update ? 'UPDATE ' : ''}[${s.id}]  ${s.title}`);
    }
    console.log(`\n  ${all.length} stories across ${db.episodes.length} episodes.\n`);
  }
} else {
  console.log(`
  Coverage ledger — ${all.length} stories across ${db.episodes.length} episodes.

    node coverage.mjs check <keywords...>   overlap check before writing a new day
    node coverage.mjs list [--id]           everything covered, newest first
    node coverage.mjs episode <YYYY-MM-DD>  one episode's rundown
`);
}
