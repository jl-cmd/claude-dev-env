Audit [REPO/ARTIFACT] [TARGET_ID] for **Category K only** (codebase conflicts — incomplete propagation). Skip A–J, L–N. Sub-bucket forced-exhaustion mode: Category K is decomposed into 9 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

[ARTIFACT METADATA — including the BEFORE state of changed surfaces, so the agent can compare before vs after]

- Title / one-line summary: [TITLE]
- Base ref / SHA (state BEFORE the change): [BASE_SHA]
- Head ref / SHA at audit time (state AFTER the change): [HEAD_SHA]
- Changed surfaces (file + line range + symbol/region name): [CHANGED_SURFACES]
- BEFORE state of each changed surface (the literal pre-change text the diff replaces): [BEFORE_SNIPPETS]
- AFTER state of each changed surface (the literal post-change text the diff installs): [AFTER_SNIPPETS]
- Stated intent of the change (what behavior the author intended to alter): [INTENT]

ID prefix: `find`.

[ONE-PARAGRAPH FRAME: describe what the diff changed in plain English, in terms narrow enough that a reader can hold the *contract* the diff is trying to enforce in their head while they read the unchanged code. State explicitly what the wider file / repo structure was left unchanged. Then state the audit goal: identify any unchanged parallel site whose existing wording / shape / behavior contradicts the new wording / shape / behavior so that the two reach the same downstream consumer (model, caller, runtime, schema, user, test) together.]

## Source material ([N] files/sections, all lines in scope)

[INLINE THE FULL DIFF — including BOTH the changed lines AND surrounding context that shows what stayed the same.]

[ALSO INCLUDE any unchanged files in the codebase that the agent must search for parallel sites. For a small repo, inline a project tree. For a large repo, identify the most likely affected files via `git grep <renamed-symbol>` or equivalent and inline those.]

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**K1. Multi-site name renames**
- Did the diff rename any symbol (function, method, class, variable, kwarg, type alias, constant name, enum variant, CSS class, config key, env var, route name, API field, log key, error code, test fixture name)?
- If yes, enumerate every reference site (call sites, imports, type annotations, error messages, docstrings, README, ADRs, tests, fixtures, CI configs, dashboards, alert rules) — does each one use the new name?
- Adversarial probes when no rename is present: (a) scan for near-renames where casing / hyphenation / pluralization changed; (b) scan for symbols whose *meaning* shifted even though the spelling did not; (c) scan for shadowed-but-not-renamed identifiers introduced in the diff.

**K2. Duplicated constants / defaults**
- Did the diff change a value (number, string, regex, path, URL, timeout, threshold, default argument, magic literal)? Enumerate every duplicated occurrence of that value across the repo, in both code and config.
- Did the diff update one occurrence but leave the duplicates stale? Cite each unchanged duplicate as the conflict pair partner.
- Adversarial probes when no duplicates exist: (a) grep the exact literal across all files; (b) grep the semantic neighbors (`120`, `2 * 60`, `"2m"`, `"PT2M"`); (c) check sibling-language partners (PowerShell + Python, TS + Go, YAML + code).

**K3. Primary path vs fallback path** ⭐ canonical K case
- Identify the primary / happy path and any fallback / error / default-when-missing / no-feature-installed path the diff touches. Do they both flow into the same downstream consumer (same return value, same response field, same log line, same UI, same exception class, same exit code)?
- Did the diff update the primary path's contribution but leave the fallback path's contribution stale (or vice versa)? Cite both lines as the conflict pair.
- Adversarial probes when paths look symmetric: (a) trace each branch's output to the same sink; (b) walk every `else:`, `except:`, `default:`, `?:`, `||`, `??`, `or` operator the diff is adjacent to; (c) check for "skill not installed" / "feature flag off" / "fixture missing" / "network unavailable" branches that bypass the new code.

**K4. Feature flag / version gate consistency**
- Did the diff flip a flag, bump a version, or change behavior under one branch of a guard? Enumerate every other guard for the same flag/version across the repo — do they all reflect the new behavior?
- Adversarial probes when the diff adds no flag: (a) is there an *existing* flag that should now be deprecated because the diff makes its protected branch unreachable; (b) is there a version-gated import or feature shim that the diff should have updated; (c) does the diff cross a deprecation window where one half of a deprecation is now wrong?

**K5. Producer-vs-consumer type contracts**
- Did the diff widen / narrow / reshape a producer's output (return type, response shape, dict keys, tuple arity, list element type, optional vs required field)? Enumerate every consumer — do their type annotations / destructuring / parsing still match?
- Adversarial probes when types look stable: (a) check for `Any` / `unknown` / `dict[str, Any]` consumers that hide drift; (b) check for serializers (JSON, MessagePack, protobuf) whose schema lags the producer; (c) check for runtime validators (pydantic, zod, joi) whose rules now allow what should be rejected (or vice versa).

**K6. Code vs documentation sync**
- Did the diff change observable behavior? Enumerate every doc surface that describes that behavior (module/class/function docstring, README, ADR, design doc, CHANGELOG, API docs, error messages shown to the user, comments adjacent to the changed code).
- Adversarial probes when docs look fine: (a) check for "see also" cross-references that now point to outdated explanations; (b) check for examples in the docstring that exercise the *old* behavior; (c) check for diagrams / state machines / sequence flows that depict the pre-diff path.

**K7. Code vs test sync**
- Did the diff change observable behavior? Enumerate every test that exercises that behavior — do positive, negative, edge, and regression tests all still express the post-diff contract?
- Adversarial probes when tests look green: (a) which tests pass *for the wrong reason* (assert on substring that survives the change but no longer represents the intent); (b) which tests are missing entirely (post-diff intent has no covering test); (c) which fixtures encode the old shape and would silently mask drift.

**K8. Cross-file / cross-language contract sync**
- Does the changed value or shape live in multiple languages (PowerShell + Python, TypeScript + Go, SQL + ORM model, Terraform + app config) or multiple file kinds (`.json` + `.yml`, `.proto` + generated stubs)? Enumerate every partner — do they all reflect the change?
- Adversarial probes when only one language is in play: (a) grep the value / shape in non-code surfaces (CI matrices, Docker env, Helm values, k8s manifests); (b) check for generated code that lags the source; (c) check for alternate spellings across language conventions (`snake_case` ↔ `camelCase` ↔ `kebab-case`).

**K9. Schema / data-shape propagation**
- Did the diff add / remove / rename a field, column, key, header, query parameter, message field, event payload field? Enumerate every site that constructs or consumes that shape — migrations, ORM models, serializers, fixtures, API docs, client SDKs, replay tooling, analytics emitters.
- Adversarial probes when no schema changed: (a) check for schemaless dicts that effectively define a shape; (b) check for ad-hoc `**kwargs` flows that propagate undeclared fields; (c) check for downstream stores (caches, queues, search indexes) whose schema now disagrees with the producer.

## Cross-bucket questions to answer at the end

Q1: Is there a pattern in this diff where the primary site is updated but a parallel site (any sub-bucket) stays stale? Cite both the diff line that was changed AND the unchanged-but-should-have-changed line.

Q2: What's the worst contradiction introduced by this change — the one most likely to silently produce contradictory behavior at runtime when the parallel-but-unchanged site is exercised? Cite the changed line and the parallel unchanged line by `path:line`.

Q3: Which existing test, doc, or downstream consumer is the strongest witness to the contradiction — i.e., which surface passes / reads coherently *only because* the parallel site was not updated alongside the diff?

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket K1-K9, produce Shape A or Shape B (with ≥3 probes). Each Shape A finding must cite BOTH the diff line that was changed AND the parallel line that was missed — the conflict is between the two, not in either alone. Category K Shape A findings always cite TWO line locations: the changed line and the unchanged-but-should-have-changed line. The `failure_mode` should describe the contradiction between the two states. Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 parallel sites that should have been updated alongside the diff — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

---

# Worked example: jl-cmd/claude-code-config PR #397 r3210166636

Note: PR #397 is the K canonical case, NOT #394.

Audit jl-cmd/claude-code-config PR #397 for **Category K only** (codebase conflicts — incomplete propagation). Skip A–J, L–N. Sub-bucket forced-exhaustion mode: Category K is decomposed into 9 sub-buckets below. Each sub-bucket REQUIRES at least one Shape A finding OR exactly one Shape B proof-of-absence with **at least 3 adversarial probes** specific to that sub-bucket. A sub-bucket returning neither is a protocol gap.

PR: fix(hooks): improve hedging-language guardrail to surface user questions
Base SHA: 76f9c1a0048729b87c44626a3380dc840065c2fa (origin/main at PR open time)
Head SHA at audit time: 95ba07d6a8e0cd041e49ec9b93ea388dab00c2f3 (the commit Cursor Bugbot reviewed at PR #397 — the version BEFORE the fix in 8bcd5154 that this audit is meant to surface)
ID prefix: `find`.

This PR's first commit modified exactly one substring inside the hedging-language hook's block-response payload — replacing the closing instruction at lines 137-138 (inside the `block_response["reason"]` f-string) with new text directing the model to do additional research or prompt the user via `AskUserQuestion` with options + context. The wider file structure was left unchanged. The audit goal: identify any unchanged parallel site whose existing wording contradicts the new line 138 wording so they would interpolate into the same string and reach the model together.

## Sub-buckets (each requires Shape A finding OR Shape B with ≥3 adversarial probes)

**K1. Multi-site name renames**
- The diff at lines 137-138 introduces no rename — the symbol names `skill_reference`, `block_response`, `formatted_term_list`, `RESEARCH_MODE_SKILL_SEARCH_PATHS` are all unchanged.
- Verify by scanning the full file for any identifier that appears in the new line 138 wording but is also defined elsewhere.

**K2. Duplicated constants / defaults**
- The string token `"I don't know"` is the load-bearing duplicated literal across this PR. Search the file at SHA 95ba07d6 for every occurrence: line 126 (inside the `else` branch's `skill_reference` literal: `"...verify with sources or reply 'I don't know'"`) and the pre-diff line 138 (the OLD `"Either VERIFY it with a source or replace it with 'I don't know'."`).
- The diff updated occurrence #2 (line 138) but NOT occurrence #1 (line 126). Both occurrences exist in strings that interpolate into the SAME `block_response["reason"]` field — the model receives both texts.
- Verify whether the operator-facing primary instruction and the fallback instruction now disagree about whether `"I don't know"` is an allowed escape.

**K3. Primary path vs fallback path** ⭐ canonical K case
- The file's `if resolved_skill_path is not None:` branch (line 121) is the PRIMARY path; the `else:` branch (lines 123-127) is the FALLBACK (no-research-mode-skill-installed) path. Both produce values for the same variable `skill_reference`.
- Both paths' output flows into the SAME f-string at line 134 (`f"{skill_reference}\n\n"`), and from there into the SAME `block_response["reason"]` value sent to Claude.
- The diff at lines 137-138 updated the wording the *primary* path's downstream message ends with (closes the `"reply 'I don't know'"` escape; replaces with `"prompt the user via AskUserQuestion..."`). The fallback path's `skill_reference` text at lines 124-126 STILL contains `"verify with sources or reply 'I don't know'"` — unchanged from main.
- When the no-research-mode-skill fallback runs, the model receives: (a) the unchanged fallback text saying `"reply 'I don't know'"` is an option, AND (b) the new line 138 text saying `"AskUserQuestion"` is the path.
- Cite line 126 (unchanged-but-should-have-changed) and line 138 (changed) as the conflict pair. Describe the contradiction the model sees.

**K4. Feature flag / version gate consistency**
- No flags, no version gates in this file. The path-search list (`RESEARCH_MODE_SKILL_SEARCH_PATHS`) is environmental, not flag-gated.
- Verify by scanning the file for `if FLAG`, `if version`, environment-variable checks beyond `expanduser("~")`.

**K5. Producer-vs-consumer type contracts**
- `skill_reference` is typed as `str` in both branches (the primary uses `f"under the research-mode constraints..."`; the fallback uses a parenthesized string concatenation). Both interpolate cleanly into the line 134 f-string.
- `block_response` is `dict[str, Any]`-shaped; consumed by `json.dumps` on line 145. No producer/consumer type drift introduced by the diff.

**K6. Code vs documentation sync**
- Top-of-file docstring (lines 2-6) says: `"When detected, Claude is forced to re-check and respond with verified facts."`
- The new line 138 text explicitly extends this to a second branch — `"prompt the user via AskUserQuestion with some potential options + context if you are unable to find anything online"` — i.e., the hook is no longer just about verified facts; it now also legitimizes user-elicited disambiguation as a valid response.
- Verify whether the docstring still describes the post-diff behavior.

**K7. Code vs test sync**
- The test file at the same SHA contains an assertion: `assert "verify with sources or reply" in parsed_response["reason"]` (line 100 of the test file).
- This assertion was satisfied by the PRE-diff state because both line 126 (`"verify with sources or reply 'I don't know'"`) and line 138 (`"Either VERIFY it with a source or replace it with 'I don't know'"`) contained the substring `"verify with sources or reply"` — wait, only line 126 contains that exact substring. Verify whether the test passes at SHA 95ba07d6 against (a) line 126's untouched fallback text or (b) some other source.
- If the test passes solely because line 126 was NOT updated, then the test is a load-bearing witness to the K3 conflict — it asserts the very fallback text that the PR's intent (close the "I don't know" escape) was meant to remove.
- The merged version (SHA 8bcd5154) updates the test assertion to `"verify with sources or prompt the user via AskUserQuestion"`, which only matches if line 126 is ALSO updated to that wording. The K3 fix and the K7 fix landed together in the merge commit; at SHA 95ba07d6 the test still passes against the unchanged fallback.

**K8. Cross-file / cross-language contract sync**
- Single-language (Python) change; cross-language not applicable for this PR.
- Cross-file: the only other affected file is the test file (already covered by K7). No CSS / TS / JSON / config files touched.

**K9. Schema / data-shape propagation**
- `block_response` dict shape is unchanged; the same four keys (`decision`, `reason`, `systemMessage`, `suppressOutput`) are emitted as before. The hook protocol contract is preserved.
- Verify no schema drift in the JSON the hook prints to stdout.

## Cross-bucket questions to answer at the end

Q1: Is there a pattern in this diff where the primary site is updated but a parallel site (any sub-bucket) stays stale? Cite both lines.
Q2: What's the worst contradiction introduced by this PR — the one most likely to silently produce contradictory guardrail behavior at runtime when the no-research-mode-skill fallback fires? Cite `packages/claude-dev-env/hooks/blocking/hedging_language_blocker.py:<line>` for both the changed and unchanged sites.
Q3: Which existing test in `test_hedging_language_blocker.py` would have caught the K3 contradiction had it been calibrated to the post-diff intent, and which existing test instead passes "for the wrong reason" because the fallback was not updated alongside the primary?

## Output

Lead: `Total: N (P0=N, P1=N, P2=N)`. For each sub-bucket K1-K9, produce Shape A or Shape B (with ≥3 probes). Each Shape A finding must cite BOTH the diff line that was changed AND the parallel line that was missed — the conflict is between the two, not in either alone. Cross-bucket Q1-Q3 answers after the per-sub-bucket walk. Adversarial second pass: "assume your first pass missed at least 3 parallel sites that should have been updated alongside the diff — find them." Open Questions section for ambiguities. Read-only. No edits, no commits.

## Diff (the buggy commit's change vs base)

```diff
@@ -134,7 +134,7 @@ def main() -> None:
             f"These words signal unverified claims. You MUST rewrite your response "
             f"{skill_reference}\n\n"
             f"Do NOT simply remove the hedging word and keep the unverified claim. "
-            f"Either VERIFY it with a source or replace it with 'I don't know'.\n\n"
+            f"Do more research to VERIFY it with a source, or prompt the user via AskUserQuestion with some potential options + context if you are unable to find anything online.\n\n"
             f"You MUST re-output the complete, revised response with the corrections applied."
         ),
```

(The rest of the PR at this SHA is a single test-file edit that does not bear on the hook's runtime behavior; the K conflict, if any, lives in the hook source file inlined below.)

## Full file at SHA 95ba07d6 (1 file, all lines in scope; the diff above only touches lines 137-138)

### packages/claude-dev-env/hooks/blocking/hedging_language_blocker.py
```python
#!/usr/bin/env python3
"""
Stop hook that blocks Claude responses containing hedging language.

Words like "likely", "probably", "presumably" signal unverified claims.
When detected, Claude is forced to re-check and respond with verified facts.
"""

import json
import os
import re
import sys
from pathlib import Path


def _insert_hooks_tree_for_imports() -> None:
    hooks_tree = Path(__file__).resolve().parent.parent
    hooks_tree_string = str(hooks_tree)
    if hooks_tree_string not in sys.path:
        sys.path.insert(0, hooks_tree_string)


_insert_hooks_tree_for_imports()

from config.messages import USER_FACING_NOTICE

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESEARCH_MODE_SKILL_SEARCH_PATHS = [
    os.path.join(PLUGIN_ROOT, "skills", "research-mode", "SKILL.md"),
    os.path.join(os.path.expanduser("~"), ".claude", "skills", "research-mode", "SKILL.md"),
    os.path.join(os.path.expanduser("~"), ".claude", "plugins", "marketplaces", "claude-deep-research", "skills", "research-mode", "SKILL.md"),
]

HEDGING_WORDS = [
    r"\blikely\b",
    r"\bunlikely\b",
    r"\bprobably\b",
    r"\bprobable\b",
    r"\bpresumably\b",
    r"\bperhaps\b",
    r"\bpossibly\b",
    r"\bseemingly\b",
    r"\bapparently\b",
    r"\barguably\b",
    r"\bsupposedly\b",
    r"\bostensibly\b",
    r"\bconceivably\b",
    r"\bplausibly\b",
]

HEDGING_PHRASES = [
    r"\bmight be\b",
    r"\bcould be\b",
    r"\bseems to be\b",
    r"\bappears to be\b",
    r"\bin all likelihood\b",
    r"\bmore likely than not\b",
    r"\bit.s possible that\b",
]

ALL_HEDGING_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in HEDGING_WORDS + HEDGING_PHRASES
]

CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```", re.MULTILINE)
INLINE_CODE_PATTERN = re.compile(r"`[^`]+`")
QUOTED_BLOCK_PATTERN = re.compile(r"^>.*$", re.MULTILINE)


def strip_code_and_quotes(text: str) -> str:
    """Remove code blocks, inline code, and blockquotes to avoid false positives."""
    text = CODE_BLOCK_PATTERN.sub("", text)
    text = INLINE_CODE_PATTERN.sub("", text)
    text = QUOTED_BLOCK_PATTERN.sub("", text)
    return text


def find_hedging_words(text: str) -> list[str]:
    """Return all hedging words/phrases found in the text."""
    prose_text = strip_code_and_quotes(text)
    matched_terms = []

    for pattern in ALL_HEDGING_PATTERNS:
        all_matches = pattern.findall(prose_text)
        for each_match in all_matches:
            normalized_term = each_match.strip().lower()
            if normalized_term not in matched_terms:
                matched_terms.append(normalized_term)

    return matched_terms


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if hook_input.get("stop_hook_active", False):
        sys.exit(0)

    assistant_message = hook_input.get("last_assistant_message", "")

    if not assistant_message:
        sys.exit(0)

    found_hedging_terms = find_hedging_words(assistant_message)

    if not found_hedging_terms:
        sys.exit(0)

    formatted_term_list = ", ".join(f'"{term}"' for term in found_hedging_terms)

    resolved_skill_path: str | None = None
    for each_skill_path in RESEARCH_MODE_SKILL_SEARCH_PATHS:
        if os.path.exists(each_skill_path):
            resolved_skill_path = each_skill_path
            break

    if resolved_skill_path is not None:
        skill_reference = f"under the research-mode constraints defined in:\n\n{resolved_skill_path}"
    else:
        skill_reference = (
            "under research-mode constraints "
            "(no research-mode skill installed; verify with sources or reply 'I don't know')"
        )

    block_response = {
        "decision": "block",
        "reason": (
            f"ANTI-HALLUCINATION GUARDRAIL: Your response contains hedging language: "
            f"{formatted_term_list}. "
            f"These words signal unverified claims. You MUST rewrite your response "
            f"{skill_reference}\n\n"
            f"Do NOT simply remove the hedging word and keep the unverified claim. "
            f"Do more research to VERIFY it with a source, or prompt the user via AskUserQuestion with some potential options + context if you are unable to find anything online.\n\n"
            f"You MUST re-output the complete, revised response with the corrections applied."
        ),
        "systemMessage": USER_FACING_NOTICE,
        "suppressOutput": True,
    }

    print(json.dumps(block_response))
    sys.exit(0)


if __name__ == "__main__":
    main()
```

### Companion test file at the same SHA (1 of 6 test cases inlined for K7 cross-reference)

```python
# packages/claude-dev-env/hooks/blocking/test_hedging_language_blocker.py
# Excerpt: the test that asserts the no-research-mode-skill fallback wording
def test_hedging_reason_contains_not_installed_notice_when_skill_absent():
    # ... fixture setup omitted ...
    assert parsed_response["decision"] == "block"
    assert "no research-mode skill installed" in parsed_response["reason"]
    assert "verify with sources or reply" in parsed_response["reason"]
    assert "SKILL.md" not in parsed_response["reason"]
    assert RESEARCH_MODE_SKILL_BODY_MARKER not in parsed_response["reason"]
```
