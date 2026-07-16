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

Run the full-tree sweep in
[`reference/sweep-procedure.md`](reference/sweep-procedure.md): scope the tree,
run the ripgrep pass for the four high-confidence pattern families (email, home
path, LAN address, secret), review each hit against the ignore list, and
remediate. It also lists the accepted residual — what to leave in place rather
than over-scrub. The ripgrep command is the only full-tree pass; the write-time
`pii_prevention_blocker` scans one payload at a time.

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
