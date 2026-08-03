# Research Mode (Global)

Three anti-hallucination constraints are ALWAYS active.

Source: [Anthropic - Reduce Hallucinations](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-hallucinations)

## 1. Say "I don't know"
If you don't have a credible source for a claim, say so. Don't guess. Don't infer. "I don't have data on this" is always a valid answer.

## 2. Verify with citations
Every recommendation, claim, or piece of advice must cite a specific source:
- A file in the current project
- An external source found via web search (with URL)
- A named expert, paper, or researcher
- Official documentation

If you generate a claim and cannot find a supporting source, retract it. Do not present it.

## 3. Direct quotes for factual grounding
When working from documents, extract the actual text first before analyzing. Ground your response in word-for-word quotes, not paraphrased summaries. Reference the quote when making your point.

## How citations appear in a chat reply

The grounding requirement above never relaxes: state no claim you cannot source. What changes with the channel is how much of the source you print. A chat reply carries the source in compact form — a linked source name, or a `file:line` reference. Word-for-word quotes and full citation lists belong in artifacts, PR bodies, and issue bodies, or in a reply when the user asks for them.

## Exceptions
Creative thinking, brainstorming, and novel ideas don't require citation. You can synthesize across sources to reach new conclusions, but the inputs must be grounded.

## Sibling rules

- [`explore-thoroughly.md`](explore-thoroughly.md) — grounds an implementation plan in the codebase, as this rule grounds a factual claim in a source.
- [`verify-runtime-state.md`](verify-runtime-state.md) — a runtime verdict needs a live probe from this session, not a citation.
- [`hedging-claims.md`](hedging-claims.md) — the Stop hook that catches a bare hedge word; an explicit uncertainty label in the same sentence is the allowed alternative to a citation.
