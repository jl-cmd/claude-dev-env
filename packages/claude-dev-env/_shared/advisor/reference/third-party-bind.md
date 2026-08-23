# Third-party bind

Detail behind the **Host profiles → Third-party host** section of [`advisor-protocol.md`](../advisor-protocol.md).
Open this when binding or re-binding the advisor from a third-party (non-Claude) harness.

## Bind steps

1. Detect the host profile first (protocol **Host profiles**).
2. Set the advisor floor to **Opus** so the walk is `candidate_tiers = ["Fable", "Opus"]` with `own_tier = Opus`. When Fable is out of usage, the sol rung ([`sol-rung.md`](sol-rung.md)) binds Sol at low effort between Fable and Opus.
3. **CLI bind (primary path):** for each candidate top-down, pipe a charter file into:

   ```
   python "$HOME/.claude/scripts/claude_chain_runner.py" --routing-mode ordered_account -- -p --model <alias> --effort <effort> --output-format json
   ```

   Use `--model fable --effort medium` on Fable; use `--model opus --effort xhigh` on Opus.
   Opus routing follows [`rules/opus5-communication-contract.md`](../../../rules/opus5-communication-contract.md).
   User-facing wording follows [`rules/asd-ste100-language.md`](../../../rules/asd-ste100-language.md).
   The caller picks the Fable effort from task scope; when the caller cannot judge scope well enough to pick, it asks the user through AskUserQuestion before binding, and defaults to `medium` when no caller choice arrives.
   A root advisor bind uses `--routing-mode ordered_account` — walk order, failover, and the `advisor_blocked` terminal status are in [`cli-chain.md`](cli-chain.md).
4. Stop at the first successful bind.
   Record `{tier, result: "cli"}` and set `selected_tier` to that tier.
   Persist `session_id` from the JSON events (any event carries it; the runner also surfaces it on `ChainInvocationOutcome.session_id`; reply text is the `type == "result"` event's `.result` field).
   Run every bind and every later consult with cwd set to the repo root the work is for — Claude sessions are project-scoped by working directory.
5. **Fail closed:** when every candidate fails (chain exhausted, `advisor_blocked`, or model unavailable), set `selected_tier = null` and a `fallback_reason`, report that the advisor is unreachable, and **stop**. ENDORSE / CORRECTION / PLAN / STOP come only from a bound advisor.
6. Assemble and paste each executor's Advisor block from [`advisor-block.md`](advisor-block.md). Executors report to the orchestrating session; that session consults the bound advisor and relays the four-signal reply.

## Session model field

Resolve a third-party session's own model field with `resolve_cli_model_id("ThirdParty")` → `third-party` when a host model alias is required.
The **advisor** bind uses Fable/Opus aliases only.
