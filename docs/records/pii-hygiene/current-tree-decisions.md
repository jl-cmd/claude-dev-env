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
| Test fixtures using real Windows username path `C:/Users/jon/...` | **Scrub** | Replaced with `C:/Users/example/...` across hooks/tests/docs examples. |
| `docs/records/ai-rules-fleet-rollout/merge-and-sync-all.sh` personal-repo inventory | **Redact** | Removed hardcoded private repo name list; script now exits with a pointer to runtime enumeration. |
| `scripts/fan_out_dispatch.py` Actions logging | **Redact** | Job log and step summary now use count-only summaries; private target repo names are not printed (issue #948). |

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

