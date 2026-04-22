"""Tests for es_exe_path_rewriter — PreToolUse hook that rewrites es.exe paths."""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

_BLOCKING_DIR = Path(__file__).resolve().parent
_HOOKS_ROOT = _BLOCKING_DIR.parent
for each_sys_path_entry in (str(_BLOCKING_DIR), str(_HOOKS_ROOT)):
    if each_sys_path_entry not in sys.path:
        sys.path.insert(0, each_sys_path_entry)

import es_exe_path_rewriter as rewriter


def test_rewriter_does_not_redefine_dynamic_stderr_handler_locally() -> None:
    """Pin PR #230 round 3 DRY fix: handler is imported from the shared module.

    Both project_paths_reader and es_exe_path_rewriter previously defined
    identical `_DynamicStderrHandler` classes. This test fails if the
    duplicate class reappears in es_exe_path_rewriter.
    """
    assert not hasattr(rewriter, "_DynamicStderrHandler")


REGISTRY_WITH_ONE_REPO = {"my-repo": "Y:\\Projects\\my-repo"}
REGISTRY_WITH_TWO_REPOS = {
    "my-repo": "Y:\\Projects\\my-repo",
    "other-repo": "C:\\Dev\\other-repo",
}
ABSOLUTE_PATH_ARGUMENT = "Y:\\Projects\\already-absolute\\file.py"
KNOWN_REPO_NAME = "my-repo"
KNOWN_REPO_PATH = "Y:\\Projects\\my-repo"
OTHER_REPO_NAME = "other-repo"
OTHER_REPO_PATH = "C:\\Dev\\other-repo"


def _run_main_with_input(hook_input: dict) -> tuple[str, str, int]:
    """Return (stdout, stderr, exit_code) from running main() with the given hook input."""
    stdin_text = json.dumps(hook_input)
    captured_stdout = StringIO()
    captured_stderr = StringIO()
    exit_code = 0
    try:
        with (
            patch("sys.stdin", StringIO(stdin_text)),
            patch("sys.stdout", captured_stdout),
            patch("sys.stderr", captured_stderr),
        ):
            rewriter.main()
    except SystemExit as e:
        exit_code = e.code or 0
    return captured_stdout.getvalue(), captured_stderr.getvalue(), exit_code


def _make_bash_input(command: str, description: str = "search files") -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command, "description": description},
    }


class TestTriggerRegex:
    def test_matches_bare_es_exe(self) -> None:
        assert rewriter.command_invokes_es_exe("es.exe my-repo")

    def test_matches_everything_forward_slash_path(self) -> None:
        assert rewriter.command_invokes_es_exe("Everything/es.exe my-repo")

    def test_matches_everything_backslash_path(self) -> None:
        assert rewriter.command_invokes_es_exe("Everything\\es.exe my-repo")

    def test_does_not_match_unrelated_command(self) -> None:
        assert not rewriter.command_invokes_es_exe("git status")

    def test_does_not_match_es_exe_inside_longer_word(self) -> None:
        assert not rewriter.command_invokes_es_exe("not_es.exe_here")

    def test_matches_case_insensitively(self) -> None:
        assert rewriter.command_invokes_es_exe("ES.EXE my-repo")


class TestRewriteCommand:
    def test_bare_token_rewrite_substitutes_registry_path(self) -> None:
        rewritten = rewriter.rewrite_command(
            "es.exe my-repo config.py", REGISTRY_WITH_ONE_REPO
        )
        assert rewritten == f'es.exe "{KNOWN_REPO_PATH}" config.py'

    def test_placeholder_token_rewrite_substitutes_registry_path(self) -> None:
        rewritten = rewriter.rewrite_command(
            'es.exe "{my-repo}" config.py', REGISTRY_WITH_ONE_REPO
        )
        assert rewritten == f'es.exe "{KNOWN_REPO_PATH}" config.py'

    def test_single_quoted_placeholder_rewrite_substitutes_registry_path(self) -> None:
        rewritten = rewriter.rewrite_command(
            "es.exe '{my-repo}' config.py", REGISTRY_WITH_ONE_REPO
        )
        assert rewritten == f'es.exe "{KNOWN_REPO_PATH}" config.py'

    def test_placeholder_without_quotes_rewrite_substitutes_registry_path(self) -> None:
        rewritten = rewriter.rewrite_command(
            "es.exe {my-repo} config.py", REGISTRY_WITH_ONE_REPO
        )
        assert rewritten == f'es.exe "{KNOWN_REPO_PATH}" config.py'

    def test_absolute_path_argument_is_never_modified(self) -> None:
        command = f'es.exe "{ABSOLUTE_PATH_ARGUMENT}" config.py'
        rewritten = rewriter.rewrite_command(command, REGISTRY_WITH_ONE_REPO)
        assert rewritten == command

    def test_unknown_token_is_never_touched(self) -> None:
        command = "es.exe unknown-name config.py"
        rewritten = rewriter.rewrite_command(command, REGISTRY_WITH_ONE_REPO)
        assert rewritten == command

    def test_multiple_tokens_all_rewrite(self) -> None:
        command = "es.exe my-repo other-repo config.py"
        rewritten = rewriter.rewrite_command(command, REGISTRY_WITH_TWO_REPOS)
        assert rewritten == f'es.exe "{KNOWN_REPO_PATH}" "{OTHER_REPO_PATH}" config.py'

    def test_empty_registry_returns_unchanged_command(self) -> None:
        command = "es.exe my-repo config.py"
        rewritten = rewriter.rewrite_command(command, {})
        assert rewritten == command

    def test_double_spaces_inside_quoted_arg_pass_through_unchanged_on_no_registry_hit(
        self,
    ) -> None:
        command = 'es.exe "foo  bar" baz'
        rewritten = rewriter.rewrite_command(command, REGISTRY_WITH_ONE_REPO)
        assert rewritten == command

    def test_tab_separator_is_preserved_when_bare_token_is_rewritten(self) -> None:
        registry = {"my-repo": "Y:\\Projects\\my-repo"}
        command = "es.exe my-repo\tconfig.py"
        rewritten = rewriter.rewrite_command(command, registry)
        assert rewritten == f'es.exe "Y:\\Projects\\my-repo"\tconfig.py'

    def test_multiple_substitutions_preserve_all_inter_token_whitespace(self) -> None:
        command = "es.exe my-repo  other-repo   config.py"
        rewritten = rewriter.rewrite_command(command, REGISTRY_WITH_TWO_REPOS)
        assert rewritten == f'es.exe "{KNOWN_REPO_PATH}"  "{OTHER_REPO_PATH}"   config.py'


class TestEmittedJsonShape:
    def test_emitted_json_has_correct_hook_event_name(self) -> None:
        hook_input = _make_bash_input(f"es.exe {KNOWN_REPO_NAME} config.py")
        with patch(
            "es_exe_path_rewriter.load_registry", return_value=REGISTRY_WITH_ONE_REPO
        ):
            stdout, _, _ = _run_main_with_input(hook_input)
        emitted = json.loads(stdout)
        assert emitted["hookSpecificOutput"]["hookEventName"] == "PreToolUse"

    def test_emitted_json_has_allow_permission_decision(self) -> None:
        hook_input = _make_bash_input(f"es.exe {KNOWN_REPO_NAME} config.py")
        with patch(
            "es_exe_path_rewriter.load_registry", return_value=REGISTRY_WITH_ONE_REPO
        ):
            stdout, _, _ = _run_main_with_input(hook_input)
        emitted = json.loads(stdout)
        assert emitted["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_emitted_json_has_rewritten_command(self) -> None:
        hook_input = _make_bash_input(f"es.exe {KNOWN_REPO_NAME} config.py")
        with patch(
            "es_exe_path_rewriter.load_registry", return_value=REGISTRY_WITH_ONE_REPO
        ):
            stdout, _, _ = _run_main_with_input(hook_input)
        emitted = json.loads(stdout)
        updated_command = emitted["hookSpecificOutput"]["updatedInput"]["command"]
        assert updated_command == f'es.exe "{KNOWN_REPO_PATH}" config.py'

    def test_description_field_round_trips_unchanged(self) -> None:
        original_description = "my special search description"
        hook_input = _make_bash_input(
            f"es.exe {KNOWN_REPO_NAME} config.py", original_description
        )
        with patch(
            "es_exe_path_rewriter.load_registry", return_value=REGISTRY_WITH_ONE_REPO
        ):
            stdout, _, _ = _run_main_with_input(hook_input)
        emitted = json.loads(stdout)
        assert (
            emitted["hookSpecificOutput"]["updatedInput"]["description"]
            == original_description
        )

    def test_additional_unknown_fields_pass_through_into_updated_input(self) -> None:
        hook_input = {
            "tool_name": "Bash",
            "tool_input": {
                "command": f"es.exe {KNOWN_REPO_NAME} config.py",
                "description": "search",
                "extra_field": "extra_value",
            },
        }
        with patch(
            "es_exe_path_rewriter.load_registry", return_value=REGISTRY_WITH_ONE_REPO
        ):
            stdout, _, _ = _run_main_with_input(hook_input)
        emitted = json.loads(stdout)
        assert (
            emitted["hookSpecificOutput"]["updatedInput"]["extra_field"]
            == "extra_value"
        )

    def test_no_code_path_returns_deny_decision(self) -> None:
        for command in [
            f"es.exe {KNOWN_REPO_NAME} config.py",
            "es.exe unknown-token config.py",
            "git status",
        ]:
            hook_input = _make_bash_input(command)
            with patch(
                "es_exe_path_rewriter.load_registry",
                return_value=REGISTRY_WITH_ONE_REPO,
            ):
                stdout, _, _ = _run_main_with_input(hook_input)
            if stdout.strip():
                emitted = json.loads(stdout)
                decision = emitted.get("hookSpecificOutput", {}).get(
                    "permissionDecision", ""
                )
                assert decision != "deny", f"deny returned for command: {command!r}"


class TestNoOutputCases:
    def test_non_es_exe_command_produces_no_output(self) -> None:
        hook_input = _make_bash_input("git status")
        with patch(
            "es_exe_path_rewriter.load_registry", return_value=REGISTRY_WITH_ONE_REPO
        ):
            stdout, _, _ = _run_main_with_input(hook_input)
        assert stdout.strip() == ""

    def test_empty_registry_produces_no_output(self) -> None:
        hook_input = _make_bash_input(f"es.exe {KNOWN_REPO_NAME} config.py")
        with patch("es_exe_path_rewriter.load_registry", return_value={}):
            stdout, _, _ = _run_main_with_input(hook_input)
        assert stdout.strip() == ""

    def test_unchanged_command_produces_no_output(self) -> None:
        hook_input = _make_bash_input("es.exe unknown-token config.py")
        with patch(
            "es_exe_path_rewriter.load_registry", return_value=REGISTRY_WITH_ONE_REPO
        ):
            stdout, _, _ = _run_main_with_input(hook_input)
        assert stdout.strip() == ""

    def test_malformed_registry_produces_no_output_and_one_stderr_line(self) -> None:
        hook_input = _make_bash_input(f"es.exe {KNOWN_REPO_NAME} config.py")
        with patch(
            "es_exe_path_rewriter.load_registry",
            side_effect=Exception("simulated read error"),
        ):
            stdout, stderr, _ = _run_main_with_input(hook_input)
        assert stdout.strip() == ""
        assert stderr.strip() != ""
        assert stderr.strip().count("\n") == 0

    def test_non_bash_tool_produces_no_output(self) -> None:
        hook_input = {
            "tool_name": "Write",
            "tool_input": {"command": f"es.exe {KNOWN_REPO_NAME}"},
        }
        with patch(
            "es_exe_path_rewriter.load_registry", return_value=REGISTRY_WITH_ONE_REPO
        ):
            stdout, _, _ = _run_main_with_input(hook_input)
        assert stdout.strip() == ""


class TestQuoteAwareTokenizer:
    def test_double_quoted_multiword_arg_with_registry_key_prefix_is_not_substituted(
        self,
    ) -> None:
        registry = {"my-repo": "Y:\\Projects\\my-repo"}
        command = 'es.exe "my-repo foo" baz'
        rewritten = rewriter.rewrite_command(command, registry)
        assert rewritten == command

    def test_single_quoted_multiword_arg_with_registry_key_prefix_is_not_substituted(
        self,
    ) -> None:
        registry = {"my-repo": "Y:\\Projects\\my-repo"}
        command = "es.exe 'my-repo baz' config.py"
        rewritten = rewriter.rewrite_command(command, registry)
        assert rewritten == command

    def test_bare_token_matching_registry_key_is_rewritten(self) -> None:
        registry = {"my-repo": "Y:\\Projects\\my-repo"}
        command = "es.exe my-repo config.py"
        rewritten = rewriter.rewrite_command(command, registry)
        assert rewritten == f'es.exe "Y:\\Projects\\my-repo" config.py'

    def test_whitespace_between_bare_tokens_is_preserved_after_rewrite(self) -> None:
        registry = {"my-repo": "Y:\\Projects\\my-repo", "other-repo": "C:\\Dev\\other"}
        command = "es.exe my-repo  other-repo   config.py"
        rewritten = rewriter.rewrite_command(command, registry)
        assert rewritten == f'es.exe "Y:\\Projects\\my-repo"  "C:\\Dev\\other"   config.py'

    def test_tab_separator_is_preserved_when_bare_token_is_rewritten(self) -> None:
        registry = {"my-repo": "Y:\\Projects\\my-repo"}
        command = "es.exe my-repo\tconfig.py"
        rewritten = rewriter.rewrite_command(command, registry)
        assert rewritten == f'es.exe "Y:\\Projects\\my-repo"\tconfig.py'


class TestQuotedSingleWordRewrite:
    def test_double_quoted_single_word_registry_key_is_rewritten(self) -> None:
        registry = {"my-repo": "Y:\\Projects\\my-repo"}
        command = 'es.exe "my-repo" config.py'
        rewritten = rewriter.rewrite_command(command, registry)
        assert rewritten == f'es.exe "Y:\\Projects\\my-repo" config.py'

    def test_single_quoted_single_word_registry_key_is_rewritten(self) -> None:
        registry = {"my-repo": "Y:\\Projects\\my-repo"}
        command = "es.exe 'my-repo' config.py"
        rewritten = rewriter.rewrite_command(command, registry)
        assert rewritten == f'es.exe "Y:\\Projects\\my-repo" config.py'


class TestPlaceholderBoundaryEnforcement:
    def test_placeholder_inside_flag_argument_is_not_rewritten(self) -> None:
        registry = {"my-repo": "Y:\\Projects\\my-repo"}
        command = "es.exe --regex=^{my-repo}$"
        rewritten = rewriter.rewrite_command(command, registry)
        assert rewritten == command

    def test_placeholder_embedded_in_token_is_not_rewritten(self) -> None:
        registry = {"my-repo": "Y:\\Projects\\my-repo"}
        command = "es.exe foo{my-repo}bar"
        rewritten = rewriter.rewrite_command(command, registry)
        assert rewritten == command

    def test_standalone_placeholder_is_still_rewritten(self) -> None:
        registry = {"my-repo": "Y:\\Projects\\my-repo"}
        command = "es.exe {my-repo} config.py"
        rewritten = rewriter.rewrite_command(command, registry)
        assert rewritten == f'es.exe "Y:\\Projects\\my-repo" config.py'


class TestAbsolutePathDetection:
    def test_windows_drive_letter_path_detected_as_absolute(self) -> None:
        assert rewriter._token_is_absolute_path("C:\\Users\\x")

    def test_windows_drive_letter_path_with_forward_slashes_detected_as_absolute(
        self,
    ) -> None:
        assert rewriter._token_is_absolute_path("Y:/Projects/foo")

    def test_unc_path_detected_as_absolute(self) -> None:
        assert rewriter._token_is_absolute_path("\\\\server\\share\\path")

    def test_posix_absolute_path_detected_as_absolute(self) -> None:
        assert rewriter._token_is_absolute_path("/etc/hosts")

    def test_relative_path_not_detected_as_absolute(self) -> None:
        assert not rewriter._token_is_absolute_path("./foo")

    def test_bare_registry_token_not_detected_as_absolute(self) -> None:
        assert not rewriter._token_is_absolute_path("my-repo")
