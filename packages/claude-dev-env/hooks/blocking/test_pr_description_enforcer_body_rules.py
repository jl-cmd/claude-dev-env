"""Unit tests for pr-description-enforcer body rule enforcement via validate_pr_body."""

import importlib.util
import json
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_ROOT = _HOOK_DIR.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

import pytest

from blocking import pr_description_readability as readability_module

enforcer_spec = importlib.util.spec_from_file_location(
    "pr_description_enforcer",
    _HOOK_DIR / "pr_description_enforcer.py",
)
assert enforcer_spec is not None
assert enforcer_spec.loader is not None
enforcer_module = importlib.util.module_from_spec(enforcer_spec)
enforcer_spec.loader.exec_module(enforcer_module)
validate_pr_body = enforcer_module.validate_pr_body


@pytest.fixture(autouse=True)
def _isolate_readability_state(tmp_path_factory, monkeypatch):
    """Redirect the three readability state files to per-test temp paths for every test.

    The enabled file is written with enabled=False so the readability check stays
    off for the body-rule tests, isolating them from readability scoring and the
    live state directory.
    """
    per_test_state_dir = tmp_path_factory.mktemp("readability_state")
    strike_path = per_test_state_dir / "strikes.json"
    override_path = per_test_state_dir / "overrides.json"
    enabled_path = per_test_state_dir / "enabled.json"
    enabled_path.write_text(json.dumps({"enabled": False}))
    monkeypatch.setattr(readability_module, "READABILITY_STATE_FILE", strike_path)
    monkeypatch.setattr(readability_module, "READABILITY_THRESHOLD_OVERRIDE_FILE", override_path)
    monkeypatch.setattr(readability_module, "READABILITY_ENABLED_STATE_FILE", enabled_path)


VALID_BODY = (
    "Allow commas in branch names so PRs whose head branch was generated from "
    "a title or external identifier no longer fail validation before any git "
    "operation.\n\n"
    "Fixes #1300.\n\n"
    "## Changes\n\n"
    "- `src/github/operations/branch.ts`: add `,` to the whitelist regex\n"
    "- `test/branch.test.ts`: 3 new cases covering comma-bearing branch names\n\n"
    "## Test plan\n\n"
    "- `bun test test/branch.test.ts`\n"
    "- `bun run typecheck`\n"
)

LEGACY_DESCRIPTION_WHY_HOW_BODY = (
    "## Description\n\nFixes a real bug in the authentication module that affected production users.\n\n"
    "## Why\n\nThe defect surfaced in production and customers reported repeated sign-in failures.\n\n"
    "## How\n\nRefactored the auth module to handle edge cases correctly.\n"
)


def _has_vague_language_violation(all_violations: list[str]) -> bool:
    return any("Vague language" in each_violation for each_violation in all_violations)


def _build_heavy_body(opening_header: str, testing_header: str) -> str:
    intro_text = (
        "Adds shape-aware validation across the pr-description-enforcer pipeline. "
        "The change unifies the body audit with the Anthropic claude-code style "
        "so heavy PRs carry both an opening header and a testing header."
    )
    return (
        f"{intro_text}\n\n"
        f"{opening_header}\n\n"
        "The earlier flow rejected too many valid bodies on equivalence checks "
        "across the three shape categories described in the guide. The fix "
        "restructures the path around shape detection and surfaces the missing "
        "category in the block message so the agent can correct it on first try.\n\n"
        f"{testing_header}\n\n"
        "- `pytest packages/claude-dev-env/hooks/blocking/test_pr_description_enforcer.py`\n"
        "- Manual smoke test against the implementation PR with a sample heavy body\n"
        "- Run the readability check across the full corpus to confirm thresholds hold\n"
    )


def test_validate_passes_anthropic_standard_body() -> None:
    assert validate_pr_body(VALID_BODY) == []


def test_validate_passes_legacy_description_why_how_body() -> None:
    """Existing Description/Why/How bodies must still pass -- the relaxed rule only widens what's accepted."""
    assert validate_pr_body(LEGACY_DESCRIPTION_WHY_HOW_BODY) == []


def test_validate_passes_sectionless_prose_body() -> None:
    """Anthropic's trivial-PR shape is one sentence with no headers."""
    body = (
        "Pin third-party GitHub Actions references to immutable commit SHAs "
        "so a tag move cannot redirect CI to attacker-controlled code."
    )
    assert validate_pr_body(body) == []


def test_validate_blocks_skeleton_body_with_only_headers_and_bullets() -> None:
    """Sections + bullets without any prose Why is rejected -- the substantive-prose check catches this."""
    body = "## Summary\n\n## Changes\n\n- `a`\n- `b`\n- `c`\n"
    violations = validate_pr_body(body)
    assert any("substantive prose" in each_violation.lower() for each_violation in violations)


def test_validate_blocks_blockquoted_headings_with_no_real_prose() -> None:
    """Regression: blockquote markers must strip BEFORE heading stripping.

    A line like `> ## Summary` starts with `>`, so `^#+[ \\t].*$` cannot match it
    in heading position. If blockquote markers are stripped after, the bare
    `## Summary` text survives into the prose stream and inflates the count.
    Correct order strips `> ` first, then the line becomes a real heading and
    drops out, leaving an effectively empty body below the 40-character minimum.
    """
    body = "> ## Summary\n> ## Why\n> ## How"
    violations = validate_pr_body(body)
    assert any("substantive prose" in each_violation.lower() for each_violation in violations)


def test_validate_passes_prose_after_bare_hashes_with_no_space() -> None:
    """Bug regression: `##\\n` followed by prose must not have its prose eaten by the heading regex.

    The previous pattern `^#+\\s.*$` matched `\\s` against the newline, then `.*$` greedily
    consumed the next line. The fix restricts the whitespace class to `[ \\t]` so only true
    headings (`## text`) match, leaving prose-after-bare-hashes intact for substantive-prose counting.
    """
    body = (
        "##\nThis is real prose that should not be eaten by the heading regex, "
        "it should pass the 40-character minimum."
    )
    assert validate_pr_body(body) == []


def test_validate_blocks_vague_language() -> None:
    body = VALID_BODY + "\nFixed bug in the auth module.\n"
    violations = validate_pr_body(body)
    assert any("Vague language" in each_violation for each_violation in violations)


def test_vague_language_inside_fenced_code_block_is_exempt() -> None:
    body = (
        "The allocator now bounds retries so a runaway request cannot exhaust the "
        "connection pool under sustained load.\n\n"
        '```bash\ngit commit -m "fixed bug in parser"\n```\n'
    )
    assert not _has_vague_language_violation(validate_pr_body(body))


def test_vague_language_inside_inline_code_span_is_exempt() -> None:
    body = (
        "This change documents the historical commit message `fixed bug` referenced "
        "in the changelog and rewrites the surrounding allocator narrative for clarity.\n"
    )
    assert not _has_vague_language_violation(validate_pr_body(body))


def test_vague_language_inside_blockquote_line_is_exempt() -> None:
    body = (
        "> The reviewer wrote: minor changes were requested here.\n\n"
        "The allocator rewrite removes the unbounded retry loop and adds a hard ceiling "
        "so a single client cannot starve the pool.\n"
    )
    assert not _has_vague_language_violation(validate_pr_body(body))


def test_vague_language_inside_markdown_table_is_exempt() -> None:
    body = (
        "The commit-message guide contrasts weak and strong messages so contributors "
        "learn the difference before opening a pull request.\n\n"
        "| Bad message | Good message |\n"
        "| --- | --- |\n"
        "| fixed bug | bound retry loop in allocator |\n"
        "| update code | rename pool field to active_count |\n"
    )
    assert not _has_vague_language_violation(validate_pr_body(body))


def test_vague_language_in_bare_prose_still_blocks() -> None:
    body = (
        "The allocator rewrite removes the unbounded retry loop and adds a hard "
        "ceiling so a single client cannot starve the pool. Fixed bug in the parser.\n"
    )
    assert _has_vague_language_violation(validate_pr_body(body))


def test_vague_language_inside_heading_is_exempt() -> None:
    body = (
        "## Fixed bug in the allocator\n\n"
        "The allocator rewrite removes the unbounded retry loop and adds a hard "
        "ceiling so a single client cannot starve the connection pool.\n"
    )
    assert not _has_vague_language_violation(validate_pr_body(body))


def test_vague_language_in_single_pipe_prose_line_still_blocks() -> None:
    body = (
        "The allocator rewrite removes the unbounded retry loop and adds a hard "
        "ceiling so a single client cannot starve the connection pool.\n\n"
        "| fixed bug\n"
    )
    assert _has_vague_language_violation(validate_pr_body(body))


def test_validate_blocks_short_body() -> None:
    violations = validate_pr_body("Too short.")
    assert any("substantive prose" in each_violation.lower() for each_violation in violations)


def test_validate_heavy_body_passes_with_problem_and_test_plan() -> None:
    body = _build_heavy_body("## Problem", "## Test plan")
    assert validate_pr_body(body) == []


def test_validate_heavy_body_blocks_when_testing_category_missing() -> None:
    """Heavy body containing two opening-category headers but no testing-category header is blocked."""
    intro_text = (
        "Adds shape-aware validation across the pr-description-enforcer pipeline. "
        "The change unifies the body audit with the Anthropic claude-code style. "
        "The block reason names the missing category for the agent to fix on first try."
    )
    body = (
        f"{intro_text}\n\n"
        "## Summary\n\n"
        "Adds a check that heavy bodies carry both an opening header and a testing header. "
        "The substantive prose lives outside the bullet section so the audit treats the body "
        "as the heavy shape rather than the standard shape under the length threshold.\n\n"
        "## Problem\n\n"
        "The earlier flow rejected too many valid bodies on equivalence checks "
        "across the three shape categories described in the guide. The fix "
        "restructures the path around shape detection and surfaces the missing "
        "category in the block message so the agent can correct it without iterating.\n\n"
        "## Changes\n\n"
        "- `validator.py`: shape detection at the head of the audit pipeline\n"
        "- `enforcer.py`: dispatch the shape-aware checks before the substantive-prose audit\n"
    )
    violations = validate_pr_body(body)
    assert any("testing" in each_violation.lower() for each_violation in violations)


def test_validate_trivial_body_blocks_summary_header() -> None:
    """A Trivial-sized body that opens with `## Summary` is blocked as ceremony."""
    body = "## Summary\n\nPin Bun to 1.3.14."
    violations = validate_pr_body(body)
    assert any(
        "ceremony" in each_violation.lower() or "trivial" in each_violation.lower()
        for each_violation in violations
    )


def test_validate_trivial_body_blocks_test_plan_header() -> None:
    """A Trivial-sized body that opens with `## Test plan` must trip the
    ceremony-on-Trivial block. The guide says Trivial bodies have zero headers,
    so the enforcer must catch every heading variant — not just the six
    `Summary|Why|Overview|Description|Intro|TL;DR` originally enumerated."""
    body = "## Test plan\n\nPin Bun to 1.3.14."
    violations = validate_pr_body(body)
    assert any(
        "ceremony" in each_violation.lower() or "trivial" in each_violation.lower()
        for each_violation in violations
    ), f"Trivial body opening with `## Test plan` must trip ceremony block; got {violations!r}"


def test_validate_trivial_body_blocks_test_plan_after_prose() -> None:
    """The doc promises "Zero `##` headers" on Trivial bodies. The earlier check
    only inspected the first non-empty line, so prose followed by `## Test plan`
    slipped through. Tighten the check to reject ANY heading in a Trivial-sized
    body so the guide and the enforcer agree."""
    body = "Pin Bun to 1.3.14.\n\n## Test plan\n\n- bun test\n"
    violations = validate_pr_body(body)
    assert any(
        "ceremony" in each_violation.lower() or "trivial" in each_violation.lower()
        for each_violation in violations
    ), f"Trivial body with later `## Test plan` must trip the block; got {violations!r}"


def test_validate_trivial_body_blocks_h1_header() -> None:
    """A Trivial-sized body opening with an `# Overview` h1 must also block, since
    Trivial shape allows zero structural headers of any level."""
    body = "# Overview\n\nPin Bun to 1.3.14."
    violations = validate_pr_body(body)
    assert any(
        "ceremony" in each_violation.lower() or "trivial" in each_violation.lower()
        for each_violation in violations
    ), f"Trivial body opening with h1 must trip ceremony block; got {violations!r}"


def test_validate_standard_body_allows_summary_header() -> None:
    """A Standard-sized body that opens with `## Summary` passes the ceremony check."""
    body = (
        "## Summary\n\n"
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits. The pull engine compares the last-modified marker "
        "before applying a remote record.\n\n"
        "## Changes\n\n"
        "- `pullEngine.ts`: compare lastModified before overwriting\n"
        "- `pullEngine.test.ts`: 3 new cases\n"
    )
    violations = validate_pr_body(body)
    assert not any(
        "ceremony" in each_violation.lower() or "trivial" in each_violation.lower()
        for each_violation in violations
    )


def test_validate_blocks_self_closing_fixes_reference() -> None:
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nFixes #467.\n"
    )
    violations = validate_pr_body(body, pr_number=467)
    assert any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    )


def test_validate_blocks_self_closing_resolves_reference() -> None:
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nResolves #467.\n"
    )
    violations = validate_pr_body(body, pr_number=467)
    assert any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    )


def test_validate_blocks_lowercase_self_closing_fixes_reference() -> None:
    """GitHub treats closing keywords (Fixes/Closes/Resolves) case-insensitively, so
    a body opening with `fixes #<own-PR>` (lowercase) auto-closes the PR on merge
    just like the capitalized form. The enforcer must catch both."""
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nfixes #467.\n"
    )
    violations = validate_pr_body(body, pr_number=467)
    assert any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    ), f"lowercase fixes self-reference must trip the block; got {violations!r}"


def test_validate_blocks_self_closing_fix_singular_reference() -> None:
    """GitHub recognizes nine closing keywords (close/closes/closed,
    fix/fixes/fixed, resolve/resolves/resolved). The bare-stem variants
    `Fix #N`, `Close #N`, `Resolve #N` close the PR on merge just like the
    plural forms, so the enforcer must catch every variant."""
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nFix #467.\n"
    )
    violations = validate_pr_body(body, pr_number=467)
    assert any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    ), f"`Fix #<own-PR>` self-reference must trip the block; got {violations!r}"


def test_validate_blocks_self_closing_closed_past_tense_reference() -> None:
    """`Closed #<own-PR>` (past tense) closes the PR on merge; the enforcer
    must catch every closing-keyword variant including past tense."""
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nClosed #467.\n"
    )
    violations = validate_pr_body(body, pr_number=467)
    assert any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    ), f"`Closed #<own-PR>` self-reference must trip the block; got {violations!r}"


def test_validate_blocks_self_closing_resolved_past_tense_reference() -> None:
    """`Resolved #<own-PR>` closes the PR on merge."""
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nResolved #467.\n"
    )
    violations = validate_pr_body(body, pr_number=467)
    assert any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    ), f"`Resolved #<own-PR>` self-reference must trip the block; got {violations!r}"


def test_validate_blocks_uppercase_self_closing_closes_reference() -> None:
    """All-caps `CLOSES #<own-PR>` also auto-closes on GitHub; the enforcer must
    catch every case variant the same way GitHub does."""
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nCLOSES #467.\n"
    )
    violations = validate_pr_body(body, pr_number=467)
    assert any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    ), f"all-caps CLOSES self-reference must trip the block; got {violations!r}"


def test_validate_allows_fixes_reference_to_different_pr() -> None:
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits.\n\nFixes #467.\n"
    )
    violations = validate_pr_body(body, pr_number=999)
    assert not any(
        "self" in each_violation.lower() or "own pr" in each_violation.lower()
        for each_violation in violations
    )


def test_validate_blocks_this_pr_opening() -> None:
    body = (
        "This PR adds a timestamp check to prevent background data pulls from "
        "overwriting recent local edits. The pull engine compares the "
        "last-modified marker before applying a remote record."
    )
    violations = validate_pr_body(body)
    assert any("this pr" in each_violation.lower() for each_violation in violations)


def test_validate_blocks_this_pr_opening_with_non_allowlisted_verb() -> None:
    """The guide describes any `This PR ...` opening as a hard block, but
    `THIS_PR_OPENING_PATTERN` previously only matched a short allowlist of
    verbs (adds|fixes|updates|does|is|was|will|removes|tightens|ports|refactors).
    Variants like `This PR introduces`, `This PR improves`, `This PR enables`
    slipped through and broke the documented contract. Catch any
    `This PR` opening regardless of the following verb."""
    body = (
        "This PR introduces a multi-tier caching layer that wraps the existing "
        "request pipeline and improves median latency on the hot path."
    )
    violations = validate_pr_body(body)
    assert any("this pr" in each_violation.lower() for each_violation in violations), (
        f"`This PR introduces` opening must trip the block regardless of verb; got {violations!r}"
    )


def test_validate_blocks_this_pr_opening_with_improves() -> None:
    body = (
        "This PR improves the request batching algorithm so the dispatcher "
        "coalesces idempotent calls before the network round-trip."
    )
    violations = validate_pr_body(body)
    assert any("this pr" in each_violation.lower() for each_violation in violations), (
        f"`This PR improves` opening must trip the block; got {violations!r}"
    )


def test_validate_allows_imperative_opening() -> None:
    body = (
        "Adds a timestamp check to prevent background data pulls from "
        "overwriting recent local edits. The pull engine compares the "
        "last-modified marker before applying a remote record."
    )
    violations = validate_pr_body(body)
    assert not any("this pr" in each_violation.lower() for each_violation in violations)


def test_validate_heavy_body_without_required_headers_blocks() -> None:
    """End-to-end: a long body without `## Problem|Summary` or `## Test plan|...`
    must trip the Heavy missing-header violation. Previously the classifier
    bypassed Heavy classification because the body lacked the headers we were
    trying to require — a circular self-bypass."""
    long_body_missing_heavy_headers = (
        "Refactors the request-pipeline batcher to coalesce idempotent calls "
        "before the network round-trip. The change touches the dispatcher, the "
        "retry loop, the error normalizer, and three downstream consumers. "
        "Every test in the integration suite continues to pass without "
        "modification because the public contract is unchanged.\n\n"
        "The new coalescer reads a per-call digest, looks up an in-flight slot "
        "indexed by that digest, and appends the caller's promise to the slot "
        "instead of dispatching a duplicate request. Once the network response "
        "arrives, every queued promise resolves with the same value. Error "
        "responses propagate to every queued promise so retry logic stays "
        "consistent with the prior contract.\n"
    )
    violations = validate_pr_body(long_body_missing_heavy_headers)
    assert any("heavy" in each_violation.lower() for each_violation in violations), (
        f"Long body missing Heavy headers must trip the required-header check; got {violations!r}"
    )
