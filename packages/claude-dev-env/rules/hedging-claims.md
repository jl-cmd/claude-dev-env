# Hedging Claims

State a claim with the evidence that backs it, or name the claim unverified. A hedge word stands in for evidence you did not gather.

`hedging_language_blocker` (Stop hook, hosted by `stop_dispatcher`) runs when `CLAUDE_PROSE_STYLE_ENFORCEMENT` is on (see [`docs/references/prose-style-enforcement.md`](../docs/references/prose-style-enforcement.md)). It blocks a response that carries a bare hedge word — `likely`, `probably`, `presumably`, `perhaps`, `possibly`, `seemingly`, `apparently`, `arguably`, `supposedly`, `ostensibly`, `conceivably`, `plausibly`, `unlikely`, `probable`, and the phrases `might be`, `could be`, `seems to be`, `appears to be`, `in all likelihood`, `more likely than not`, `it's possible that` — **unless the same sentence** labels the claim with explicit uncertainty (`unverified`, `I don't know`, `I do not know`, `no source for this claim`, `without a source`).

A label in another sentence does not clear a bare hedge. Deleting the hedge word and keeping the claim does not clear the block. Gather the source, run the probe, label the claim unverified in that sentence, or ask the user through `AskUserQuestion` — then re-output the whole revised response.

When enforcement is off, bare hedges still emit privacy-safe advisory candidates for precision measurement (OP-07B).

Sibling rules: [`research-mode.md`](research-mode.md) names what counts as a citation; [`verify-runtime-state.md`](verify-runtime-state.md) names the live probe a runtime verdict rests on.
