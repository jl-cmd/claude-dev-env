# Audit reply template

Canonical reply shape for every orchestrator-to-thread reply posted by the PR-loop suite (`pr-converge`, `bugteam`, `findbugs`, `qbug`, `fixbugs`, and the `clean-coder` agent). Every reply Claude posts to an unresolved review thread on a draft PR uses this template.

Read this doc before authoring any code that posts a reply. The template is the contract `clean-coder` will read in a later PR (blocked on open PR #424); this doc defines the shape that wiring must emit.

## Provenance

The template mirrors Anthropic's `claude[bot]` reply structure observed on `anthropics/claude-code`. Reference example: PR `anthropics/claude-code#10826`, inline comment `2483980211`. Reading that thread shows the structural anchors this template captures: a status header line, a horizontal-rule separator, an `<action_heading> ✅` section, a plain-language explanation, anchored `**`<file>:<line>`:**` bullets, and a closing paragraph.

## When the template applies

Every reply path uses the same skeleton. Two paths exist; both produce a reply with the structure below.

| Path | When the orchestrator picks it | Code-side action |
|---|---|---|
| Fix | Thread classified `still_applies`. Code change addresses the finding. | `clean-coder` commits the fix, pushes, then replies. |
| No-longer-applies | Thread classified `no_longer_applies`. Concern is moot under the current code (file removed, intent satisfied differently, refactor obviated the concern). | No code change. Orchestrator posts the reply directly. |

## Template skeleton

```
**Claude finished @<reviewer>'s task** —— <status_line>

---
### <action_heading> ✅

<1–2 paragraph plain-language explanation>

**`<file>:<line>`:**
- <bullet describing change or rationale>
- <bullet describing change or rationale>

<closing paragraph>
```

### Placeholder reference

| Placeholder | Required value |
|---|---|
| `<reviewer>` | GitHub login of the reviewer whose thread the reply addresses (e.g., `cursor[bot]`, `copilot-pull-request-reviewer[bot]`, `claude[bot]`, the bugteam-account login, a human reviewer's login). |
| `<status_line>` | One of two fixed strings, see [Per-path variation](#per-path-variation). |
| `<action_heading>` | Per-path content, see [Per-path variation](#per-path-variation). |
| `<file>:<line>` | Path relative to repo root and the line number the reviewer anchored to. Multiple `**`<file>:<line>`:**` blocks are allowed when the reply spans more than one anchor in the same thread. |
| Bullets | Two or more bullets per anchor block. Each bullet is one sentence. |
| Closing paragraph | One paragraph that ties the bullets back to the reviewer's concern. Affirmative phrasing only. |

The separator between the header and `<action_heading>` is a Markdown horizontal rule (`---`) on its own line. The em-dash separator inside the header line is `——` (two em-dashes, U+2014 ×2). Both render correctly on GitHub.

## Per-path variation

| Path | `<status_line>` | `<action_heading>` |
|---|---|---|
| Fix | `Fixed in <SHA>` (short SHA, 7 characters) | Finding-specific action verb. Example: `Replaced Any with concrete type`, `Renamed handle_request to dispatch_webhook`, `Added missing Raises: section`. |
| No longer applies | `This concern no longer applies` | Reason-specific. Example: `File removed in commit <SHA>`, `Intent satisfied via refactor in commit <SHA>`, `Concern superseded by upstream change`. |

## Structural identity rule

The skeleton is identical across both paths. The only per-path differences are `<status_line>` and `<action_heading>`. Every other element is present in both paths:

- The header line with `**Claude finished @<reviewer>'s task** —— <status_line>` is present in both paths.
- The horizontal rule separator is present in both paths.
- The `### <action_heading> ✅` line is present in both paths.
- The plain-language explanation is present in both paths.
- The `**`<file>:<line>`:**` bullet blocks are present in both paths. On the fix path, bullets describe what changed. On the no-longer-applies path, bullets describe why the concern is moot at that anchor.
- The closing paragraph is present in both paths.

A reply that omits any of these elements does not satisfy the template.

## Worked example — fix path

Reviewer thread (synthesized for this doc):

> `cursor[bot]` on `src/foo.py:42`:
> The `handle_request` function returns `Any`. Name the concrete return type so callers do not lose type information.

Reply posted by `clean-coder` after committing the fix at SHA `a3f9c12`:

```markdown
**Claude finished @cursor[bot]'s task** —— Fixed in a3f9c12

---
### Replaced Any with concrete return type ✅

The reviewer's concern is correct: returning `Any` from a public function erases type information for every caller and defeats `mypy`'s ability to catch shape mismatches downstream. The fix names the concrete return type the function already produces.

**`src/foo.py:42`:**
- Changed the return annotation from `Any` to `RequestOutcome`.
- Renamed the function from `handle_request` to `dispatch_webhook` to comply with the banned-prefix rule (`handle_` is one of the banned function prefixes per `CODE_RULES.md`).
- Added a Google-style `Returns:` section to the docstring naming the new return type.

The function signature now matches its actual behavior, and `mypy --strict` reports zero errors on the touched file.
```

## Worked example — no-longer-applies path

Reviewer thread (synthesized for this doc):

> `copilot-pull-request-reviewer[bot]` on `src/legacy_adapter.py:88`:
> This compatibility shim should be removed once the upstream migration completes. Add a TODO with the planned removal date.

Reply posted by the orchestrator directly (no code change) after the upstream migration lands and removes the shim file entirely:

```markdown
**Claude finished @copilot-pull-request-reviewer[bot]'s task** —— This concern no longer applies

---
### File removed in commit b8e2d4f ✅

The compatibility shim the reviewer flagged is no longer present in the tree. The upstream migration completed in commit `b8e2d4f`, and the same commit deleted `src/legacy_adapter.py` outright. There is no longer any shim to add a TODO to, and there is no longer any caller that imports from the removed module.

**`src/legacy_adapter.py:88`:**
- The anchored line lives in a file deleted by commit `b8e2d4f`.
- A repo-wide grep for `legacy_adapter` returns zero matches.
- The two former call sites (`src/api/router.py`, `src/api/middleware.py`) import from the consolidated module instead.

The thread can be resolved without further action; the reviewer's underlying concern is satisfied by the deletion rather than by the originally requested TODO.
```

## Relationship to the audit review body

The audit review body posted by `post_audit_thread.py` (consumers: `bugteam`, `findbugs`, `qbug`) shares the same header anchor pattern:

<!-- audit-body-skeleton:start -->
```
**<Skill> audit completed** —— <state_label>

---
### <heading>

<summary paragraph>

**Findings:** <N> | **Severity:** <P0 count>P0 / <P1 count>P1 / <P2 count>P2

<optional collapsed details section per finding>
```
<!-- audit-body-skeleton:end -->

The audit review body announces a complete audit pass; the reply template addresses one specific thread. They use the same `**Title** —— <status>` header convention so a reader scanning a PR sees consistent visual anchoring across both surfaces.

## Cross-references

- [`audit-contract.md`](audit-contract.md) — finding schema (Shape A / Shape B), adversarial second pass, post-fix self-audit, persistence layout. The fields in a Shape A finding (`file`, `line`, `failure_mode`) feed the placeholders in this template. Replies cite the same `<file>:<line>` anchors that the originating audit recorded.
- [`fix-protocol.md`](fix-protocol.md) — step 12 of the fix protocol describes the reply step. Step 12 currently shows only a terse `Fixed in <short_sha>` reply shape. A Phase-2 follow-on edit replaces step 12's terse shape with this template's full structure. That edit is out of scope for this PR.
- [`gh-payloads.md`](gh-payloads.md) — MCP and REST endpoints used to post replies (`add_reply_to_pull_request_comment` and `post_fix_reply.py`). The transport is independent of the template; both transports accept the body string this template defines.
