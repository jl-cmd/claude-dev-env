---
name: cde-create-skill
description: Write or update a portable SKILL.md workflow when pstack requests create-skill on a host without Cursor's built-in skill.
---

# Create a portable skill

State the user-visible outcome and the exact trigger first. Inspect applicable repository instructions and existing skills before adding a new skill.

Create a lowercase, hyphenated skill directory under the project's .claude/skills. Give SKILL.md YAML frontmatter with a matching name and a one-line description that says when to use it. Put the workflow after the frontmatter. Keep supporting scripts and references together with the skill, and use relative links inside it. Add a Codex .agents/skills directory link where needed, preserving existing files.

Use native host tools and capability checks. Give each step a concrete input, action, and observable result. Separate human choices from facts the agent can inspect. Read referenced instructions before using them.

Verify metadata, links, and script behavior. Then invoke the installed skill in the intended host and record the actual result. Distinguish a filesystem check from a native invocation. Keep the scope to the requested workflow.
