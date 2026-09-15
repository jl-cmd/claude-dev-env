"""Tests for the retired-hook-prose rule over rules Markdown."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from policy_lint import adapter_retired_hook_prose, registry
from policy_lint.model import ContentOrigin, Document, DocumentRule

_RULE_ID = "retired-hook-prose"
_RULES_DOCUMENT_PATH = "packages/claude-dev-env/rules/example.md"
_INSTALLER_SOURCE = """
export const RETIRED_HOOK_REGISTRATION_RELATIVE_PATHS = new Set([
    'blocking/destructive_command_blocker.py',
]);
"""
_HOOKS_CONFIGURATION = """
{
  "hooks": {
    "PostToolUse": [
      {"hooks": [{"command": "python hooks/observability/session_file_edit_tracker.py"}]}
    ]
  }
}
"""
_DISPATCHER_ROSTER_SOURCE = """
ALL_HOSTED_HOOK_ENTRIES = (
    HostedHookEntry("advisory/refactor_guard.py", is_blocking=False),
)
"""


def _build_package(repository_root: Path) -> None:
    package_root = repository_root / "packages" / "claude-dev-env"
    hooks_root = package_root / "hooks"
    (hooks_root / "blocking").mkdir(parents=True)
    (hooks_root / "advisory").mkdir(parents=True)
    (hooks_root / "observability").mkdir(parents=True)
    (hooks_root / "hooks_constants").mkdir(parents=True)
    (package_root / "bin").mkdir(parents=True)
    (package_root / "rules").mkdir(parents=True)
    (hooks_root / "blocking" / "windows_rmtree_blocker.py").write_text("", "utf-8")
    (hooks_root / "advisory" / "refactor_guard.py").write_text("", "utf-8")
    (hooks_root / "observability" / "session_file_edit_tracker.py").write_text(
        "", "utf-8"
    )
    (hooks_root / "blocking" / "content_hash_store.py").write_text("", "utf-8")
    (hooks_root / "hooks.json").write_text(_HOOKS_CONFIGURATION, "utf-8")
    (
        hooks_root / "hooks_constants" / "pre_tool_use_dispatcher_constants.py"
    ).write_text(_DISPATCHER_ROSTER_SOURCE, "utf-8")
    (package_root / "bin" / "install.mjs").write_text(_INSTALLER_SOURCE, "utf-8")


def _diagnostics_for(repository_root: Path, prose: str) -> tuple[str, ...]:
    document = Document(
        PurePosixPath(_RULES_DOCUMENT_PATH),
        prose,
        None,
        None,
        ContentOrigin.WORKTREE,
    )
    all_diagnostics = adapter_retired_hook_prose.retired_hook_prose_diagnostics(
        document, repository_root
    )
    return tuple(each_diagnostic.message for each_diagnostic in all_diagnostics)


def test_a_live_claim_for_a_surviving_unregistered_hook_is_reported(
    tmp_path: Path,
) -> None:
    _build_package(tmp_path)
    all_messages = _diagnostics_for(
        tmp_path,
        "The `windows_rmtree_blocker.py` PreToolUse hook blocks the unsafe pattern.\n",
    )
    assert len(all_messages) == 1
    assert "windows_rmtree_blocker" in all_messages[0]


def test_a_live_claim_for_a_roster_hook_absent_from_disk_is_reported(
    tmp_path: Path,
) -> None:
    _build_package(tmp_path)
    all_messages = _diagnostics_for(
        tmp_path,
        "The `destructive_command_blocker` hook watches every Bash-tool command.\n",
    )
    assert len(all_messages) == 1
    assert "destructive_command_blocker" in all_messages[0]


def test_a_registered_hook_described_in_the_present_tense_passes(
    tmp_path: Path,
) -> None:
    _build_package(tmp_path)
    all_messages = _diagnostics_for(
        tmp_path,
        "`session_file_edit_tracker` records each Write path, and `refactor_guard` reports a risk.\n",
    )
    assert all_messages == ()


def test_a_past_tense_retirement_sentence_passes(tmp_path: Path) -> None:
    _build_package(tmp_path)
    all_messages = _diagnostics_for(
        tmp_path,
        "Commit `0f21faf8e` retired the blocking hooks. "
        "`destructive_command_blocker` was one of them.\n",
    )
    assert all_messages == ()


def test_a_sentence_crediting_the_staged_policy_lint_passes(tmp_path: Path) -> None:
    _build_package(tmp_path)
    all_messages = _diagnostics_for(
        tmp_path,
        "`windows_rmtree_blocker.py` reports the unsafe pattern, "
        "and the staged policy lint runs it over each changed file.\n",
    )
    assert all_messages == ()


def test_a_hook_directory_support_module_passes(tmp_path: Path) -> None:
    _build_package(tmp_path)
    all_messages = _diagnostics_for(
        tmp_path,
        "`content_hash_store.py` holds the full contract in its module docstring.\n",
    )
    assert all_messages == ()


def test_a_verb_before_the_hook_name_passes(tmp_path: Path) -> None:
    _build_package(tmp_path)
    all_messages = _diagnostics_for(
        tmp_path,
        "The staged lint runs `windows_rmtree_blocker.py` over each changed file.\n",
    )
    assert all_messages == ()


def test_a_code_span_between_the_name_and_its_verb_does_not_hide_the_claim(
    tmp_path: Path,
) -> None:
    _build_package(tmp_path)
    all_messages = _diagnostics_for(
        tmp_path,
        "`destructive_command_blocker` (PreToolUse on Bash `git commit`) "
        "denies a commit that drops session edits.",
    )
    assert len(all_messages) == 1
    assert "destructive_command_blocker" in all_messages[0]


def test_a_second_hook_name_bounds_the_first_claim(tmp_path: Path) -> None:
    _build_package(tmp_path)
    all_messages = _diagnostics_for(
        tmp_path,
        "`destructive_command_blocker` was retired, and `refactor_guard` reports a risk.",
    )
    assert all_messages == ()


def test_the_rule_is_registered_for_changed_and_repository_selections() -> None:
    all_matching_rules = tuple(
        each_rule
        for each_rule in registry.default_registry()
        if each_rule.rule_id == _RULE_ID
    )
    assert len(all_matching_rules) == 1
    registered_rule = all_matching_rules[0]
    assert isinstance(registered_rule, DocumentRule)
    assert registered_rule.rule_sets == frozenset({"changed", "repository"})


def test_the_committed_rules_directory_names_no_gate_that_stopped_running() -> None:
    repository_root = Path(__file__).resolve().parents[4]
    rules_root = repository_root / "packages" / "claude-dev-env" / "rules"
    all_messages: list[str] = []
    for each_path in sorted(rules_root.glob("*.md")):
        relative_path = each_path.relative_to(repository_root).as_posix()
        document = Document(
            PurePosixPath(relative_path),
            each_path.read_text(encoding="utf-8"),
            None,
            None,
            ContentOrigin.WORKTREE,
        )
        all_messages.extend(
            f"{relative_path}:{each_diagnostic.location.start_line}: {each_diagnostic.message}"
            for each_diagnostic in (
                adapter_retired_hook_prose.retired_hook_prose_diagnostics(
                    document, repository_root
                )
            )
        )
    assert all_messages == []
