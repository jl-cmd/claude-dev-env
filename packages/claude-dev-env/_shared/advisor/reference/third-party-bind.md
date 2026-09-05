# Third-party bind

Detail behind the **Host profiles → Third-party host** section of [`advisor-protocol.md`](../advisor-protocol.md).
Open this when binding or re-binding the advisor from a third-party (non-Claude, non-Codex) harness.

## GOTCHA: Cursor Astra first shot

Cursor is a third-party host. When the walk reaches Astra (`ADVISOR_ASTRA=1` / `--enable-astra` after Fable is out of usage, or the user asks for Astra), bind Astra on the **first** tool call through the headless Codex helper. Do not use the Agent or Task tool, do not spawn Grok as a substitute, and do not search the filesystem for `codex_usage_probe.py`.

```
python "$HOME/.claude/_shared/advisor/scripts/codex_astra_advisor.py" --bind --enable-astra --cwd <repo-root>
```

Pipe the standing-reviewer charter on stdin. Persist `session_id` from the JSON reply. Later consults: `--resume <session_id>` with the delta on stdin. Capture helper / `codex` stdout as UTF-8 on Windows (`encoding="utf-8"`, `errors="replace"`). Probe path and preflight: [`astra-rung.md`](astra-rung.md).

When the Astra flag is off, follow the Claude-chain steps below.

## Bind steps

1. Name the session identity first (protocol **Host profiles**). This path is for a ThirdParty profile.
2. Walk `candidate_tiers = ["Fable"]`. When Fable is out of usage, the Astra rung ([`astra-rung.md`](astra-rung.md)) binds Astra after Fable (`candidate_tiers = ["Fable", "Astra"]`).
3. **CLI bind (primary path):** for Fable, pipe a charter file into:

   ```
   python "$HOME/.claude/scripts/claude_chain_runner.py" --routing-mode ordered_account -- -p --model <alias> --effort <effort> --output-format json
   ```

   Use `--model fable --effort` with the value of `ADVISOR_EFFORT` (default `low`) on Fable.
   User-facing wording follows [`rules/asd-ste100-language.md`](../../../rules/asd-ste100-language.md).
   A root advisor bind uses `--routing-mode ordered_account`. Walk order, failover, and the `advisor_blocked` terminal status are in [`cli-chain.md`](cli-chain.md).
4. Stop at the first successful bind.
   Record `{tier, result: "cli"}` for Fable or `{tier: "Astra", result: "codex"}` for the Astra helper, and set `selected_tier` to that tier.
   Persist `session_id` from the JSON events (any event carries it; the runner also surfaces it on `ChainInvocationOutcome.session_id`; reply text is the `type == "result"` event's `.result` field).
   Run every bind and every later consult with cwd set to the repo root the work is for. Claude sessions are project-scoped by working directory.
5. **Fail closed:** when every candidate fails (chain exhausted, `advisor_blocked`, or model unavailable), set `selected_tier = null` and a `fallback_reason`, report that the advisor is unreachable, and **stop**. ENDORSE / CORRECTION / PLAN / STOP come only from a bound advisor.
6. Assemble and paste each executor's Advisor block from [`advisor-block.md`](advisor-block.md). Executors report to the orchestrating session; that session consults the bound advisor and relays the four-signal reply.

## Session model field

Resolve a third-party session's own model field with `resolve_cli_model_id("ThirdParty")` → `third-party` when a host model alias is required.
The **advisor** bind uses the Fable alias. Astra binds through the Codex helper.
