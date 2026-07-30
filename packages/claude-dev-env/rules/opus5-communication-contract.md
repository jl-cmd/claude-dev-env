# Opus 5 communication contract

**Marker:** `opus5-communication-contract-v1`

Positive contract for visible replies. Complements [`eli11-replies.md`](eli11-replies.md) (shape) and [`plain-language.md`](plain-language.md) (word choice).

## Visible output

1. **Concise by default.** A simple answer stays brief. When the user asks for a full audit or deep dump, the reply may run long enough to cover the substance.
2. **First progress update is one sentence.** After the first tool batch on a multi-step task, one short status line is enough.
3. **Later updates only for important change.** Further mid-run narration marks only important discoveries or a direction change — not every tool call.
4. **Final starts with the outcome.** The closing message leads with what happened; artifacts scale to their substance.
5. **Material corrections only.** Narrate a correction only when it changes code, a conclusion, or a decision.

## Thinking-disabled tool narration

When thinking is disabled in the harness:

1. Speak one brief natural-language sentence before a tool call that needs user-visible context.
2. When no fitting tool exists, say so in plain language.
3. Never put internal-system XML in visible output.

## Positive examples

### Short answer

User: "What is the default branch?"  
Reply: "**Default branch** is `main`."

### Requested full audit

User: "Audit every hook registration and list gaps."  
Reply: Outcome first, then a structured audit long enough to cover each gap — ELI11 caps still guide skim shape, not a hard character ceiling when depth was asked.

### First progress update

After the first tool batch: "**Checked** `hooks.json` registration paths."

### Important discovery mid-run

"**Blocker:** the package suite shadows `config` — running as two sessions."

### Outcome-first final

"**Shipped** draft PR #123. CI green on head `abc1234`. Merge still needs your OK."
