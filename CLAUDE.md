# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                              # install deps (incl. dev group)
uv run pytest                        # full suite
uv run pytest tests/test_publish.py::test_name -x   # single test
uv run agsoc <cmd>                   # run the CLI from source
```

There is no linter or formatter configured.

## What this is

A local-first content pipeline split in two halves, and the split is the design:

- **The agent** (Claude Code, via `skills/`) does everything judgment-based: capturing ideas, reading the voice profile, drafting variants. It writes markdown files directly.
- **The CLI** (`agsoc`, `src/agenticsocial/`) is deliberately dumb: storage, status transitions, validation, and publishing. It contains no LLM calls — `research.py` fetches and formats, it never summarizes.

Content is plain markdown with YAML frontmatter in `workspace/sources/<id>/` (`source.md`, `x.md`/`linkedin.md`/`youtube.md`, optional `brief.md`). There is no database; the filesystem is the state.

## The approval gate

The status machine in `models.py` (`ALLOWED_TRANSITIONS`) is the core invariant. `draft → in_review → approved → publishing → published | failed`. There is no edge from `in_review` to `publishing`, and only `in_review` reaches `approved`.

**Agents must never run `agsoc approve` or `agsoc post`.** That rule is stated in `skills/fanout/SKILL.md` and it applies to you too when working in this repo. Agent work stops by setting `status: in_review` in a variant's frontmatter.

Approval is per-*status*, not per-content: editing an approved variant does not revoke approval. Any change to a variant body means resetting `status: in_review`.

## Publishing invariants

`x/publish.py::publish_variant` persists `posted_ids` to disk after **every single tweet**, so an interruption mid-thread can never double-post — `--resume` skips `len(posted_ids)` tweets and replies to the last id. Any change there must preserve save-after-each-post.

`cli.py::post` checks `assert_transition(..., PUBLISHING)` *before* touching the keyring, so an unapproved variant fails without prompting for credentials.

All writes go through `workspace.atomic_write` (tempfile + `os.replace`); never write variant files with plain `write_text`.

Tweet length uses `textutils.weighted_length`, not `len()` — X counts every URL as exactly 23 chars. CJK double-weighting is not modeled.

## Auth

OAuth 2.0 PKCE, public-client (no secret). Tokens live only in the OS keychain via `keyring` (service `agenticsocial`, account `x`) — never in `workspace/` or any file. `config.toml` holds only the `client_id`. The callback listener binds `localhost:8721` for exactly one request.

## Workspace resolution

`Workspace.locate()` reads `$AGSOC_WORKSPACE` (default `./workspace`). Tests set it via `monkeypatch.setenv` — that's the fixture pattern in `tests/test_cli.py`.

## Scope

v1 publishes to X only. `linkedin`/`youtube` exist in `PLATFORMS` and the voice template, but `post`/`approve` reject non-`x` platforms. `Status.SCHEDULED` is reserved and has no transitions.

## engine/

The video render engine — a Node subproject, and the target of the video MVP (see `docs/superpowers/specs/2026-08-15-agenticsocial-video-mvp-design.md`). Renders vertical news videos frame-by-frame with Playwright, then encodes with ffmpeg. It has its own README with the render workflow.

**Its invariant is load-bearing:** `window.__seek(t)` must position every element purely as a function of `t` — no CSS keyframes, no `Date.now()`, no randomness. That purity is what makes renders reproducible and any single frame re-creatable for inspection. Anything touching it needs the determinism test green in the same commit.

Tracked: `scene.html`, `engine.js`, `render.mjs`, `coverage.mjs`, `content/*.js`, `coverage.json`, `package*.json`. Ignored: `node_modules/`, `frames/`, `probe/`, `*.mp4`, `*.png`.

Check `coverage.json` via `node coverage.mjs check <terms>` before writing a new episode — the series must never re-tell a story as if it were new.

## workspace/ is gitignored

`workspace/` holds the operator's own content (sources, drafts, and — from Phase 1 onward — series and episodes). It is deliberately not part of this repo. Consequence worth knowing: **nothing under `workspace/` is version controlled or backed up by this repo.** Content worth keeping needs its own git repo or backup.
