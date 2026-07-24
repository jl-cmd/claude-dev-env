---
name: review-router
description: >-
  Resolve and arm one supported `route_review_config` route through the registered Agent|Task gate. Triggers: /review-router and guarded reviewer spawn.
---

# Review Router

Resolve and arm the supported `e-simplify` route. The registered `PreToolUse Agent|Task` hook enforces the exact armed spawn payload.

## When this applies

Use for `/review-router` and route execution after `/review-tier`. Return `UNSUPPORTED_ROUTE` for `e-code-review`; preserve `/e-code-review` behavior.

## Operations

1. Register `reference/task-seeds.md` with the host task tool.
2. Call `scripts/review_router_cli.py resolve` for the current `route_policy_hash` decision and optional tier override.
3. Call `arm` for the exact selected slot and dispatch the returned Agent|Task payload.
4. Let the registered hook enforce the payload, then call `close`.

The route topology is fixed: T1 uses one Luna High slot, T2 uses one Luna Max slot, and T3 uses six ordered Luna High slots.

## Composition

| Peer | When | Produces | Missing behavior |
|---|---|---|---|
| `/review-tier` | Before routing | Current tier decision | Return the route request to `/review-tier`. |
| `/e-simplify` | When cleanup review is requested | Cleanup review request | Return `UNSUPPORTED_ROUTE`. |

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Route contract and operations |
| `reference/route-policy.json` | Supported route topology |
| `reference/task-seeds.md` | Current route task seeds |
| `scripts/review_router.py` | `route_policy_hash` input and route resolution |
| `scripts/review_router_cli.py` | Resolve, arm, and close operations |
| `scripts/test_review_router.py` | Route policy tests |
| `scripts/test_review_router_cli.py` | CLI rejection tests |
| `scripts/test_review_router_integration.py` | CLI and registered-hook tests |
| `scripts/review_router_constants/config/constants.py` | Portable route constants |
| `scripts/review_router_constants/config/__init__.py` | Runtime configuration package |
| `scripts/review_router_constants/__init__.py` | Constants package |
| `scripts/conftest.py` | Test import setup |

## Folder map

- `reference/` — route policy and task seeds.
- `scripts/` — route resolution, CLI operations, and tests.
