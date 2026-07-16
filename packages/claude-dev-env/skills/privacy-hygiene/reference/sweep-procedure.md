# Full-tree PII sweep procedure

The on-demand full-repository sweep for the `privacy-hygiene` skill — the
complement to the write-time `pii_prevention_blocker`, which scans one payload at
a time. The canonical per-payload patterns live in the hooks' `pii_scanner` and
`pii_prevention_constants` modules; the ripgrep command below is the only
full-tree pass. The hub ([`../SKILL.md`](../SKILL.md)) points here.

## 1. Scope the tree

```
git status -sb
git diff --stat
git diff --cached --stat
```

Prefer the branch diff vs `origin/main` for PR prep:

```
git fetch origin main
git diff --name-only origin/main...HEAD
```

## 2. Search for high-confidence patterns

Run from the repo root (PowerShell-friendly example):

```
rg -n --hidden -g '!node_modules' -g '!.git' -e '@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' -e 'Users[/\\][^/\\]+' -e '[/]home/[^/]+' -e '\b(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)\b' -e '\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b' -e '\bgithub_pat_[A-Za-z0-9_]{20,}\b' -e '\bAKIA[0-9A-Z]{16}\b' -e '-----BEGIN [A-Z ]*PRIVATE KEY-----'
```

Review each hit. Ignore:

- Test fixtures under `test_*.py` / `*_test.py` / `/tests/` (synthetic only)
- `LICENSE` / copyright notice identity that is intentional and public
- This package's own `pii_scanner` / `pii_prevention_constants` modules
- Documented placeholders (`user@example.com`, `C:/Users/<you>/`)

## 3. Remediate

| Hit | Fix |
|---|---|
| Real email | Replace with `user@example.com` or remove |
| Home path | Use `Path.home()`, `~`, or `C:/Users/<you>/` |
| LAN address | Remove, use a hostname, or — for your own NAS — set the host in `CLAUDE_NAS_HOST` or `~/.claude/local-identity.json`, both of which stay out of git |
| Credential material | Remove from the tree; rotate the credential; load from env/secret store |
| Already committed | Rewrite is not enough if already pushed — rotate secrets; scrub history only with explicit user approval |

## 4. Re-check before commit / post

- Stage only clean files
- Prefer `--body-file` for `gh` posts (also required by the gh-body-file rule)
- Let `pii_prevention_blocker` re-run on the next Write / commit / post

## Accepted residual (do not over-scrub)

- LICENSE copyright lines naming a legal person or org that owns the work
- Intentional public maintainer identity published on purpose
- Example domains reserved for documentation (`example.com` and siblings)
- Placeholder home users (`example`, `user`, `alice`, `<you>`, `YOUR_USER`)
- The NAS host you configure locally (allowlisted at scan time, never committed)
- Public addresses and docs that name private ranges without a live host (still prefer hostnames)
