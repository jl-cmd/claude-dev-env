# PII hygiene decisions (current tree) — issue #945

`claude-dev-env` is the public Claude Code config package that ships to npm and hosts
its own source. This log records which personal-data items in the tree stay in place and
which are scrubbed for the public package.

## Keep in place

| Item | Decision | Reason |
|---|---|---|
| `LICENSE` copyright line `Jon Lombardi` | **Keep** | A copyright line for the author's own work belongs in a public package; it is not third-party personal data. |

## Scrubbed for the public tree

| Item | Decision | Detail |
|---|---|---|
| Real username paths in fixtures (`C:/Users/<name>/…`, `/home/<name>/…`) | **Scrub** | Fixtures, hook tests, and installer tests use `C:/Users/example/…` and `/home/example/…`. |
| Fleet-rollout record scripts holding a hardcoded private repo list | **Redact** | `merge-and-sync-all.sh` and `propagate-sync-fix.sh` drop the repo list; the target list is built at run time. |
| `scripts/fan_out_dispatch.py` workflow output | **Redact** | The step summary carries Metric/Count rows only; log notices print no owner or repository names (issue #948). |
| Sample private-repo names and PR numbers in worked examples | **Scrub** | Worked examples use `example-org/example-repo` and generic PR numbers. |
| Neon project ids and a partial Apps Script id in docs | **Scrub** | Docs use generic placeholders that name no real project. |
| NAS host, ssh user, and port in the NAS ssh hook, its rule, and their tests | **Local config** | The hook reads the `CLAUDE_NAS_*` env vars or `~/.claude/local-identity.json`; the committed tree carries placeholders (`nas.example.local`, `operator`, `22`). |
| GitHub owner scopes for the fan-out (`scripts/fan_out_dispatch.py`, `scripts/bootstrap-listeners.sh`, the fan-out workflow) | **Local config** | The dispatcher reads `FANOUT_OWNER_SCOPES` or `config/local-identity.json` through `config/local_identity.py`; the workflow reads the repo variables `FANOUT_OWNER_1` and `FANOUT_OWNER_2`. The committed default is `example-owner`. |
