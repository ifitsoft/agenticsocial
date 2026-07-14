---
name: repurpose
description: Use when the user has long-form content (blog post URL, article, video transcript) to turn into platform-native social posts via agenticsocial.
---

# Repurpose: long-form → platform variants

Turn existing long-form content into social variants.

## Workflow
1. Create the source:
   - Blog/article: `agsoc new "<title>" --url <url>` then `agsoc research <id>`
     (this also extracts the article text into `brief.md`).
   - Transcript: `agsoc new "<title>" --file <transcript path>`.
2. Read the extracted content. Identify the 1–3 strongest standalone
   insights — a thread carries ONE insight, not a summary of everything.
3. Follow the fanout skill from step 2 to draft variants in the user's voice.
4. Include a link back to the original in the final tweet.

## Hard rules
- Platform-native beats faithful: rewrite, don't excerpt.
- Never run `agsoc approve` or `agsoc post`.
