---
name: privacy-hygiene
description: Full-repo sweep for personal data and secrets before commit or durable GitHub post. Use when preparing a PR, cleaning a leak, or when `pii_prevention_blocker` denies a write, post, or commit. Triggers on "privacy hygiene", "personal data", "secret sweep", "sanitize repository", "/privacy-hygiene".
---

# privacy-hygiene

## Overview

Find and remove personal data and high-confidence secrets before they land in git history or a durable GitHub post. The `pii_prevention_blocker` hook blocks the common cases at write, post, and commit time. This skill is the full sweep when you need a broader pass or a remediation plan.

**Announce at start:** "Running privacy-hygiene sweep."

## When to run a full sweep

- Before the first push of a branch that touched logs, screenshots, config samples, or machine-local paths
- After a hook block on email, home path, LAN address, or secret material
- Before opening a PR to a repository that is public (or will be made public)
- After pasting support tickets, env dumps, or terminal transcripts into the tree

## What the automated gate blocks

| Category | Blocked examples | Allowed residual |
|---|---|---|
| Email | `user@example.com` | `user@example.com`, `user@example.org`, `user@example.net` |
| Home path | `C:/Users/example/...`, `/Users/example/...`, `/home/example/...` | `C:/Users/example/...`, `C:/Users/<you>/...`, `/Users/alice/...` |
| LAN address | Unlisted `10.x` / `172.16–31.x` / `192.168.x` | Public addresses; your NAS host from `CLAUDE_NAS_HOST` or `~/.claude/local-identity.json`; entries in `ALL_ALLOWLISTED_PRIVATE_IP_ADDRESSES` |
| Secret | `ghp_…`, `github_pat_…`, `AKIA…`, PEM private-key headers | Public keys, redacted `***`, env var names without values |

Surfaces:

1. **Write / Edit / MultiEdit** — payload text about to land on disk (via PreToolUse dispatcher)
2. **Durable posts** — `gh pr/issue create|comment|edit|review` bodies and GitHub MCP body/comment fields (Bash and PowerShell)
3. **git commit** — staged blob text (non-exempt paths) on Bash and PowerShell, including `git.exe` and flag forms (`--no-verify`, `-c`, `-C`). Commit message bodies (`-m` / `-F`) are out of scope for the automated gate

## Sweep procedure

### 1. Scope the tree

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

### 2. Search for high-confidence patterns

Run from the repo root (PowerShell-friendly example):

```
rg -n --hidden -g '!node_modules' -g '!.git' -e '@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' -e 'Users[/\\][^/\\]+' -e '[/]home/[^/]+' -e '\b(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+)\b' -e '\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b' -e '\bgithub_pat_[A-Za-z0-9_]{20,}\b' -e '\bAKIA[0-9A-Z]{16}\b' -e '-----BEGIN [A-Z ]*PRIVATE KEY-----'
```

Review each hit. Ignore:

- Test fixtures under `test_*.py` / `*_test.py` / `/tests/` (synthetic only)
- `LICENSE` / copyright notice identity that is intentional and public
- This package's own `pii_scanner` / `pii_prevention_constants` modules
- Documented placeholders (`user@example.com`, `C:/Users/<you>/`)

### 3. Remediate

| Hit | Fix |
|---|---|
| Real email | Replace with `user@example.com` or remove |
| Home path | Use `Path.home()`, `~`, or `C:/Users/<you>/` |
| LAN address | Remove, use a hostname, or — for your own NAS — set the host in `CLAUDE_NAS_HOST` or `~/.claude/local-identity.json`, both of which stay out of git |
| Credential material | Remove from the tree; rotate the credential; load from env/secret store |
| Already committed | Rewrite is not enough if already pushed — rotate secrets; scrub history only with explicit user approval |

### 4. Re-check before commit / post

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

## Enable on any machine / public repository

Install or reinstall the package so hooks and this skill land under `~/.claude/`:

```
cd packages/claude-dev-env
node bin/install.mjs
```

Hooks register via `hooks/hooks.json` into `~/.claude/settings.json`. Once installed, the same gates apply in every repository the agent touches — private or public.

## Open knobs

- **NAS / LAN allowlist:** Unlisted private IPs are blocked. The scanner resolves your NAS host from `CLAUDE_NAS_HOST`, then `~/.claude/local-identity.json` (`nas.host`), and allowlists it when it is a private address, so the committed tree holds no real host. `ALL_ALLOWLISTED_PRIVATE_IP_ADDRESSES` in `hooks_constants` holds the static allowlist for any host every machine must share.
- **Commit-scan exempt repositories:** named owner/repo slugs skip the staged-commit PII scan only. Set `CLAUDE_PII_EXEMPT_REPOS` (comma-separated `owner/repo` values) or list them under `pii_exempt_repositories` in `~/.claude/local-identity.json`. Matching uses the repository's `remote.origin.url` and accepts only the exact host `github.com` (https, ssh scheme, or scp-style). A repository with no readable origin is never exempt (fail-closed to scanning). Write / Edit / MultiEdit and durable post bodies still scan in every repository.
- **Public maintainer identity:** when a real email or name is intentional product surface, keep it and note that in the PR body so reviewers do not treat it as a leak.

## What this skill does not do

- Does not rewrite git history without explicit user approval
- Does not rotate credentials for you
- Does not replace the write-time hook — it complements it
- Does not scan commit-message text (`-m` / `-F`); keep messages free of secrets yourself
