---
name: capture
description: Use when the user dumps rough ideas, voice-note transcripts, or a stream of thoughts — turns them into clean agenticsocial sources for later drafting.
---

# Capture: rough input → clean sources

Turn a messy idea dump into one or more agenticsocial sources.

## Workflow
1. Split the input into distinct post-worthy ideas. Merge fragments that
   belong together; drop filler.
2. For each idea, run: `agsoc new "<crisp working title>"`.
   For a long transcript, save it to a file first and use
   `agsoc new "<title>" --file <path>`.
3. Append a short summary of the user's raw thinking to the body of each
   created `source.md` (below the frontmatter) so context isn't lost.
4. Report the created source ids and suggest next steps: `agsoc research <id>`
   for topics needing grounding, or the fanout skill to draft now.

## Hard rules
- Never invent ideas the user didn't express.
- Never run `agsoc approve` or `agsoc post`.
