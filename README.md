# agenticsocial

Local-first, agent-driven content pipeline. Your agent (Claude Code or any
agentic CLI) gathers research and drafts posts in your voice; a deliberately
dumb CLI (`agsoc`) owns storage, the human approval gate, and publishing to X.
Nothing goes live without you running `agsoc approve`.
Note: approval is per-status, not per-content — if you (or an agent) edit a draft after approving it, run agsoc review and agsoc approve again before posting.

**v1 publishes to X/Twitter.** LinkedIn and YouTube variants are structured-for
and land next.

## Install

```bash
uv tool install agenticsocial   # or: pip install agenticsocial
agsoc init                      # scaffolds ./workspace
```

Then edit `workspace/voice.md` — it's what makes drafts sound like you.

## Connect X

1. Create an app at https://developer.x.com (free tier: ~500 posts/month).
2. In *User authentication settings*: OAuth 2.0, type **Native App** (public
   client), callback URL `http://localhost:8721/callback`.
3. Put the OAuth 2.0 Client ID in `workspace/config.toml` under `[x] client_id`.
4. Run `agsoc auth x` — tokens are stored in your OS keychain, never in files.

## Workflow

```bash
agsoc new "Why we deleted staging"        # capture an idea
agsoc research staging                    # fetch a cited brief into brief.md
# → your agent drafts workspace/sources/<id>/x.md (see skills/)
agsoc review staging                      # per-tweet char counts
agsoc approve staging                     # the human gate
agsoc post staging                        # thread goes live, URL recorded
agsoc post staging --resume               # continue if a thread failed mid-way
```

Content lives in `workspace/` as plain markdown with YAML frontmatter.
Statuses: `draft → in_review → approved → publishing → published | failed`.
Only the CLI moves statuses; agents draft, humans approve.

## Agent skills

`skills/` ships three skills for Claude Code (usable as plain prompts anywhere):

- **capture** — idea dump → clean sources
- **fanout** — source + voice profile + brief → platform drafts, stopping at `in_review`
- **repurpose** — blog post / transcript → platform-native variants

## Development

```bash
uv sync && uv run pytest
```

Apache-2.0. Contributions welcome — especially LinkedIn/YouTube publishers
and the Fanout web UI (see `docs/superpowers/specs/`).
