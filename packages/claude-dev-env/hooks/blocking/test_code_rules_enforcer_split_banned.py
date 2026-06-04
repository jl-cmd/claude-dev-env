"""Behavior tests for the code_rules_banned_identifiers code-rules check module."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_banned_identifiers import (  # noqa: E402
    ALL_BANNED_IDENTIFIERS,
    BANNED_IDENTIFIER_MESSAGE_SUFFIX,
    BANNED_IDENTIFIER_SKIP_ADVISORY,
    MAX_BANNED_IDENTIFIER_ISSUES,
    check_banned_noun_word_boundary,
)

from hooks_constants.banned_identifiers_constants import (  # noqa: E402
    ALL_BANNED_IDENTIFIERS as config_all_banned_identifiers,
)
from hooks_constants.banned_identifiers_constants import (  # noqa: E402
    BANNED_IDENTIFIER_MESSAGE_SUFFIX as config_banned_identifier_message_suffix,
)
from hooks_constants.banned_identifiers_constants import (  # noqa: E402
    BANNED_IDENTIFIER_SKIP_ADVISORY as config_banned_identifier_skip_advisory,
)
from hooks_constants.banned_identifiers_constants import (  # noqa: E402
    MAX_BANNED_IDENTIFIER_ISSUES as config_max_banned_identifier_issues,
)

code_rules_enforcer = SimpleNamespace(
    ALL_BANNED_IDENTIFIERS=ALL_BANNED_IDENTIFIERS,
    BANNED_IDENTIFIER_MESSAGE_SUFFIX=BANNED_IDENTIFIER_MESSAGE_SUFFIX,
    BANNED_IDENTIFIER_SKIP_ADVISORY=BANNED_IDENTIFIER_SKIP_ADVISORY,
    MAX_BANNED_IDENTIFIER_ISSUES=MAX_BANNED_IDENTIFIER_ISSUES,
    check_banned_noun_word_boundary=check_banned_noun_word_boundary,
)


def test_should_expose_all_banned_identifiers_from_config() -> None:
    expected_banned_identifiers = frozenset({
        "result", "data", "output", "response", "value", "item", "temp",
        "argv", "args", "kwargs", "argc",
    })
    actual_banned_identifiers = getattr(
        code_rules_enforcer, "ALL_BANNED_IDENTIFIERS", None
    )
    assert actual_banned_identifiers is not None, (
        "Renamed constant ALL_BANNED_IDENTIFIERS must be importable from "
        "config/banned_identifiers_constants.py and re-exposed on the "
        f"enforcer module, got: {actual_banned_identifiers!r}"
    )
    assert expected_banned_identifiers <= actual_banned_identifiers, (
        "ALL_BANNED_IDENTIFIERS must contain every expected banned identifier; "
        f"missing: {expected_banned_identifiers - actual_banned_identifiers!r}"
    )


def test_should_source_banned_identifier_companion_constants_from_config() -> None:
    assert (
        code_rules_enforcer.MAX_BANNED_IDENTIFIER_ISSUES
        is config_max_banned_identifier_issues
    )
    assert (
        code_rules_enforcer.BANNED_IDENTIFIER_MESSAGE_SUFFIX
        is config_banned_identifier_message_suffix
    )
    assert (
        code_rules_enforcer.BANNED_IDENTIFIER_SKIP_ADVISORY
        is config_banned_identifier_skip_advisory
    )


def test_should_reexport_all_banned_identifiers_from_config() -> None:
    assert code_rules_enforcer.ALL_BANNED_IDENTIFIERS is config_all_banned_identifiers


def test_banned_noun_word_skips_non_aliased_upstream_import() -> None:
    """A non-aliased upstream import the author cannot rename
    (`from typing import ItemsView`) must not be flagged, while an
    author-coined alias still is."""
    production_path = "packages/myapp/services/customer_pipeline.py"
    upstream_issues = code_rules_enforcer.check_banned_noun_word_boundary(
        "from typing import ItemsView\n", production_path
    )
    aliased_issues = code_rules_enforcer.check_banned_noun_word_boundary(
        "import legacy_helper as cached_response\n", production_path
    )
    assert upstream_issues == []
    assert any("cached_response" in each_issue for each_issue in aliased_issues)


def test_banned_noun_word_defers_scope_to_caller_when_requested() -> None:
    """loop7-P1: when the gate sets the deferral flag, the banned-noun check must
    return every violation so ``split_violations_by_scope`` can scope by added
    line before reporting the in-scope set."""
    binding_count = 5
    source = "".join(
        f"BINDING_{each_index}_RESULT_PATH = {each_index}\n"
        for each_index in range(binding_count)
    )
    issues = code_rules_enforcer.check_banned_noun_word_boundary(
        source,
        "/project/src/many_nouns.py",
        defer_scope_to_caller=True,
    )
    assert len(issues) == binding_count, (
        "deferral must return every banned-noun violation, "
        f"got: {issues!r}"
    )


def test_banned_noun_message_carries_binding_line_span() -> None:
    """A banned-noun binding carries its own binding line as a one-line span so
    the commit gate reconstructs it through the same shared span mechanism the
    other diff-scoped checks use, while keeping the Line N: prefix intact. The
    binding-line granularity matches the companion exact-match
    check_banned_identifiers and avoids re-flagging a pre-existing binding when
    an unrelated line of its enclosing function is edited."""
    source = (
        "def aggregate() -> list[int]:\n"
        "    canned_results = [1, 2, 3]\n"
        "    return canned_results\n"
    )
    issues = code_rules_enforcer.check_banned_noun_word_boundary(
        source, "/project/src/has_noun.py"
    )
    binding_line = 2
    expected_fragment = f"(binding span at line {binding_line}, spanning 1 lines)"
    assert any(
        each_issue.startswith(f"Line {binding_line}:") and expected_fragment in each_issue
        for each_issue in issues
    ), f"banned-noun message must carry the binding-line span fragment, got: {issues!r}"


def test_banned_noun_message_module_level_binding_spans_one_line() -> None:
    """A module-level banned-noun binding spans its own binding line alone
    (span 1)."""
    source = "SAFE_OUTPUT_PATH = '/var/run/x'\n"
    issues = code_rules_enforcer.check_banned_noun_word_boundary(
        source, "/project/src/module_noun.py"
    )
    expected_fragment = "(binding span at line 1, spanning 1 lines)"
    assert any(expected_fragment in each_issue for each_issue in issues), (
        f"module-level banned-noun span must be one line, got: {issues!r}"
    )


def test_banned_noun_word_boundary_flags_plural_results_identifier() -> None:
    """A plural banned noun ('results') embedded in an identifier must flag.

    ``ALL_BANNED_NOUN_WORDS`` contains plural forms (results, outputs,
    responses, values, items) in addition to the singular nouns, so an
    identifier such as ``canned_results`` is flagged even though no singular
    exact-match identifier appears.
    """
    source = "canned_results = []\n"
    issues = code_rules_enforcer.check_banned_noun_word_boundary(
        source, "/project/src/pipeline.py"
    )
    assert any("canned_results" in each_issue for each_issue in issues), (
        "a plural banned-noun identifier must be flagged by the word-boundary "
        f"check; got: {issues!r}"
    )
