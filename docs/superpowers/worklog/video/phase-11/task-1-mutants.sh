#!/bin/bash
# Phase 11 Task 1 mutation sweep. Each mutant is a one-line edit that makes a
# weaker implementation of the coverage ledger; a KILLED mutant is one the suite
# refuses.
#
# PYTHONDONTWRITEBYTECODE=1 throughout (D-100): the suite is fast enough that
# consecutive mutants land inside one mtime second and CPython would hand the
# harness a stale .pyc — a measurement that has stopped observing the thing it
# measures.
#
# Exit codes are read UNPIPED (D-105).
set -u
cd "$(dirname "$0")/../../../../.." || exit 1
export PYTHONDONTWRITEBYTECODE=1
TMP=$(mktemp -d)
LOG=$TMP/mutants.log
echo "harness scratch: $TMP"
: > $LOG
KILLED=0; SURVIVED=0

mutate() {  # mutate <file> <old> <new>
  python3 - "$1" "$2" "$3" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()
old, new = sys.argv[2], sys.argv[3]
assert old in s, f"mutation anchor not found in {p}: {old[:60]}"
p.write_text(s.replace(old, new, 1))
PY
}

run() {  # run <id> <what> <file> <old> <new> <command...>
  id=$1; what=$2; file=$3; old=$4; new=$5; shift 5
  cp "$file" "$TMP/mut.bak"
  if ! mutate "$file" "$old" "$new"; then
    echo "$id  ANCHOR MISSING — $what" | tee -a $LOG
    cp "$TMP/mut.bak" "$file"; return
  fi
  "$@" > "$TMP/mut.out" 2>&1
  code=$?          # unpiped, D-105
  cp "$TMP/mut.bak" "$file"
  if [ $code -ne 0 ]; then
    KILLED=$((KILLED+1)); echo "$id  KILLED    $what" | tee -a $LOG
    grep -E "FAILED" "$TMP/mut.out" | head -2 | sed 's/^/          /' >> $LOG
  else
    SURVIVED=$((SURVIVED+1)); echo "$id  SURVIVED  $what" | tee -a $LOG
  fi
}

PY_ALL="uv run pytest -q -x"
C=src/agenticsocial/video/coverage.py
L=src/agenticsocial/video/cli.py
S=skills/storyboard/SKILL.md

# --- M1 · the matcher stops being one-directional --------------------------------------
run M1a "the matcher is a raw substring again (D-112's exact defect)" $C \
  '    return t in squashed(haystack(story))' \
  '    return term.lower() in haystack(story).lower()' $PY_ALL
run M1b "the term is normalised and the ledger is not" $C \
  '    return t in squashed(haystack(story))' \
  '    return t in haystack(story).lower()' $PY_ALL
run M1c "matching tightens to whole tokens (watermark loses watermarking)" $C \
  '    return t in squashed(haystack(story))' \
  '    return t in spaced(haystack(story)).split(" ")' $PY_ALL
run M1d "the entities are not searched" $C \
  '    for key in ("entities", "sources"):' \
  '    for key in ("sources",):' $PY_ALL
run M1e "the title is not searched" $C \
  'HAYSTACK_FIELDS = ("id", "title", "note", "act", "angle")' \
  'HAYSTACK_FIELDS = ("id", "note", "act", "angle")' $PY_ALL

# --- M2 · matching so loose that everything hits ---------------------------------------
run M2a "an empty needle matches every story" $C \
  '    if not t:
        return False' \
  '    if not t:
        return True' $PY_ALL
run M2b "every term is a hit" $C \
  '    return t in squashed(haystack(story))' \
  '    return True' $PY_ALL
run M2c "another series' stories are counted as this series' hits" $C \
  '        found = [s for s in stories if matches(s, term)]' \
  '        found = [s for s in stories if matches(s, term)] + [
            s for o in (others or {}).values() for s in all_stories(o) if matches(s, term)
        ]' $PY_ALL

# --- M3 · the word "safe" returns -------------------------------------------------------
run M3a "a miss says it is safe to run as new" $L \
  "            typer.echo(f'\\n  \"{result.term}\"  — no entry matches this string.')" \
  "            typer.echo(f'\\n  \"{result.term}\"  — NOT COVERED. Safe to run as new.')" $PY_ALL
run M3b "the bound on what absence proves is dropped" $L \
  '            typer.echo(
                "     That is all it proves. It does not mean the story is new: the ledger"
            )' \
  '            pass' $PY_ALL
run M3c "the miss no longer says what was searched" $L \
  '            typer.echo(f"     searched {scope}.")' \
  '            pass' $PY_ALL
run M3d "the related pointer is counted as a hit" $C \
  '                related=[] if found else related_terms(stories, term),' \
  '                related=[],' $PY_ALL

# --- M4 · a real hit softened into a maybe ----------------------------------------------
run M4a "the hit line becomes a suggestion" $L \
  '            f"\n  → {hits} hit(s). Cover these as updates (state what is new) "
            "or drop them.\n"' \
  '            f"\n  → {hits} hit(s). These might be related; maybe cover as updates.\n"' $PY_ALL
run M4b "a hit stops naming the episode it collides with" $L \
  "                typer.echo(f\"     {story['date']}  [{story.get('id', '?')}]  {label}\")" \
  "                pass" $PY_ALL
run M4c "a hit stops printing the title the author has to read" $L \
  "                typer.echo(f\"       {story.get('title', '')}\")" \
  "                pass" $PY_ALL

# --- M5 · migration drops an entry ------------------------------------------------------
run M5a "a migrated episode is counted and not written" $C \
  '            episodes.append(ep)
            moved.append(date)' \
  '            moved.append(date)' $PY_ALL
run M5b "the last story of each episode is left behind" $C \
  '            episodes.append(ep)' \
  '            episodes.append({**ep, "stories": ep.get("stories", [])[:-1]})' $PY_ALL
run M5c "a date that differs is silently overwritten, no refusal at all" $C \
  "        elif mine == ep:
            skipped.append(date)" \
  "        elif True:
            episodes[episodes.index(mine)] = ep
            skipped.append(date)" $PY_ALL
run M5d "the arithmetic that must balance is not checked" $C \
  '    if after_stories != before_stories + moved_stories:' \
  '    if False:' $PY_ALL

# --- M6 · migration duplicates into every series ---------------------------------------
run M6a "the migration is copied into every series in the workspace" $L \
  '        coverage_mod.save_ledger(s, merged)
    except OSError as e:
        raise _fail(f"cannot write {coverage_mod.LEDGER_NAME}: {e}")
    typer.echo(
        f"\n  the source file is not modified' \
  '        for slug in series_slugs(ws):
            coverage_mod.save_ledger(load_series(ws, slug), merged)
    except OSError as e:
        raise _fail(f"cannot write {coverage_mod.LEDGER_NAME}: {e}")
    typer.echo(
        f"\n  the source file is not modified' $PY_ALL

# --- M7 · the node command comes back, or the doc still points at it --------------------
# A file resurrection rather than an edit: the retirement is a claim about what
# is NOT there, so the mutant has to put it back. Removed again immediately.
echo '// restored' > engine/coverage.mjs
$PY_ALL > "$TMP/mut.out" 2>&1
code=$?          # unpiped, D-105
rm -f engine/coverage.mjs
if [ $code -ne 0 ]; then
  KILLED=$((KILLED+1)); echo "M7a  KILLED    the retired node command is restored" | tee -a $LOG
else
  SURVIVED=$((SURVIVED+1)); echo "M7a  SURVIVED  the retired node command is restored" | tee -a $LOG
fi
run M7b "the skill sends the author back to the node command" $S \
  'uv run agsoc coverage check <keyword> [keyword...] --series <slug>' \
  'node engine/coverage.mjs check <keyword> [keyword...]' $PY_ALL

# --- M8 · the round trip: add writes what check cannot find -----------------------------
run M8a "add writes its stories under a key check does not read" $C \
  '    entry["stories"] = derive_stories(script, _manifest(episode))' \
  '    entry["items"] = derive_stories(script, _manifest(episode))
    entry["stories"] = []' $PY_ALL
run M8b "add normalises ids differently from check (digits dropped)" $C \
  '    s = spaced(text).replace(" ", "-")' \
  '    s = re.sub(r"[0-9]", "", spaced(text)).replace(" ", "-")' $PY_ALL
run M8c "add records no entities" $C \
  '    return sorted({a.value for a in atoms_of(beat_text(beat)) if a.kind == "entity"})' \
  '    return []' $PY_ALL
run M8d "add records no title" $C \
  '        title = text or f"{beat.type} beat {beat.index + 1}"' \
  '        title = f"{beat.type} beat {beat.index + 1}"' $PY_ALL
run M8e "add records the chrome beats too" $C \
  '        if beat.type in EXEMPT_TYPES:
            continue' \
  '        if False:
            continue' $PY_ALL
run M8f "add records the source key and not the host" $C \
  '        if host:
            out.append(host)' \
  '        pass' $PY_ALL

# --- M9 · R5: add records after render, and only the operator runs it -------------------
run M9a "an unrendered episode can be recorded" $C \
  '    if episode.status is not Status.RENDERED:' \
  '    if False:' $PY_ALL
run M9b "an episode marked rendered with no record is accepted" $C \
  '    if not render_record(episode):' \
  '    if False:' $PY_ALL
run M9c "the same episode can be recorded twice" $C \
  '    if existing and not replace:' \
  '    if False:' $PY_ALL
run M9d "--dry-run writes after all" $L \
  '    if dry_run:
        typer.echo("\n  --dry-run: nothing written.\n")
        return
    try:
        coverage_mod.save_ledger(s, merged)
    except OSError as e:
        raise _fail(f"cannot write {coverage_mod.LEDGER_NAME}: {e}")
    stories, episodes = coverage_mod.counts(merged)' \
  '    try:
        coverage_mod.save_ledger(s, merged)
    except OSError as e:
        raise _fail(f"cannot write {coverage_mod.LEDGER_NAME}: {e}")
    if dry_run:
        typer.echo("\n  --dry-run: nothing written.\n")
        return
    stories, episodes = coverage_mod.counts(merged)' $PY_ALL
run M9e "the screen stops saying the ledger holds what was rendered" $L \
  '        "  what it records is what was RENDERED. If this episode is never "' \
  '        "  what it records is what happened. If this episode is never "' $PY_ALL

# --- M10 · the read-only commands --------------------------------------------------------
run M10a "an unknown episode exits 0" $L \
  '        raise _fail(f"no episode for {date} in `{s.slug}`. Known: {known}")' \
  '        return' $PY_ALL
run M10b "a broken neighbouring series takes the check down" $L \
  '        except (SeriesError, coverage_mod.CoverageError, OSError):
            continue' \
  '        except ():
            continue' $PY_ALL
run M10c "the ledger is written non-atomically" $C \
  '    atomic_write(
        ledger_path(series),
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n",
    )' \
  '    ledger_path(series).write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )' $PY_ALL

echo "----- $((KILLED+SURVIVED)) mutants · $KILLED killed · $SURVIVED survived" | tee -a $LOG
