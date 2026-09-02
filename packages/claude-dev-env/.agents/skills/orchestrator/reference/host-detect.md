# Host detect

Name the host so worker-model routing can pick `sonnet` or the
resolver-printed sonnet-equivalent id.

1. Read the session's named identity.
2. A `codex` token selects Codex. A `claude` token selects Claude. Any
   other identity selects ThirdParty.
3. When both tokens appear, Codex wins.

Mechanical override for scripts:

1. `ADVISOR_HOST_PROFILE=ThirdParty` or `=Claude` or `=Codex`.
2. `THIRD_PARTY=1` (or `true` / `yes` / `on`) selects ThirdParty.
3. Default: Claude.
