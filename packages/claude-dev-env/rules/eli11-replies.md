# ELI11 Replies

**Users read about 20% of your words, and 79% of them scan.** Write every reply so the bold words alone tell the whole story.

## Four skim mechanics

1. **Bold keyword first** — open every line and bullet with its load-bearing words in bold. Eyes land on the first words of a line, then fall down the left edge — the [F-pattern](https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content-discovered/).
2. **One idea per line** — a second idea in the same line is invisible to a skimmer.
3. **Conclusion first** — the outcome goes in sentence one. Detail sits below it, or gets cut.
4. **Half the words** — write it, halve it, halve it again. Cap a reply at about 120 words.

**Measured gains** ([NN/g eyetracking](https://www.nngroup.com/articles/how-users-read-on-the-web/)): concise +58%, scannable layout +47%, both together +124%.

## Reply shape

1. **Action first** — when the user must act, open with "Do N things" and numbered click-by-click steps, one short line each.
2. **Outcome first** — when nothing is needed, open with the outcome in one sentence.
3. **Findings** — at most 3 short bullets.
4. **Detail** — only when the user asks.

## Rules

- **One command per block** — a command the user runs goes in its own `bash`-tagged fenced block, so the Run button appears. That tag gives the user a Run button; [`shell-invocation-policy`](shell-invocation-policy.md) stays in charge of the agent's own Bash-tool calls, which run pwsh-only.
- **One line per status** — each background-work update gets a single line.
- **Cut findings first** — when a reply runs long, drop findings and keep the action steps.
- **Skim test** — reading only the bold words tells the whole story.

## Relationship to other rules

- **[`plain-language`](plain-language.md)** owns word choice; this rule owns reply length and shape.
- **`AskUserQuestion`** carries every question to the user, in the same short style.
