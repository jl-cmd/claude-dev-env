"""Tests for open_questions_in_plans_blocker hook."""

import ast
import json
import os
import subprocess
import sys


HOOK_SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), "open_questions_in_plans_blocker.py"
)


def _read_hook_module_docstring() -> str:
    source_text = open(HOOK_SCRIPT_PATH, encoding="utf-8").read()
    module_docstring = ast.get_docstring(ast.parse(source_text))
    assert module_docstring is not None
    return module_docstring

_plan_with_open_questions = (
    "## Context\nA plan.\n\n## Open Questions\n- Which auth provider?\n"
)
_plan_without_open_questions = "## Context\nA plan.\n\n## Approach\nDo the thing.\n"


class _RunHook:
    def __call__(
        self, tool_name: str, tool_input: dict
    ) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        return subprocess.run(
            [sys.executable, HOOK_SCRIPT_PATH],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )


_run_hook = _RunHook()


def test_blocks_write_plan_with_open_questions_heading():
    result = _run_hook(
        "Write",
        {
            "file_path": os.path.expanduser("~/.claude/plans/add-feature.md"),
            "content": _plan_with_open_questions,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Open Questions" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_blocks_edit_plan_adding_open_questions():
    result = _run_hook(
        "Edit",
        {
            "file_path": os.path.expanduser("~/.claude/plans/refactor.md"),
            "old_string": "## Approach\nDo it.",
            "new_string": "## Approach\nDo it.\n\n## Open Questions\n- Which DB?",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_project_local_plans_directory():
    """Project-local `.claude/plans/` paths are also covered."""
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/my-plan.md",
            "content": _plan_with_open_questions,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_module_docstring_names_docs_plans_directory_family():
    """The docstring enumerates every directory family the detector fires on,
    including the repo-local `docs/plans/` family it now blocks."""
    module_docstring = _read_hook_module_docstring()

    assert "docs/plans/" in module_docstring


def test_blocks_repo_docs_plan_packet_directory():
    """Repo-local `docs/plans/<slug>/` packet docs are plan files too."""
    result = _run_hook(
        "Write",
        {
            "file_path": "docs/plans/add-login/spec/scope.md",
            "content": _plan_with_open_questions,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_windows_style_repo_docs_plan_packet_directory():
    result = _run_hook(
        "Write",
        {
            "file_path": "docs\\plans\\add-login\\spec\\scope.md",
            "content": _plan_with_open_questions,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_case_insensitive_heading():
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/x.md",
            "content": "# open questions\n- foo\n",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_bold_open_questions_heading():
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/x.md",
            "content": "**Open Questions**\n- foo\n",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_underscore_bold_open_questions_heading():
    """Canonical markdown underscore-bold `__Open Questions__` must block.

    Regression for the `\b` bug between word characters `s` and `_`.
    """
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/x.md",
            "content": "__Open Questions__\n- foo\n",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_open_questions_inside_fenced_code_block():
    """A heading quoted inside a fenced code block (e.g., rule docs showing what NOT to write) must NOT block."""
    content = (
        "## Context\n"
        "Example of what plans should NOT contain:\n\n"
        "```markdown\n"
        "## Open Questions\n"
        "- placeholder\n"
        "```\n\n"
        "## Approach\nDo the thing.\n"
    )
    result = _run_hook(
        "Write",
        {"file_path": ".claude/plans/x.md", "content": content},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_open_questions_inside_inline_code():
    """A heading-shaped string inside inline code (`## Open Questions`) must NOT block."""
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/x.md",
            "content": "Avoid sections like `## Open Questions` in plans.\n",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_open_questions_when_stray_backtick_precedes_real_heading():
    """A stray unmatched backtick on an earlier line must not cause the inline-code
    stripper to swallow the real `## Open Questions` heading further down. CommonMark
    inline-code spans cannot cross newlines, so the heading still has to block.

    Regression for `[^`]+` greedily matching across newlines and erasing the heading.
    """
    content_with_stray_backtick = (
        "Some text with stray backtick `here.\n"
        "\n"
        "## Open Questions\n"
        "- foo\n"
        "\n"
        "More `code` later.\n"
    )
    result = _run_hook(
        "Write",
        {"file_path": ".claude/plans/x.md", "content": content_with_stray_backtick},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Open Questions" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_blocks_multiedit_with_open_questions_in_any_edit():
    result = _run_hook(
        "MultiEdit",
        {
            "file_path": ".claude/plans/x.md",
            "edits": [
                {"old_string": "foo", "new_string": "bar"},
                {"old_string": "baz", "new_string": "## Open Questions\n- new"},
            ],
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_multiedit_without_open_questions():
    result = _run_hook(
        "MultiEdit",
        {
            "file_path": ".claude/plans/x.md",
            "edits": [
                {"old_string": "foo", "new_string": "bar"},
                {"old_string": "baz", "new_string": "qux"},
            ],
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_openquestions_concatenated_word():
    """`## OpenQuestions` (no separator) is a different word and must NOT block."""
    result = _run_hook(
        "Write",
        {"file_path": ".claude/plans/x.md", "content": "## OpenQuestions\n- foo\n"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_open_questionable_heading():
    """`## Open Questionable Plans` is a different word and must NOT block."""
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/x.md",
            "content": "## Open Questionable Plans\n- foo\n",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_plan_without_open_questions():
    result = _run_hook(
        "Write",
        {
            "file_path": os.path.expanduser("~/.claude/plans/clean.md"),
            "content": _plan_without_open_questions,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_open_questions_prose_outside_heading():
    """A plan that merely mentions 'open questions' in prose, not as a heading, is fine."""
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/x.md",
            "content": "## Context\nThere are no open questions left.\n",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_md_file_outside_plans_directory():
    """An `Open Questions` section in a non-plan .md file is not this hook's concern."""
    result = _run_hook(
        "Write",
        {
            "file_path": "docs/notes.md",
            "content": _plan_with_open_questions,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_non_markdown_file_in_plans_directory():
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/notes.txt",
            "content": _plan_with_open_questions,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_unknown_tool():
    result = _run_hook(
        "Grep",
        {"pattern": "foo", "path": "."},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_empty_file_path():
    result = _run_hook(
        "Write",
        {"file_path": "", "content": _plan_with_open_questions},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_json_decode_error():
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_non_dict_stdin():
    payload = json.dumps(["not", "a", "dict"])
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_denial_carries_system_message_and_context():
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude/plans/x.md",
            "content": _plan_with_open_questions,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["suppressOutput"] is True
    assert isinstance(output["systemMessage"], str) and output["systemMessage"]
    additional_context = output["hookSpecificOutput"]["additionalContext"]
    assert "AskUserQuestion" in additional_context
    assert "investigate" in additional_context.lower()


def test_edit_without_open_questions_in_new_string_passes():
    result = _run_hook(
        "Edit",
        {
            "file_path": ".claude/plans/x.md",
            "old_string": "## Open Questions\n- foo",
            "new_string": "## Resolved\n- foo is bar",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_windows_style_plans_path():
    result = _run_hook(
        "Write",
        {
            "file_path": ".claude\\plans\\my-plan.md",
            "content": _plan_with_open_questions,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def _make_plan_file_on_disk(tmp_path, content: str):
    plans_directory = tmp_path / ".claude" / "plans"
    plans_directory.mkdir(parents=True, exist_ok=True)
    plan_file = plans_directory / "existing-plan.md"
    plan_file.write_text(content, encoding="utf-8")
    return plan_file


def test_blocks_edit_when_existing_file_has_open_questions_outside_edit_window(tmp_path):
    """An Edit that touches unrelated text must STILL block when the file on disk
    already contains an `## Open Questions` heading that the edit does not remove."""
    existing_content = (
        "## Context\nA plan.\n\n## Open Questions\n- Which auth provider?\n\n"
        "## Approach\nDo the thing.\n"
    )
    plan_file = _make_plan_file_on_disk(tmp_path, existing_content)
    result = _run_hook(
        "Edit",
        {
            "file_path": str(plan_file),
            "old_string": "## Approach\nDo the thing.",
            "new_string": "## Approach\nDo the thing better.",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Open Questions" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_blocks_multiedit_when_existing_file_has_open_questions_untouched_by_any_edit(tmp_path):
    """A MultiEdit whose edits leave the existing `## Open Questions` section
    on disk untouched must still block."""
    existing_content = (
        "# Plan\n\n## Open Questions\n- Which DB?\n\n## Steps\n- step one\n- step two\n"
    )
    plan_file = _make_plan_file_on_disk(tmp_path, existing_content)
    result = _run_hook(
        "MultiEdit",
        {
            "file_path": str(plan_file),
            "edits": [
                {"old_string": "step one", "new_string": "first step"},
                {"old_string": "step two", "new_string": "second step"},
            ],
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_edit_that_removes_open_questions_from_existing_file(tmp_path):
    """An Edit that replaces the existing `## Open Questions` section with a
    resolved section must NOT block — the post-edit content has no heading."""
    existing_content = (
        "## Context\nA plan.\n\n## Open Questions\n- Which auth provider?\n\n"
        "## Approach\nDo the thing.\n"
    )
    plan_file = _make_plan_file_on_disk(tmp_path, existing_content)
    result = _run_hook(
        "Edit",
        {
            "file_path": str(plan_file),
            "old_string": "## Open Questions\n- Which auth provider?",
            "new_string": "## Auth\nUse OAuth via the existing provider.",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_multiedit_that_removes_open_questions_from_existing_file(tmp_path):
    """A MultiEdit whose edits collectively remove the existing `## Open Questions`
    section must NOT block — the post-edit content has no heading."""
    existing_content = (
        "# Plan\n\n## Open Questions\n- Which DB?\n\n## Steps\n- step one\n"
    )
    plan_file = _make_plan_file_on_disk(tmp_path, existing_content)
    result = _run_hook(
        "MultiEdit",
        {
            "file_path": str(plan_file),
            "edits": [
                {"old_string": "## Open Questions\n- Which DB?", "new_string": "## DB\nPostgres"},
                {"old_string": "step one", "new_string": "first step"},
            ],
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_edit_when_existing_file_at_tilde_path_has_open_questions(tmp_path, monkeypatch):
    """An Edit against a tilde-prefixed `~/.claude/plans/x.md` path must expand the
    tilde before reading the existing file, matching the expansion already done in
    `_is_inside_plans_directory`. Without the expansion, the disk read fails and the
    hook silently falls back to scanning `new_string` — reintroducing the bug for the
    canonical home-directory plans path.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    existing_content = (
        "## Context\nA plan.\n\n## Open Questions\n- Which auth provider?\n\n"
        "## Approach\nDo the thing.\n"
    )
    _make_plan_file_on_disk(tmp_path, existing_content)
    real_plan_file = tmp_path / ".claude" / "plans" / "existing-plan.md"
    tilde_plan_path = "~/.claude/plans/existing-plan.md"
    payload = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": tilde_plan_path,
                "old_string": "## Approach\nDo the thing.",
                "new_string": "## Approach\nDo the thing better.",
            },
        }
    )
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
    )
    assert result.returncode == 0
    assert real_plan_file.exists()
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Open Questions" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_blocks_edit_when_file_missing_but_new_string_has_open_questions(tmp_path):
    """When the target file does not exist on disk, the hook must fall back to
    scanning `new_string` (preserves existing behavior for first-write edits)."""
    plans_directory = tmp_path / ".claude" / "plans"
    plans_directory.mkdir(parents=True, exist_ok=True)
    missing_plan_file = plans_directory / "not-yet-saved.md"
    result = _run_hook(
        "Edit",
        {
            "file_path": str(missing_plan_file),
            "old_string": "## Approach\nDo it.",
            "new_string": "## Approach\nDo it.\n\n## Open Questions\n- foo",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_edit_with_empty_old_string_on_clean_existing_file_does_not_falsely_block(tmp_path):
    """An Edit with empty `old_string` against an existing clean plan must not
    synthesize a phantom prepended `new_string`. Without the guard,
    `existing_text.replace('', new_string, 1)` prepends `new_string` to the
    existing file content, fabricating an `## Open Questions` heading that the
    real Edit tool would never actually produce — leading to a false deny.
    """
    clean_existing_content = "## Context\nA plan.\n\n## Approach\nDo the thing.\n"
    plan_file = _make_plan_file_on_disk(tmp_path, clean_existing_content)
    result = _run_hook(
        "Edit",
        {
            "file_path": str(plan_file),
            "old_string": "",
            "new_string": "## Open Questions\n- placeholder",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_edit_with_non_string_old_string_on_existing_file_does_not_falsely_block(tmp_path):
    """An Edit whose `old_string` is not a string (defensive against unexpected
    payloads) must be treated as 'cannot reconstruct post-edit content' and
    fall back to the unmodified existing content.
    """
    clean_existing_content = "## Context\nA plan.\n\n## Approach\nDo the thing.\n"
    plan_file = _make_plan_file_on_disk(tmp_path, clean_existing_content)
    result = _run_hook(
        "Edit",
        {
            "file_path": str(plan_file),
            "old_string": None,
            "new_string": "## Open Questions\n- placeholder",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_edit_with_empty_old_string_still_blocks_when_existing_file_has_open_questions(tmp_path):
    """When `old_string` is empty and the existing file already contains an
    `## Open Questions` heading, the unmodified existing content still triggers
    the block — the guard returns existing content as-is, not a fabrication.
    """
    existing_content = (
        "## Context\nA plan.\n\n## Open Questions\n- Which auth provider?\n\n"
        "## Approach\nDo the thing.\n"
    )
    plan_file = _make_plan_file_on_disk(tmp_path, existing_content)
    result = _run_hook(
        "Edit",
        {
            "file_path": str(plan_file),
            "old_string": "",
            "new_string": "## Approach\nDo the thing better.",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_edit_with_empty_old_string_on_missing_file_still_scans_new_string(tmp_path):
    """When the file is missing and `old_string` is empty, preserve the existing
    missing-file fallback: scan `new_string` for an Open Questions heading.
    """
    plans_directory = tmp_path / ".claude" / "plans"
    plans_directory.mkdir(parents=True, exist_ok=True)
    missing_plan_file = plans_directory / "not-yet-saved.md"
    result = _run_hook(
        "Edit",
        {
            "file_path": str(missing_plan_file),
            "old_string": "",
            "new_string": "## Approach\nDo it.\n\n## Open Questions\n- foo",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_multiedit_skips_edit_with_empty_old_string_on_existing_file(tmp_path):
    """A MultiEdit whose first entry has an empty `old_string` (and a dangerous
    `new_string` containing an Open Questions heading) must skip that entry —
    not prepend the new_string into the existing content via `replace('', X, 1)`.
    """
    clean_existing_content = "## Context\nA plan.\n\nstep one\n"
    plan_file = _make_plan_file_on_disk(tmp_path, clean_existing_content)
    result = _run_hook(
        "MultiEdit",
        {
            "file_path": str(plan_file),
            "edits": [
                {"old_string": "", "new_string": "## Open Questions\n- placeholder"},
                {"old_string": "step one", "new_string": "first step"},
            ],
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_multiedit_with_only_invalid_edits_on_existing_file_returns_existing_content(tmp_path):
    """A MultiEdit whose every entry has an empty `old_string` must leave the
    existing file content unchanged for the scan — no synthetic prepends.
    """
    clean_existing_content = "## Context\nA plan.\n\n## Approach\nDo the thing.\n"
    plan_file = _make_plan_file_on_disk(tmp_path, clean_existing_content)
    result = _run_hook(
        "MultiEdit",
        {
            "file_path": str(plan_file),
            "edits": [
                {"old_string": "", "new_string": "## Open Questions\n- one"},
                {"old_string": "", "new_string": "## Open Questions\n- two"},
            ],
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_multiedit_with_only_invalid_edits_on_missing_file_still_scans_new_strings(tmp_path):
    """When the file is missing and every entry has an empty `old_string`,
    preserve the missing-file fallback: scan the joined `new_string` values.
    """
    plans_directory = tmp_path / ".claude" / "plans"
    plans_directory.mkdir(parents=True, exist_ok=True)
    missing_plan_file = plans_directory / "not-yet-saved.md"
    result = _run_hook(
        "MultiEdit",
        {
            "file_path": str(missing_plan_file),
            "edits": [
                {"old_string": "", "new_string": "## Open Questions\n- placeholder"},
            ],
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_multiedit_missing_file_mixed_valid_invalid_includes_invalid_new_string(tmp_path):
    """When the file is missing and edits mix valid + invalid `old_string` entries,
    the missing-file fallback must scan EVERY edit's `new_string`. Filtering by
    `_is_valid_old_string` is only correct for the existing-file branch (where
    `replace('', X, 1)` would fabricate a prepend). For the missing-file branch
    we start from empty and concatenate candidate content — the safe behavior is
    over-blocking: scan all new_strings.
    """
    plans_directory = tmp_path / ".claude" / "plans"
    plans_directory.mkdir(parents=True, exist_ok=True)
    missing_plan_file = plans_directory / "not-yet-saved.md"
    result = _run_hook(
        "MultiEdit",
        {
            "file_path": str(missing_plan_file),
            "edits": [
                {"old_string": "", "new_string": "## Open Questions\n- foo\n"},
                {"old_string": "preamble", "new_string": "epilogue"},
            ],
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Open Questions" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_edit_with_file_path_pointing_at_directory_does_not_crash(tmp_path):
    """When `file_path` points at a directory (not a file), `_read_plan_file_text_and_missing_flag`
    raises `IsADirectoryError` on `Path.read_text`. The hook must catch it like the
    other narrow read failures and fall back to scanning the edit's `new_string`."""
    plans_directory = tmp_path / ".claude" / "plans"
    plans_directory.mkdir(parents=True, exist_ok=True)
    directory_as_file_path = plans_directory / "looks-like-file.md"
    directory_as_file_path.mkdir()
    result = _run_hook(
        "Edit",
        {
            "file_path": str(directory_as_file_path),
            "old_string": "preamble",
            "new_string": "## Open Questions\n- placeholder",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Open Questions" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_blocks_edit_when_existing_file_permission_denied_does_not_silently_pass(tmp_path):
    """When an Edit targets an existing plan file but the disk read raises
    `PermissionError`, the hook cannot prove the on-disk content is clean. It must
    conservatively block rather than silently falling back to the missing-file
    new_string scan — the file exists with an unknown payload that could still
    contain `## Open Questions`.

    Simulated via a sidecar Python stub that monkeypatches `Path.read_text` to
    raise `PermissionError`, then runs the hook in-process via the same JSON
    contract as the subprocess `_run_hook` helper.
    """
    plans_directory = tmp_path / ".claude" / "plans"
    plans_directory.mkdir(parents=True, exist_ok=True)
    plan_file = plans_directory / "unreadable.md"
    plan_file.write_text("placeholder", encoding="utf-8")
    stub_script = tmp_path / "run_with_permission_error.py"
    stub_script.write_text(
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        f"sys.path.insert(0, {repr(os.path.dirname(HOOK_SCRIPT_PATH))})\n"
        "original_read_text = Path.read_text\n"
        "def _raise_permission_error(self, *args, **kwargs):\n"
        "    raise PermissionError('simulated locked file')\n"
        "Path.read_text = _raise_permission_error\n"
        "\n"
        "import open_questions_in_plans_blocker as hook_module\n"
        "hook_module.main()\n",
        encoding="utf-8",
    )
    payload = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(plan_file),
                "old_string": "preamble",
                "new_string": "## Approach\nDo the thing better.",
            },
        }
    )
    result = subprocess.run(
        [sys.executable, str(stub_script)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Open Questions" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_blocks_edit_when_existing_file_unicode_decode_error_does_not_silently_pass(tmp_path):
    """When an Edit targets an existing plan file whose bytes are not valid UTF-8,
    `Path.read_text(encoding='utf-8')` raises `UnicodeDecodeError`. The hook cannot
    reason about binary content, so it must conservatively block rather than
    silently falling back to the missing-file new_string scan.
    """
    plans_directory = tmp_path / ".claude" / "plans"
    plans_directory.mkdir(parents=True, exist_ok=True)
    plan_file = plans_directory / "binary-content.md"
    plan_file.write_bytes(b"\xff\xfe\xfd raw bytes that are not valid utf-8 \xff")
    result = _run_hook(
        "Edit",
        {
            "file_path": str(plan_file),
            "old_string": "preamble",
            "new_string": "## Approach\nDo the thing better.",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Open Questions" in output["hookSpecificOutput"]["permissionDecisionReason"]
