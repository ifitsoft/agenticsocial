# Phase 1 — Series & episode scaffolding

Creates the on-disk structure and status machine for video series and episodes,
so later phases have somewhere to write and a lifecycle to move through.

**Spec:** `docs/superpowers/specs/2026-08-15-agenticsocial-video-mvp-design.md`
**Plan:** `docs/superpowers/plans/2026-08-16-phase-01-scaffolding.md`
**Roadmap:** `docs/superpowers/plans/2026-08-16-video-mvp-roadmap.md`

---

## What you can do after this merges

```bash
agsoc series new the-brief --name "The Brief"
agsoc video new 2026-08-14 --series the-brief
agsoc series list
agsoc video list --series the-brief
```

That produces the spec §5 layout — `series.toml`, `coverage.json`,
`episodes/<id>/{script.yaml,sources/,out/,probe/}` — and a status machine in
which **the only path to `rendering` runs through `approved`.**

No video yet. Phase 1.5 (next) renders a hand-written three-beat script to a
watchable MP4.

## What's in it

| Area | |
|---|---|
| `src/agenticsocial/video/models.py` | `Series`, `Episode`, `SeriesError`, `EpisodeError` |
| `src/agenticsocial/video/series.py` | `series.toml` scaffolding and loading |
| `src/agenticsocial/video/episode.py` | episode directories, status lifecycle, `script.yaml` I/O |
| `src/agenticsocial/video/cli.py` | `agsoc series` / `agsoc video` command groups |
| `src/agenticsocial/models.py` | `RENDERING`/`RENDERED` states, `VIDEO_TRANSITIONS`, table-aware transition checks |
| `engine/` | the render engine, **moved out of the gitignored `workspace/`** |

The text pipeline is unchanged and its tests are untouched.

## Two things a reviewer should look at first

**1. `engine/` is now in version control.** `workspace/` is gitignored wholesale,
so ~1,500 lines of hand-written engine source (`engine.js`, `scene.html`,
`render.mjs`, `content/*.js`) had no history and Phase 4 could not have modified
it on a branch. Moved intact; output (`*.mp4`, `frames/`, `probe/`,
`node_modules/`) stays ignored. **Repo is still 7.89 KiB with zero media tracked.**

**2. `script.yaml` is a two-document YAML file, and Phase 1 never parses the
second one.** Metadata is document 1; beats are document 2, split textually and
re-emitted byte-for-byte. This is load-bearing: spec §10 binds approval to
`script_sha256`, and the storyboard skill writes comments and formatting that
`safe_dump` would destroy. Four tasks went into making that guarantee true —
`DECISIONS.md` D-026, D-027, D-031, D-033.

⚠️ **Do not read `script.yaml` with `agenticsocial.frontmatter.parse`.** It will
appear to work, returning correct metadata and the beats as an unparsed string.
That trap is documented in `episode.py`'s module docstring.

## How it was built

Three roles, separated: a project leader who writes briefs and never writes
feature code; a fresh implementer per task working strictly TDD; and a QA
reviewer that never sees the implementer's report, so it reviews the code rather
than the explanation.

Every task landed **two commits — failing tests, then implementation** — so the
RED phase is verifiable from history rather than from a report.

Four planned tasks became fourteen. Every extra one came from a defect found by
an implementer or a reviewer; none from scope drift. The full record is in
`docs/superpowers/worklog/video/` — briefs, reports with pasted RED/GREEN
evidence, reviews, and 49 numbered decisions.

## What the review found

The phase-gate review ran **87 mutants** across four modules and returned
*merge-after-fixes*; those fixes are in. `series.py` specifically: 34 mutants,
30 killed. **No workspace escape is reachable with any string an operator can
type.**

Findings that would have shipped as real harm, all caught before merge:

- **An approval-gate bypass.** `draft → rendering` passed all 112 tests at the
  time; a mutation-testing pass found it.
- **A second gate bypass via a stale object** — `set_status` gated on the
  in-memory status while writing against the disk file.
- **Config corruption that blamed the operator.** A quote or emoji in `--name`
  corrupted both `series.toml` and `coverage.json`, reported it as "malformed
  series.toml", and left a partial directory that blocked the obvious retry.
- **A workspace escape.** `--series ../../outside` wrote a real episode outside
  the workspace.
- **Silent data loss.** Beats written as a bare YAML sequence were replaced with
  `beats: []`; separately, mixed line endings ate the first byte of the beats
  document while leaving a file that still parsed.

## Known and deliberately deferred

Recorded in `DECISIONS.md` D-040 and D-042, carried to Phase 2:

- `%YAML` directives, leading blank lines, a missing leading `---`, and UTF-8
  BOMs in `script.yaml` raise `EpisodeError` though PyYAML accepts them
- `tolerance_sec`, `name`, `byline`, `register` and `design.*` accept wrong types
- a symlinked series or `episodes/` directory can write outside the workspace —
  **accepted deliberately** (D-041): planting the symlink needs write access that
  already permits writing anywhere, and symlinking to another volume is what an
  operator with 27 MB renders actually does
- 12 remaining `series.py` / `episode.py` asymmetries, including two separate
  `64` constants that will drift

None causes harm; each produces a clear error or affects only machine-written
data. The line drawn for this gate: **fix what causes harm before it, fix what
causes confusion after.**

## Test plan

`uv run pytest` — **319 passed**, no network, no new dependencies.

Manual smoke test, verified before merge:

```bash
export AGSOC_WORKSPACE=/tmp/demo/workspace
uv run agsoc init /tmp/demo/workspace
uv run agsoc series new the-brief --name "The Brief"
uv run agsoc video new 2026-08-14 --series the-brief
uv run agsoc series list && uv run agsoc video list --series the-brief
```

Worth trying to break: nonsense in `--series`, a URL as an episode id,
`series.toml` saved as Latin-1, an emoji in `--name`, a directory chmod'd to 000.
Every one of those was a real bug at some point in this phase.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
