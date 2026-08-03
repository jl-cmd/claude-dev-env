# CLI Claude-chain

Detail behind the `## CLI chain` section of [`advisor-protocol.md`](../advisor-protocol.md).
The shared runner is `python "$HOME/.claude/scripts/claude_chain_runner.py" [--routing-mode usage_ranked|ordered_account] -- <claude args...>`.

## Modes

| Mode | Flag | Walk order | Failover |
|---|---|---|---|
| Usage-ranked (default) | `--routing-mode usage_ranked` or omit the flag | Highest weekly remaining first (`claude_chain_usage` / usage-pause OAuth probe) | Usage-limit signature only |
| Ordered-account | `--routing-mode ordered_account` | Config list order in `~/.claude/claude-chain.json` | Usage-limit signature only; auth / timeout / config / other process errors → `advisor_blocked` |

**Third-party host root advisor bind and consult:** use ordered-account mode.
The primary launcher from the chain config is tried first.
A usage-limit result advances to the next config entry.
Any non-usage failure terminates as `advisor_blocked`.
Persist `session_id` from a successful bind and pass it to `-p --resume <session_id> --output-format json` on later consults.

**General chain calls** (non-root automation): keep the default usage-ranked mode so spare capacity on other accounts is preferred.

## Tier-to-alias map

Map `selected_tier` when one exists (the warm agent already bound at or above the floor).
Map the floor tier only when the walk exhausted with `selected_tier=null`.
Resolve that tier to its CLI / Agent model alias before the first call — the CLI `--model` flag and the Agent tool `model:` field take the short aliases below.
Source of truth: `ALL_CLI_MODEL_ID_BY_TIER` and `resolve_cli_model_id(tier)` in `advisor_scripts_constants` / the `tier_model_ids.py` helper.

| Ladder tier (Title Case) | CLI / Agent `model` alias |
|---|---|
| Fable | `fable` |
| Opus | `opus` |
| Sonnet | `sonnet` |
| Haiku | `haiku` |
| ThirdParty (third-party session model field only) | `third-party` |

Resolve in code with `python -c "from tier_model_ids import resolve_cli_model_id; print(resolve_cli_model_id('Opus'))"` from `$HOME/.claude/_shared/advisor/scripts/` (any letter case accepted; unknown tiers raise `ValueError`).

## Brief piping

Write the charter or the consult brief to a temporary file under the job's own temporary directory (or the OS temp directory when no job directory exists) and pipe it in from that file.
Drop the file once the consult completes.

## Session resume

Read the `session_id` out of the first call's JSON events.
Pass it to `-p --resume <session_id> --output-format json` on every later consult — `-p` stays on the resume call too, since it is still a non-interactive invocation.
A session store belongs to the binary and account that minted it, so after a usage-limit failover to the next binary a `--resume` against it can fail.
Treat that failure as starting over.
Resend the charter plus a compact recap of the consults since the last one, capture the new `session_id` the fresh call returns, and continue from there.
