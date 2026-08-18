#!/bin/bash
# Phase 10 Task 1 mutation sweep. Each mutant is a one-line edit that makes a
# weaker implementation; a KILLED mutant is one the suite refuses.
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

# apply <file> <python-expression-file-rewrite>
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
    grep -E "FAILED|FAIL " "$TMP/mut.out" | head -2 | sed 's/^/          /' >> $LOG
  else
    SURVIVED=$((SURVIVED+1)); echo "$id  SURVIVED  $what" | tee -a $LOG
  fi
}

PY_ALL="uv run pytest -q -x"
NODE_FMT="node engine/format.test.mjs"
NODE_DET="node engine/determinism.test.mjs"

P=src/agenticsocial/video/plan.py
S=src/agenticsocial/video/series.py
C=src/agenticsocial/video/cli.py
E=engine/engine.js
B=engine/planbuild.js
R=engine/render.mjs

# --- M7 · the wide format is not wide -------------------------------------------------
run M7a "wide declares the vertical stage (1080x1920)" $P \
  '"w": 1920,
        "h": 1080,' '"w": 1080,
        "h": 1920,' $PY_ALL
run M7b "the plan drops the format it was built for" $P \
  '"format": {"name": fmt, **FORMATS[fmt]},' '"format": {"name": fmt, **FORMATS["vertical"]},' $PY_ALL
run M7c "render.mjs ignores plan.format and hardcodes the viewport" $R \
  'viewport: { width: fmt.w, height: fmt.h },' 'viewport: { width: 1080, height: 1920 },' $NODE_FMT

# --- M2 · the format changes timing ---------------------------------------------------
run M2a "wide runs at a different pace" $P \
  'hold = round(beat.hold * pace, 3)' 'hold = round(beat.hold * pace * (0.9 if fmt == "wide" else 1), 3)' $PY_ALL

# --- M8 · vertical moves --------------------------------------------------------------
run M8a "vertical's safe area silently moves to §9's numbers" $P \
  '"safe_top": 400,
        "safe_bottom": 1580,' '"safe_top": 430,
        "safe_bottom": 1560,' $PY_ALL
run M8b "every format writes plan-vertical.json" $P \
  'path = episode.out_dir / f"plan-{fmt}.json"' 'path = episode.out_dir / "plan-vertical.json"' $PY_ALL

# --- M1 · the two contexts stop being one system --------------------------------------
run M1a "the stage never declares its measure" $E \
  "st.dataset.measure=FMT.measure;" "st.dataset.measure='narrow';" $NODE_FMT
run M1b "the scale is declared and never applied" $E \
  "st.style.setProperty('--fmt-scale',String(s));" "st.style.setProperty('--fmt-scale','1');" $NODE_FMT
run M1c "planbuild stops handing the format over" $B \
  'format(plan.format);' '/* format(plan.format); */' $PY_ALL

# --- M4/M5 · overflow is not loud -----------------------------------------------------
run M4a "overflow is measured and never refused" $E \
  'if(!bad.length)return;' 'if(bad.length>=0)return;' $NODE_FMT
run M4b "the fit check runs in the narrow context only" $E \
  'for(let i=0;i<SCENES.length;i++){
    const over=fitOf(i);' "for(let i=0;i<SCENES.length&&FMT.measure==='narrow';i++){
    const over=fitOf(i);" $NODE_FMT
run M4c "only the bottom overflow is looked for" $E \
  "if(above>FIT_TOL)parts.push(above+'px above');" "if(false)parts.push(above+'px above');" $NODE_FMT
run M4d "a word past the measure is not overflow" $E \
  "if(side>FIT_TOL)parts.push(side+'px past the measure');" "if(false)parts.push(side+'px past the measure');" $NODE_FMT
run M4e "the tolerance is widened until nothing overflows" $E \
  'const FIT_TOL=2;' 'const FIT_TOL=2000;' $NODE_FMT
run M4f "the refusal never reaches the runner (it is only drawn in #ui)" $E \
  'throw new Error(msg);' 'console.error(msg);' $NODE_FMT

# --- M6 · crying wolf -----------------------------------------------------------------
run M6a "fit is measured before the animations land (p=0)" $E \
  'for(const a of ANIMS)a.fn(1);' 'for(const a of ANIMS)a.fn(0);' $NODE_FMT

# --- M3 · purity ----------------------------------------------------------------------
run M3a "the fit check leaves its last scene on the stage" $E \
  "CUR=-1;ANIMS=[];stageScenes.innerHTML='';SC=null;" "/* left as measured */" $NODE_DET

# --- M9 · the render implies the format was approved ----------------------------------
run M9a "the format line stops saying it was not approved" $C \
  'f"{fmt} · {size}chosen at render time and NOT part of the approval — "' \
  'f"{fmt} · {size}"' $PY_ALL
run M9b "the probe screen never names the format" $C \
  'typer.echo(_detail("format", _format_line(fmt)))' 'pass' $PY_ALL
run M9c "the render screen never names the format" $C \
  'typer.echo(_detail("format", _format_line(record["format"])))' 'pass' $PY_ALL

# --- M10 · type_family / type_scale ----------------------------------------------------
run M10a "the retired token is copied into the plan again" $S \
  'return {k: v for k, v in design.items() if k not in RETIRED_DESIGN_TOKENS}' \
  'return dict(design)' $PY_ALL
run M10b "the approval binds a token that reaches no frame" $P \
  '"design": lambda s: render_design(s.design),' '"design": lambda s: dict(s.design),' $PY_ALL
run M10c "an unknown type_scale is accepted in Python" $S \
  'if scale is not None and scale not in TYPE_SCALES:' 'if False:' $PY_ALL
run M10d "an unknown type_scale is accepted in the renderer" $E \
  'if(!Object.prototype.hasOwnProperty.call(TYPE_SCALES,name)){' 'if(false){' $NODE_FMT
run M10e "type_scale is read and ignored" $E \
  'TYPE_SCALE=TYPE_SCALES[name];' 'TYPE_SCALE=1;' $NODE_FMT
run M10f "a series that still declares type_family is refused" $S \
  'def warn_retired_design(design: dict, where: Any) -> None:' \
  'def warn_retired_design(design: dict, where: Any) -> None:
    if set(design) & set(RETIRED_DESIGN_TOKENS):
        raise SeriesError(f"{where}: retired design token")' $PY_ALL

echo "----- $((KILLED+SURVIVED)) mutants · $KILLED killed · $SURVIVED survived" | tee -a $LOG
