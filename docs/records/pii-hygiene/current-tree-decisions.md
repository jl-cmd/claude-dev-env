# PII hygiene decisions (current tree) — issue #945

Recorded while continuing the remediation started in session
`29e23cb0-1612-44ff-bbe0-770d589e9f15`.

## Keep as-is

| Item | Decision | Rationale |
|---|---|---|
| NAS address `192.168.1.100` and SSH user `jon@…` in NAS hook/rule/tests | **Keep** for now | Functional contract for the NAS SSH enforcer; RFC1918-only, not internet-routable. Externalizing to a gitignored local config remains optional follow-up if the fresh public export still wants a placeholder-only tree. |
| `LICENSE` copyright line `Jon Lombardi` | **Keep** | Copyright assertion for the author's own work is intentional for a public package; not third-party PII. |

## Changed in this branch

| Item | Decision | Change |
|---|---|---|
| Test fixtures using real Windows username path `C:/Users/jon/...` (and `/home/jon`, `Users/jonlo`) | **Scrub** | Replaced with `C:/Users/example/...` / `/home/example/...` across hooks/tests/installer fixtures and local settings allowlist. |
| `docs/records/ai-rules-fleet-rollout/merge-and-sync-all.sh` personal-repo inventory | **Redact** | Removed hardcoded private repo name list; script now exits with a pointer to runtime enumeration. |
| `docs/records/ai-rules-fleet-rollout/propagate-sync-fix.sh` personal-repo inventory | **Redact** | Same treatment as `merge-and-sync-all.sh`; hardcoded `jl-cmd/*` and `JonEcho/*` target list removed. |
| `scripts/fan_out_dispatch.py` workflow output | **Redact** | Step summary is Metric/Count rows only; notices never print owner or repository full names (issue #948). |

## Still blocked on owner decision

See GitHub issue #950 parent and private audit notes from the prior session:
whether to publish a **fresh clean-history repo** vs flip this repo public.
`refs/pull/N/head` permanently retains all historical PR commits, so flipping
this repository public is permanently high-risk even after Support GC.

## Publish path decision (2026-07-09)

**Chosen: fresh clean-history public repo.**

- Keep `jl-cmd/claude-code-config` **private forever**.
- Publish a separate public repository whose only history is a clean export of current `main` (no PR refs, no issue history, no dangling objects).
- GitHub Support GC of dangling PII objects on the private original becomes **defense-in-depth**, not a gate to publishing.
- npm `package.json` `repository` field (and any external links that cite private PR/issue numbers as the package home) must point at the new public repo after export.


**Public export target:** `jl-cmd/claude-dev-env`.

