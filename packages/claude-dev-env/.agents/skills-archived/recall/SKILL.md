---
name: recall
description: "Retrieve prior session context and decisions from Obsidian vault for the current project."
argument-hint: "[search query or project name]"
---

# Recall

Search the Obsidian vault for prior session context, decisions, research, and gotchas relevant to the current task.

## Instructions

1. **Determine search query.** If `$ARGUMENTS` is provided, use it as the search query. Otherwise, infer the project name from the current conversation context (git remote, working directory, or topic being discussed).

2. **Search by frontmatter first.** Use `mcp__obsidian__search_notes` with `searchFrontmatter: true` and the project name. This finds session reports and decision notes tagged with the project.

3. **Search by content keywords.** If frontmatter search returns few results, search again by content using relevant keywords from the current task (component names, error messages, library names).

4. **Read top matches.** Use `mcp__obsidian__read_note` to read the top 3 most relevant results. Prefer recent notes over older ones. Prefer decision notes and session summaries over raw research.

5. **Present findings with attribution.** For each note, include:
   - Note path and date
   - Project name
   - Relevant excerpts (not the full note unless it's short)
   - Whether any decisions are marked `status: Superseded`

6. **Handle no results honestly.** If no vault history exists for this project, say so explicitly. Do not fabricate or infer history that isn't in the vault.
