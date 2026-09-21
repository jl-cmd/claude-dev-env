# No Contrast Framing

**When this applies:** Every sentence a person reads. A chat reply, a commit
message, a pull request title or body, a review comment, an issue, a rule file,
a document, a plan, a memory file.

## Rule

State what is true. Leave the rejected reading out.

A contrast defines its subject against something the writer already decided
against, so the reader carries two readings where one would do, and the second
one is the writer's own discarded draft. The sentence says more and shows less.

Six forms carry the whole ban. Each row names the form the check reports.

| Form | Shape | Write this |
|---|---|---|
| `trailing-comma-not` | `a diff regression, not shared infrastructure` | `a diff regression` |
| `corrective-it-is-not` | `it is not a flake, it is a bug` | `a bug`, then the evidence that shows it |
| `substitution-rather-than` | `park it rather than fix it` | `park it` |
| `additive-not-just` | `not just for today` | the point the sentence was building toward |
| `comparative-ranking` | `being precise matters more than trying to cover them` | `be precise about these three` |
| `substitution-as-opposed-to` | `a warning as opposed to a failure` | `a warning` |

A comparison of quantities stays. "The function runs more than 30 lines" counts
lines. The ban covers the comparison that ranks one course of action over
another the writer is turning down.

Three shapes stay quiet by design. A backticked span or a fenced block carries
an example, so the check blanks it first. A line opening with `>` quotes
someone else, whose words are theirs to write. A sentence already carrying a
bare `not` before the comma is listing items, as in "not in chat, not in a
commit message", so only a first `, not` reports. A release automation body
passes the post linter untouched, since the bot builds it from commit subjects
and reads it back as machine input.

When the sentence thins after the contrast comes out, the missing piece is
evidence. Name it: the failing check, the log line, the measured number, the
file and the line.

## Where it is enforced

| Surface | What runs |
|---|---|
| Authored Markdown in the repository | The staged policy lint's `contrast-framing` rule, on every changed file, graded against the file's prior text |
| A pull request or issue title and body, and a comment | `scripts/durable_post_lint.py`, which every post passes through before it reaches GitHub |
| A chat reply | The writer, reading the sentence back before sending |

The pattern list lives in
`scripts/dev_env_scripts_constants/contrast_framing_constants.py`, and both
lints read that one list. A synchronization test requires a row in the table
above for every form the list carries.

A chat reply reaches no check, so the same list is what the writer reads the
sentence against: a comma followed by `not`, a `rather than`, a `not just`, a
ranking of one thing over another.

## Sibling rules

| Rule | Role |
|---|---|
| [`asd-ste100-language.md`](asd-ste100-language.md) | Plain word choice, sentence style, and tone |
| [`correction-lens.md`](correction-lens.md) | Every correction becomes a control at the highest layer that can hold it |
| [`research-mode.md`](research-mode.md) | A claim carries its source |
