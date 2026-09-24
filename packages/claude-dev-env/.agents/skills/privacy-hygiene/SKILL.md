---
name: privacy-hygiene
description: Full-repo sweep for personal data and secrets before commit or durable GitHub post. Use when preparing a PR, cleaning a leak, or when the user asks for a privacy or secret sweep of a repository.
---

# privacy-hygiene

## Overview

Find and remove personal data and high-confidence secrets before they land in git history or a durable GitHub post. No write-time hook scans for these. This skill is the sweep.

**Announce at start:** "Running privacy-hygiene sweep."

## When to run a full sweep

- Before the first push of a branch that touched logs, screenshots, config samples, or machine-local paths
- After a `tracked-secrets` or gitleaks finding on email, home path, LAN address, or secret material
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

1. **Committed tree.** `scripts/repository_policy.py` runs its `tracked-secrets` check over every tracked file with this scanner, and CI runs the same command
2. **CI** — the `committed-tree` job in `.github/workflows/ci-tests.yml` runs [gitleaks](https://github.com/gitleaks/gitleaks) over every commit the pull request adds, test files included. The repository-root `.gitleaks.toml` adds three rules to the gitleaks defaults: a user folder path that names a person, an RFC 1918 address, and an email other than a noreply or example address. To clear a fixture that must stay, add its gitleaks fingerprint to `.gitleaksignore`

## Sweep procedure

Run the full-tree sweep in
[`reference/sweep-procedure.md`](reference/sweep-procedure.md): scope the tree,
run the ripgrep pass for the four high-confidence pattern families (email, home
path, LAN address, secret), review each hit against the ignore list, and
remediate. It also lists the accepted residual — what to leave in place rather
than over-scrub. The ripgrep command is the only pass over the tree.

## Enable on any machine / public repository

Install or reinstall the package so hooks and this skill land under `~/.claude/`:

```
cd packages/claude-dev-env
node bin/install.mjs
```

Once installed, this skill is available in every repository the agent touches, private or public. No installed hook scans a write, a commit, or a post.

## Open knobs

- **NAS / LAN allowlist:** Unlisted private IPs are blocked. The scanner resolves your NAS host from `CLAUDE_NAS_HOST`, then `~/.claude/local-identity.json` (`nas.host`), and allowlists it when it is a private address, so the committed tree holds no host address. `ALL_ALLOWLISTED_PRIVATE_IP_ADDRESSES` in `hooks_constants` holds the static allowlist for any host every machine must share.
- **Public maintainer identity:** when an email or name is intentional product surface, keep it and note that in the PR body so reviewers do not treat it as a leak.

## What this skill does not do

- Does not rewrite git history without explicit user approval
- Does not rotate credentials for you
- Does not scan commit-message text (`-m` / `-F`); keep messages free of secrets yourself
