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
| Sample private-repo names and PR numbers in worked examples | **Scrub** | Worked examples use `example-org/example-repo` and generic PR numbers. |
| Neon project ids and a partial Apps Script id in docs | **Scrub** | Docs use generic placeholders that name no real project. |
| NAS host, ssh user, and port in the NAS ssh hook, its rule, and their tests | **Local config** | The hook reads the `CLAUDE_NAS_*` env vars or `~/.claude/local-identity.json`; the committed tree carries placeholders (`nas.example.local`, `operator`, `22`). |
