---
name: fanout
description: Use when the user wants to turn an agenticsocial source into platform drafts — reads the voice profile and research brief, writes variants, and stops at in_review for human approval.
---

# Fanout: source → platform variants

You are drafting social content from a source in an agenticsocial workspace.

## Hard rules
- NEVER run `agsoc approve` or `agsoc post`. Your job ends at `in_review`.
- ALWAYS read `voice.md` before writing a single word, and follow its
  per-platform rules exactly.
- If `brief.md` exists in the source directory, ground claims in it and
  keep source URLs handy for reference links.

## Workflow
1. Find the source: `agsoc list`, then read `workspace/sources/<id>/source.md`
   (and `brief.md` if present).
2. Read `workspace/voice.md`.
3. Draft the X variant at `workspace/sources/<id>/x.md`:
   - YAML frontmatter: `platform: x`, `status: draft`, `approved_at: null`,
     `posted_url: null`, `posted_at: null`, `posted_ids: []`
   - Body: tweets separated by `---tweet---` on its own line.
   - The first tweet is the hook. Write 2–3 alternative hooks as an HTML
     comment (`<!-- alt hooks: ... -->`) at the end of the file so the user
     can swap.
   - Keep every tweet ≤ 280 chars (URLs count as 23). Check with
     `agsoc review <id>` — fix anything flagged.
4. Set `status: in_review` in the frontmatter when the draft is ready.
5. Tell the user: review with `agsoc review <id>`, approve with
   `agsoc approve <id>`, then `agsoc post <id>`.
