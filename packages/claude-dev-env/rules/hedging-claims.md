# Hedging Claims

State a claim with the evidence that backs it, or name the claim unverified. A hedge word stands in for evidence you did not gather.

`hedging_language_blocker` (Stop hook, hosted by `stop_dispatcher`) blocks a response carrying one — `likely`, `probably`, `presumably`, `perhaps`, `possibly`, `seemingly`, `apparently`, `arguably`, `supposedly`, `ostensibly`, `conceivably`, `plausibly`, `unlikely`, `probable`, and the phrases `might be`, `could be`, `seems to be`, `appears to be`, `in all likelihood`, `more likely than not`, `it's possible that`.

Deleting the hedge word and keeping the claim does not clear the block. Gather the source, run the probe, or ask the user through `AskUserQuestion` — then re-output the whole revised response.

Sibling rules: [`research-mode.md`](research-mode.md) names what counts as a citation; [`verify-runtime-state.md`](verify-runtime-state.md) names the live probe a runtime verdict rests on.
