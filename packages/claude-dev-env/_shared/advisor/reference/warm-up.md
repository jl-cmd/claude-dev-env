# Warm-up spawn fields and charter

Detail behind the **Warm-up** section of [`advisor-protocol.md`](../advisor-protocol.md).
Open this when binding the warm advisor on a Claude host or a Codex host, and for the charter text on every host.

## Spawn fields for a Claude host

The consuming skill's session tries Fable first. Spawn with:

- `subagent_type: session-advisor` (see [`agents/session-advisor.md`](../../../agents/session-advisor.md) for the full signal contract).
- `model`: the short alias via `resolve_cli_model_id("Fable")` (alias table: [`cli-chain.md`](cli-chain.md)): `fable`. When Fable is out of usage and the Astra rung is open, continue with the Codex helper in [`astra-rung.md`](astra-rung.md) as the Astra fallback.
- `name`: a name the session and every consumer will use to reach it (e.g. `team-advisor-agent`).
- `run_in_background: true`.
- `prompt`: the charter below. A **Fable**-tier try carries the exact token `FABLE-SPAWN-AUTHORIZED` in that prompt. `hooks/blocking/fable_spawn_gate.py` denies every `Agent` or `Task` spawn at `model: fable` whose prompt lacks that token. A try at any other tier needs no token.

Stop at the first successful bind. That try's tier is `selected_tier`; the warm advisor lives at that tier for the rest of the session.

## Charter (the spawn prompt)

The charter states the agent's role, the repo path, and the session's current goal in two or three sentences. The agent is a standing reviewer. It answers only via SendMessage. File edits and commands are out of its scope.
On a Fable-tier try, include the exact token `FABLE-SPAWN-AUTHORIZED` as plain text in this prompt (substring match; the gate reads the token alone, wherever it came from).
State plainly:

- Every consult carries: who is asking (name and assignment), what changed since their last consult, the live decision or question, and any load-bearing paths or excerpts.
- Reply via SendMessage to whoever sent the consult, by name. Each reply goes back to its own sender, and many different consumers may reach this one agent.
- Treat each consult on its own terms, keyed to the sender's stated assignment. Different consumers' consults will interleave in this one transcript. Keep each consumer's context separate, and blend only when a consult explicitly asks for that.
- If a consult re-raises a question already answered, with nothing new attached, reply by restating the prior answer and naming it as a restatement.
- Every reply, including this first bind turn, opens its first line with exactly one of the four uppercase signal words: `ENDORSE`, `CORRECTION`, `PLAN`, `STOP`. Nothing else on that line. Standing by after the bind is itself an `ENDORSE` of the charter, stated as that first line.

The agent finishes its first turn standing by. `SendMessage` alone resumes it; between consults it waits quietly.

## Codex host

Spawn a native in-session Astra subagent at `resolve_codex_model_id("Astra")` (`gpt-6-astra`) with the charter as its prompt.
Record `{tier: "Astra", result: "spawned"}` on success. Fail closed when that spawn does not bind.
The `ADVISOR_ASTRA` flag is not required. Do not walk Fable. Consults stay in-session with that Astra subagent.
Identity routing: [`identity.md`](identity.md).

## Third-party host

Bind per [`third-party-bind.md`](third-party-bind.md) and charter the CLI session with the same charter. The reply contract is the same, and consults travel through the CLI runner.
