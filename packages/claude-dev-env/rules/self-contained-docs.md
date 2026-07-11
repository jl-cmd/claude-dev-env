# Self-Contained Documentation

**When this applies:** All generated artifacts — gists, decision docs, PR descriptions, issue bodies, plans, SKILL.md content. Exception: Obsidian session logs (intentionally conversation-scoped).

## Rule

Every document must be fully self-contained. A reader with zero prior context must understand every statement without needing access to the conversation that produced it.

## Patterns to Catch and Replace

| Pattern | Example | Fix |
|---|---|---|
| References to options/choices discussed in conversation | "This is not Option A from the original framing" | Delete the sentence, or restate the decision on its own terms |
| "As discussed" / "as we decided" / "from the prior session" | "As discussed, we'll use embeddings" | "Sref matching uses sentence-transformer embeddings" |
| Pronouns pointing to conversation context | "This approach addresses the concerns raised earlier" | State what the concerns were inline, or delete |
| Relative framing ("instead of X") where X was only discussed verbally | "Instead of the three options considered" | State the chosen approach directly without referencing alternatives the reader can't see |
| Session-specific sequencing | "After Round 3 we decided..." | State the decision as a fact |
