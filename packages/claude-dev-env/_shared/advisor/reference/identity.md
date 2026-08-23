# Session identity

Detail behind the **Host profiles** section of [`advisor-protocol.md`](../advisor-protocol.md).
Open this when binding the advisor and the session must name its identity.

## Resolve the profile

Call `resolve_session_identity` from `$HOME/.claude/_shared/advisor/scripts/tier_model_ids.py` with the session's named identity.

| Identity text | Host profile | Bind path |
|---|---|---|
| a `codex` token | Codex | In-session Sol spawn |
| a `claude` token | Claude | In-session Fable spawn of `session-advisor` |
| any other identity | ThirdParty | Headless CLI chain |

When both `codex` and `claude` tokens appear, Codex wins. Empty text is ThirdParty.

## Bind path

**Claude.** Spawn `subagent_type: session-advisor` at Fable through the Agent tool. When Fable is out of usage, bind Sol through the Codex helper if `ADVISOR_SOL` is on. Fail closed when neither binds.

**Codex.** Spawn a native in-session Sol subagent at `resolve_codex_model_id("Sol")` (`gpt-5.6-sol`). Walk `candidate_tiers = ["Sol"]`. Record `{tier: "Sol", result: "spawned"}` on success. The `ADVISOR_SOL` flag is not required. Fail closed when Sol does not bind. Do not walk Fable on a Codex host.

**ThirdParty.** Bind Fable through the CLI Claude-chain. When Fable is out of usage, bind Sol through the Codex helper if `ADVISOR_SOL` is on. Fail closed when neither binds.

## Mechanical override

Scripts that cannot self-identify read `detect_host_profile`. `ADVISOR_HOST_PROFILE` accepts `Claude`, `Codex`, or `ThirdParty`. `THIRD_PARTY=1` selects ThirdParty. The default is Claude.
