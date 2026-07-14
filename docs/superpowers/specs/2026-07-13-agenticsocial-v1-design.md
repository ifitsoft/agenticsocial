# agenticsocial v1 — Design Spec

**Date:** 2026-07-13
**Status:** Approved pending user review
**Product vision reference:** Fanout mockup (`Fanout.dc.html`, Claude Design project `f5aba9ee-afeb-497b-90a5-898e08320781`)

## Summary

agenticsocial is an open-source, local-first content pipeline. A deliberately "dumb" Python CLI (`agsoc`) owns storage, research fetching, credential handling, and publishing. Bundled agent skills let Claude Code (or any agentic CLI the user already runs) do the creative work: developing ideas, drafting in the user's voice, and repurposing one source into per-platform variants ("fan-out").

The CLI makes **no LLM calls**. Intelligence comes from whatever agent drives it.

## Decisions made

| Decision | Choice |
|---|---|
| Form factor | CLI + agent skills (Fanout web UI is v2, layered on the same workspace) |
| Content sources | Web research/trends, user's long-form content, idea capture |
| Posting | Official X API v2, free tier (~500 writes/month) |
| Stack | Python 3.11+, `uv`, `typer`, published to PyPI as `agenticsocial` |
| LLM wiring | Agent-first; CLI is deterministic only |
| Storage | Markdown files with YAML frontmatter in a workspace directory |
| v1 platforms | X/Twitter end-to-end; LinkedIn + YouTube variant types structured-for but not built |

## Domain model (from the Fanout mockup)

- **Source** — raw material: URL/blog post, rough idea, or transcript. Research briefs attach to sources as grounding material.
- **Variant** — a platform-specific rendition generated from a source (X post/thread, LinkedIn post, YouTube metadata pack). Each variant has its own lifecycle:
  `draft → in_review → approved → scheduled → publishing → published | failed`
  (v1 implements all states except `scheduled`, which is reserved for the v2 calendar.)
- **Voice profile** — persona + per-platform rules (e.g. X: no hashtags, ≤280, hook-first) + example posts the user liked. Skills require the agent to read it before drafting.

**Approval gate (locked):** status transitions are enforced only by the CLI. The agent may create and edit variant files freely, but `in_review → approved` requires a human running `agsoc approve`, and only `approved` variants can be posted. Nothing goes live without a human OK.

## Workspace layout

Default `./workspace/`, path configurable, gitignored by default (personal content stays out of the open-source repo; users may version it separately).

```
workspace/
  sources/
    2026-07-13-kill-staging/       # one directory per source
      source.md                    # frontmatter: id, type (url|idea|transcript), title, origin_url, created
      brief.md                     # optional research brief: fetched material with citations
      x.md                         # X variant
      linkedin.md                  # LinkedIn variant (v1.1)
      youtube.md                   # YouTube metadata pack (v1.1)
  voice.md                         # voice profile
  config.toml                      # workspace settings, platform credential references
```

Variant file format (X example):

```yaml
---
platform: x
status: in_review
approved_at: null
posted_url: null
posted_at: null
posted_ids: []        # per-tweet ids for thread resume
---
Tweet 1 text...

---tweet---

Tweet 2 text...
```

Threads are one file split by `---tweet---` so the agent edits a thread as a single document and the CLI publishes chunk-by-chunk.

## CLI surface

```
agsoc init                          # scaffold workspace + voice.md template
agsoc new "title or idea text"      # create a source; --url fetches and attaches origin, --file for transcripts
agsoc research <source> [--query]   # fetch web/RSS/URL material into brief.md with citations (no LLM)
agsoc list [--status in_review]     # table of sources/variants and statuses
agsoc review <source>               # render variant: char counts per tweet, thread preview
agsoc approve <source> [--platform x]
agsoc post <source> [--resume] [--dry-run]
agsoc status                        # workspace overview
agsoc auth x                        # one-time OAuth 2.0 PKCE browser flow
```

`agsoc research` uses deterministic fetching only (DuckDuckGo search, RSS, URL extraction via `trafilatura`); the agent reads and synthesizes the brief.

## X publishing

- Official X API v2, OAuth 2.0 PKCE user-context flow via `agsoc auth x`.
- Tokens stored in the OS keychain (`keyring` library) — never in workspace files or the repo.
- Threads post tweet-by-tweet with reply chaining. `publishing` status is written before the first API call; each posted tweet id is appended to `posted_ids` so a mid-thread failure is detectable and `agsoc post --resume` continues without double-posting.
- Character validation (280 limit, URLs weighted at 23) runs at `review`/`approve` time so failures surface before posting.
- Rate-limit and auth errors print actionable messages (when to retry; re-run `agsoc auth x`).

## Agent skills

Shipped in `skills/` in the repo, installable as a Claude Code plugin; written to be usable as plain prompts with other agentic CLIs.

- **fanout** — take a source (+ brief if present), read `voice.md`, draft the requested variants; include 2–3 alternative hooks as comments for the user to choose from; finish at `in_review` and direct the user to `agsoc review`.
- **capture** — turn a rambling idea dump into one or more clean sources.
- **repurpose** — long-form content (blog post, transcript) → platform variants.

Skills never approve or post.

## Error handling

- All workspace writes are atomic (temp file + rename).
- Invalid status transitions are rejected with a message naming the allowed next states.
- `agsoc post` on a non-approved variant fails loudly.
- Interrupted publishing is resumable (see X publishing above).

## Testing

- `pytest`; unit tests for frontmatter parsing, status-transition enforcement, thread splitting, character counting.
- X client tested against recorded HTTP fixtures (`respx`); no live API in CI.
- `agsoc post --dry-run` exercises the full pipeline without network writes.

## Out of scope for v1 (structured-for)

- Fanout local web UI (v2 — a localhost server rendering the mockup UI over the same workspace files).
- LinkedIn and YouTube publishing (variant file formats defined; `posted` transitions unimplemented).
- Scheduling/calendar (`scheduled` status reserved), analytics, token-expiry cron.
- Embedded LLM mode for non-agent users (possible v2 hybrid).

## Execution note

When implementing this spec, the main session orchestrates; implementation subagents run on Opus models.
