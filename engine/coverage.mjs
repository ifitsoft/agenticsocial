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
 */
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const db = JSON.parse(await readFile(join(HERE, 'coverage.json'), 'utf8'));
const [cmd, ...rest] = process.argv.slice(2);

const all = db.episodes.flatMap((e) => e.stories.map((s) => ({ ...s, date: e.date })));
all.sort((a, b) => (a.date < b.date ? 1 : -1));

const haystack = (s) =>
  [s.id, s.title, s.note || '', ...(s.entities || []), ...(s.sources || [])]
    .join(' ')
    .toLowerCase();

if (cmd === 'check') {
  const terms = rest.filter((t) => !t.startsWith('--')).map((t) => t.toLowerCase());
  if (!terms.length) {
    console.error('usage: node coverage.mjs check <keyword> [keyword...]');
    process.exit(2);
  }
  let hits = 0;
  for (const term of terms) {
    const found = all.filter((s) => haystack(s).includes(term));
    if (!found.length) {
      console.log(`\n  "${term}"  — NOT COVERED. Safe to run as new.`);
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
      : '\n  → No overlap. All clear.\n'
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
