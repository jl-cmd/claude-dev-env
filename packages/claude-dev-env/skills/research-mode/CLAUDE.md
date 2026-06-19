# research-mode

Activates three anti-hallucination constraints: cite every claim, say "I don't know" when evidence is lacking, and quote directly from source documents.

**Trigger:** "research mode", "toggle research", `/research-mode`.

## Purpose

Enforces factual accuracy for research tasks by requiring citations and explicit uncertainty. Stays active until the user exits with "exit research mode".

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | The complete skill — three constraints, source authority hierarchy, exit condition. No companion files. |

## Three active constraints (all simultaneous)

1. **Say "I don't know"** when no credible source backs a claim.
2. **Verify with citations** — every recommendation cites a specific source (project file, URL, named expert, or official docs).
3. **Direct quotes for factual grounding** — extract actual text before analyzing; ground in word-for-word quotes.

## Source authority hierarchy

1. Official vendor/creator documentation
2. Files in the current project
3. Academic papers, named researchers
4. Reputable external sources with URLs
5. Blog posts and community content (lowest; never cited alone when official docs exist)

## Conventions

- This mode is not the default; it applies only after the trigger fires.
- Creative thinking and brainstorming are out of scope for this mode.
- The global `~/.claude/rules/research-mode.md` carries the same three constraints as always-on background rules; this skill makes them explicit and surfaced during the session.
