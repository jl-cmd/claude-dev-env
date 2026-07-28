# Claims as Quotes

**When this applies:** Agent reports, hand-off artifacts, review verdicts, and PR or commit prose that state what existing code does.

## Rule

Under `research-mode.md`, a factual claim carries its source. This rule sets the shape a claim takes when it decides a design or gates an action: the `path:line` reference, the quoted lines, and the claim sentence travel together. The consumer reads those lines before acting on the claim.

In a chat reply, research-mode's compact citation stands — a linked source name or a `file:line` reference. The three-piece shape binds agent reports, hand-off artifacts, review verdicts, and PR or commit prose.

Claims of this shape:

- "the helper already normalizes this"
- "the gate covers that path"
- "this caller handles the new shape"

Each one settles a design question for whoever reads it, so each one carries its quote. A claim without its quote decides nothing: it is a lead to check, not a fact to build on.

## The failure shape

A paraphrase of code behavior, accepted without the source lines, ships a design premise nobody checked. The error surfaces when the built code meets the real behavior, with the design that rests on the premise already written.

## What a claim carries

| Piece | Shape |
|---|---|
| Reference | `payments/refund.py:88-90` — the path with the line span |
| Quote | The lines word for word, in a fenced block |
| Claim | One sentence naming what those lines settle |

## Examples

**A lead:** "`build_refund` already clamps the refund to the order total, so the new path needs no bound check."

**A fact:** the reference, the lines, and the claim together.

`payments/refund.py:88-90`

```python
def build_refund(order, requested_amount):
    refund_amount = min(requested_amount, order.total)
    return Refund(order_id=order.id, amount=refund_amount)
```

`build_refund` clamps to `order.total` on its one path, so a caller downstream of it needs no bound check.

## What the consumer does

- Read the quoted lines before the sentence that summarizes them.
- Treat a claim that arrives without its quote as a lead: pull the lines yourself, or ask the sender for them, before any design rests on it.
- When the quoted lines say something other than the claim, the lines win.

## Enforcement

The AI review lane and audit skills carry this rule: an agent applies it to the claims a report, a verdict, or a PR body makes about existing code. No blocking hook backs it, because telling a design-deciding claim from background prose needs meaning a regex cannot read.

## Sibling rules

| Rule | Role |
|---|---|
| `research-mode.md` | Names what counts as a citation and grounds a factual claim in word-for-word quotes |
| `hedging-claims.md` | Catches a hedge word standing in for evidence on a claim; this rule catches a claim missing its quote |
| `verify-runtime-state.md` | A verdict about what runs rests on a live probe from this session |
| `falsify-before-green.md` | A check's green counts once the check has been shown red |
| `measurement-denominators.md` | Every count names what it scanned |
