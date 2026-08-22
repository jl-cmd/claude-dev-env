# Offense examples (this repo)

Classify by **role** — the reusable work the surface performs — not by matching a string list. For whether code belongs in `shared_utils` vs a workflow package, invoke `shared-extraction-audit`; this map only scores names.

## Quick classifier

```
Queue, report parser, or routing table for one workflow only?
  YES → driver name OK
Shared artifact change a second workflow would call?
  YES → capability name required (flag when a driver word is present)
  Stays inside that workflow → OK driver; state why in the report
```

## OK — correctly driver-named

| Surface | Why OK |
|---------|--------|
| `cert_fix_queue` | Rejected-theme queue drain — driver-only orchestration |
| Cert report title → which ops to run | Driver / routing |
| Cert report locate / folder routing | Driver-only path finding for cert artifacts |
| Unfixable / unfixable-pattern tables | Cert-report classification artifacts |

## Violations — driver word on reusable capability

| Surface | Why violation | Suggested rename direction |
|---------|---------------|----------------------------|
| `cert_closeout` color engine (batch color UID rewrite) | General STP color batch shared across workflows | Capability name: STP color batch / color UID rewrite |
| `cert_fix_*` modules that are general STP patches | Patch logic reusable outside cert closeout | Name the STP operation (asset replace, sound slot, …) |
| `cert_fix_page_indicators` | Thematic page-indicator pair generation is a reusable asset op | Capability: page indicators / home indicator pair |
| Portal/export-named helper that any workflow could call | Motive word on a reusable library | Name the shared action (sheet write, APK locate, …) |
| PR titled or scoped with a driver word when the diff is a general capability | Motive framing on a library change | Retitle/scope to the capability; keep driver wording on the queue/driver PR |
