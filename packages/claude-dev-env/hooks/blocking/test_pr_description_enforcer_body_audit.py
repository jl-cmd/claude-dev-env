"""Unit tests for pr-description-enforcer body markdown and shape helpers."""

import importlib.util
import pathlib
import re as _re
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
_HOOKS_ROOT = _HOOK_DIR.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

from hooks_constants.pr_description_enforcer_constants import ALL_HEAVY_OPENING_HEADERS

body_audit_spec = importlib.util.spec_from_file_location(
    "pr_description_body_audit",
    _HOOK_DIR / "pr_description_body_audit.py",
)
assert body_audit_spec is not None
assert body_audit_spec.loader is not None
hook_module = importlib.util.module_from_spec(body_audit_spec)
body_audit_spec.loader.exec_module(hook_module)


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


def test_compute_pr_body_shape_trivial() -> None:
    """A short single-sentence body with zero headers classifies as Trivial."""
    body = "Pin third-party GitHub Actions references to immutable commit SHAs."
    assert hook_module._compute_pr_body_shape(body) == "trivial"


def test_compute_pr_body_shape_standard() -> None:
    """A medium body with one ## header below the Heavy threshold classifies as Standard."""
    body = (
        "Adds a timestamp check to prevent background data pulls from overwriting "
        "recent local edits. The pull engine compares the last-modified marker "
        "before deciding whether to apply a remote record.\n\n"
        "## Changes\n\n"
        "- `pullEngine.ts`: compare lastModified before overwriting\n"
        "- `pullEngine.test.ts`: 3 new cases\n"
    )
    assert hook_module._compute_pr_body_shape(body) == "standard"


def test_compute_pr_body_shape_heavy() -> None:
    """A long body with two Heavy-detection headers classifies as Heavy."""
    body = _build_heavy_body("## Problem", "## Test plan")
    assert hook_module._compute_pr_body_shape(body) == "heavy"


def test_first_non_empty_line_helper_is_removed() -> None:
    """`_first_non_empty_line` was the basis of the prior ceremony-on-Trivial
    check, which now uses `_iter_section_headers`. The helper has no remaining
    call sites; pin its removal so it cannot drift back as dead code."""
    assert not hasattr(hook_module, "_first_non_empty_line"), (
        "_first_non_empty_line must be removed; the ceremony-on-Trivial check "
        "now reads through _iter_section_headers instead."
    )


def test_strip_leading_hash_lines_helper_is_removed() -> None:
    """The unused leading-hash stripper must not exist as a module attribute."""
    assert not hasattr(hook_module, "_strip_leading_hash_lines")


def test_strip_markdown_ceremony_returns_stripped_prose() -> None:
    """The shared markdown stripper removes fences, inline code, blockquotes,
    headings, bullets, bold, emphasis, and Markdown link targets, leaving the
    underlying prose intact."""
    body = "\n".join(
        [
            "# Heading text",
            "> blockquoted content",
            "- bullet content",
            "**bold body**",
            "*emphasized body*",
            "[link label](https://example.com)",
            "`inline code body`",
            "```",
            "fenced code body",
            "```",
            "plain prose line",
        ]
    )
    stripped = hook_module.strip_markdown_ceremony(body)
    assert "Heading text" not in stripped
    assert "blockquoted content" in stripped
    assert "bullet content" in stripped
    assert "bold body" in stripped
    assert "emphasized body" in stripped
    assert "link label" in stripped
    assert "plain prose line" in stripped
    assert "inline code body" not in stripped
    assert "fenced code body" not in stripped
    assert "https://example.com" not in stripped


def test_strip_markdown_ceremony_used_by_substantive_prose_count() -> None:
    """_count_substantive_prose_chars is consistent with the shared stripper:
    its returned count matches len of the whitespace-collapsed stripped body."""
    body = "# Heading\n\nA single paragraph of prose with **bold** and `code` words."
    stripped = hook_module.strip_markdown_ceremony(body)
    collapsed = _re.sub(r"\s+", " ", stripped).strip()
    assert hook_module._count_substantive_prose_chars(body) == len(collapsed)


def test_shape_classifier_uses_substantive_chars_not_raw_length() -> None:
    """Shape classifier and ceremony-on-Trivial check must agree on the metric used
    against TRIVIAL_BODY_CHAR_THRESHOLD. A body whose raw length passes the
    threshold but whose substantive prose does not (e.g. tiny prose with a large
    fenced code block) is genuinely Trivial in shape -- not Standard."""
    tiny_prose_with_large_code_fence = "Done.\n\n```\n" + ("x" * 300) + "\n```"
    assert len(tiny_prose_with_large_code_fence) >= hook_module.TRIVIAL_BODY_CHAR_THRESHOLD
    assert (
        hook_module._count_substantive_prose_chars(tiny_prose_with_large_code_fence)
        < hook_module.TRIVIAL_BODY_CHAR_THRESHOLD
    )
    assert hook_module._compute_pr_body_shape(tiny_prose_with_large_code_fence) == "trivial"


def test_body_contains_any_header_rejects_plural_extension() -> None:
    """`_body_contains_any_header` must enforce a word boundary after the
    canonical header text. `## Problems` (plural) extends the canonical
    word and must NOT satisfy `## Problem`, otherwise the Heavy
    required-header check is weaker than the documented contract."""
    body_with_plural_extension = "## Problems\n\nDetails follow."
    candidate_set = frozenset({"## Problem"})
    assert not hook_module._body_contains_any_header(body_with_plural_extension, candidate_set), (
        "`## Problems` must NOT satisfy `## Problem` (different header)"
    )


def test_body_contains_any_header_accepts_punctuation_suffix() -> None:
    """The boundary rule must still accept canonical headers followed by
    non-word punctuation: colon, em-dash, parenthesis, trailing whitespace.
    Reviewers write `## Problem (context)` and `## Test plan: scope` —
    these must continue to satisfy the canonical headers."""
    candidate_set = frozenset({"## Problem"})
    for each_body in [
        "## Problem\n\nDetails.",
        "## Problem:\n\nDetails.",
        "## Problem (context)\n\nDetails.",
        "## Problem — context\n\nDetails.",
    ]:
        assert hook_module._body_contains_any_header(each_body, candidate_set), (
            f"`{each_body!r}` must satisfy `## Problem` (punctuation/space follows)"
        )


def test_body_contains_any_header_rejects_alphanumeric_suffix() -> None:
    """`## Problem2`, `## ProblemX`, `## Problem_one` are different headers
    and must not match `## Problem`."""
    candidate_set = frozenset({"## Problem"})
    for each_body in [
        "## Problem2\n\nDetails.",
        "## ProblemX\n\nDetails.",
        "## Problem_one\n\nDetails.",
    ]:
        assert not hook_module._body_contains_any_header(each_body, candidate_set), (
            f"`{each_body!r}` must NOT satisfy `## Problem` (alphanumeric continuation)"
        )


def test_iter_section_headers_ignores_headings_inside_fenced_code_blocks() -> None:
    """Headings nested inside ``` ... ``` fences are example content, not body headers.
    The shape classifier and the Heavy required-header check must agree with the markdown
    stripper -- the body of this very test demonstrates the regression."""
    body = (
        "Intro paragraph that does not classify the body.\n\n```\n## Problem\n## Test plan\n```\n"
    )
    headers = hook_module._iter_section_headers(body)
    assert headers == [], f"Expected zero headers (fenced content), got {headers}"
    assert hook_module._compute_pr_body_shape(body) != "heavy", (
        "Body with only fenced example headers must not classify as heavy"
    )
    assert hook_module._body_contains_any_header(body, ALL_HEAVY_OPENING_HEADERS) is False, (
        "Heavy opening-header check must not see fenced example content"
    )


def test_long_body_without_heavy_headers_still_classifies_heavy() -> None:
    """The Heavy required-header check in `validate_pr_body` only runs when
    `_compute_pr_body_shape` returns HEAVY. Previously the classifier required
    BOTH length >= 500 chars AND >= 2 heavy detection headers, which meant a
    long body missing the required headers entirely was classified Standard
    and silently bypassed the missing-header enforcement. Length alone must
    drive the HEAVY classification so the validator can enforce the rule."""
    long_body_with_no_heavy_headers = (
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
    assert (
        hook_module._count_substantive_prose_chars(long_body_with_no_heavy_headers)
        >= hook_module.HEAVY_MIN_BODY_CHARS_FOR_CLASSIFICATION
    )
    assert (
        hook_module._compute_pr_body_shape(long_body_with_no_heavy_headers)
        == hook_module.HEAVY_SHAPE
    )


def test_compute_pr_body_shape_uses_named_shape_constants() -> None:
    """`_compute_pr_body_shape` returns the centralised shape names rather than
    inline string literals. Confirm the constants flow through end-to-end."""
    trivial_body = "Bump bun to 1.3.14."
    assert hook_module._compute_pr_body_shape(trivial_body) == hook_module.TRIVIAL_SHAPE


def test_iter_section_headers_docstring_matches_actual_pattern() -> None:
    """`_iter_section_headers` uses `HEADING_LINE_PATTERN = ^#+`, so it returns
    every ATX heading level (`#`, `##`, `###`...), not just `##`. The docstring
    must describe that actual contract so callers cannot be misled."""
    docstring = hook_module._iter_section_headers.__doc__ or ""
    assert "every ATX heading" in docstring or "any heading level" in docstring, (
        f"_iter_section_headers docstring must document that it matches every "
        f"heading level (`HEADING_LINE_PATTERN` is `^#+`); got: {docstring!r}"
    )
