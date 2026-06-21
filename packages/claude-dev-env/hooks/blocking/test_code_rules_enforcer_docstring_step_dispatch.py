"""Tests for check_docstring_step_enumeration_dispatch_coverage — O4 step drift.

A function whose docstring enumerates a linear step sequence matching the body's
top-level calls, while the body also routes to a corrective action inside an
``if``/``elif`` branch the prose never names, hides that conditional path from the
reader. This is the deterministic slice of Category O4 (step-ordering narrative).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_enforcer_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_rules_enforcer = _load_enforcer_module()


def check_docstring_step_enumeration_dispatch_coverage(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_step_enumeration_dispatch_coverage(
        content, file_path
    )


def validate_content(content: str, file_path: str, old_content: str) -> list[str]:
    return code_rules_enforcer.validate_content(content, file_path, old_content)


PRODUCTION_FILE_PATH = "/project/src/theme_update_listing_edits.py"
TEST_FILE_PATH = "/project/src/test_theme_update_listing_edits.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def _drifted_update_binary_function() -> str:
    return (
        "async def _open_update_and_upload_binary(\n"
        "    self, content_id: str, apk_path: Path\n"
        ") -> ClickedUpdateButton:\n"
        '    """Open the theme\'s update form, upload the new binary, and exclude'
        " Fold devices.\n"
        "\n"
        "    Navigates to the content list, searches for the content ID, clicks\n"
        "    whichever update-action button is present, navigates to the Binary tab,\n"
        "    and uploads the APK.\n"
        '    """\n'
        "    if not await self.navigate_to_content_list_start():\n"
        "        return ClickedUpdateButton.NONE\n"
        "    if not await self.search_for_content_id(content_id):\n"
        "        return ClickedUpdateButton.NONE\n"
        "    clicked = await self.click_update_button()\n"
        "    if not await self.navigate_to_binary_tab():\n"
        "        return ClickedUpdateButton.NONE\n"
        "    decision = await classify_binary_state(self.automation.cdp, self.oneui_number)\n"
        "    if decision.path is BinaryUpdatePath.PATH_B_CANCEL_UPDATE:\n"
        "        if not await cancel_and_reinitiate_update(self, content_id):\n"
        "            return ClickedUpdateButton.NONE\n"
        "    elif decision.path is BinaryUpdatePath.PATH_A_REPLACE_BINARY:\n"
        "        if not await replace_target_binary_row(self.automation, apk_path):\n"
        "            return ClickedUpdateButton.NONE\n"
        "    if not await upload_binary_to_open_theme(self.automation, [apk_path]):\n"
        "        return ClickedUpdateButton.NONE\n"
        "    return clicked\n"
    )


def _enumerated_update_binary_function() -> str:
    return (
        "async def _open_update_and_upload_binary(\n"
        "    self, content_id: str, apk_path: Path\n"
        ") -> ClickedUpdateButton:\n"
        '    """Open the theme\'s update form, upload the new binary, and exclude'
        " Fold devices.\n"
        "\n"
        "    Navigates to the content list, searches for the content ID, clicks\n"
        "    whichever update-action button is present, navigates to the Binary tab,\n"
        "    classifies the existing binary rows and, when needed, cancels and\n"
        "    reinitiates the update or replaces the target binary row, then uploads\n"
        "    the APK.\n"
        '    """\n'
        "    if not await self.navigate_to_content_list_start():\n"
        "        return ClickedUpdateButton.NONE\n"
        "    if not await self.search_for_content_id(content_id):\n"
        "        return ClickedUpdateButton.NONE\n"
        "    clicked = await self.click_update_button()\n"
        "    if not await self.navigate_to_binary_tab():\n"
        "        return ClickedUpdateButton.NONE\n"
        "    decision = await classify_binary_state(self.automation.cdp, self.oneui_number)\n"
        "    if decision.path is BinaryUpdatePath.PATH_B_CANCEL_UPDATE:\n"
        "        if not await cancel_and_reinitiate_update(self, content_id):\n"
        "            return ClickedUpdateButton.NONE\n"
        "    elif decision.path is BinaryUpdatePath.PATH_A_REPLACE_BINARY:\n"
        "        if not await replace_target_binary_row(self.automation, apk_path):\n"
        "            return ClickedUpdateButton.NONE\n"
        "    if not await upload_binary_to_open_theme(self.automation, [apk_path]):\n"
        "        return ClickedUpdateButton.NONE\n"
        "    return clicked\n"
    )


def test_should_flag_branch_only_dispatch_call_the_prose_omits() -> None:
    issues = check_docstring_step_enumeration_dispatch_coverage(
        _drifted_update_binary_function(), PRODUCTION_FILE_PATH
    )
    assert any("cancel_and_reinitiate_update" in each for each in issues), (
        f"The Path B cancel-and-reinitiate dispatch must be flagged, got: {issues!r}"
    )
    assert any("replace_target_binary_row" in each for each in issues), (
        f"The Path A replace-target-row dispatch must be flagged, got: {issues!r}"
    )


def test_should_report_category_o4_in_the_message() -> None:
    issues = check_docstring_step_enumeration_dispatch_coverage(
        _drifted_update_binary_function(), PRODUCTION_FILE_PATH
    )
    assert any("O4" in each for each in issues), (
        f"Expected the Category O4 label in the message, got: {issues!r}"
    )


def test_should_not_flag_when_dispatch_steps_are_enumerated() -> None:
    issues = check_docstring_step_enumeration_dispatch_coverage(
        _enumerated_update_binary_function(), PRODUCTION_FILE_PATH
    )
    assert issues == [], (
        f"A docstring that names the corrective-path steps must not be flagged, got: {issues!r}"
    )


def test_should_not_flag_when_fewer_than_two_linear_steps_are_named() -> None:
    source = (
        "def run(target: object) -> None:\n"
        '    """Compose the report from the target."""\n'
        "    compose_report(target)\n"
        "    flush_pending_writes(target)\n"
        "    if target.is_stale:\n"
        "        purge_expired_cache_entries(target)\n"
    )
    issues = check_docstring_step_enumeration_dispatch_coverage(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        "Only one linear step (compose_report) is named in the prose, below the bind "
        f"threshold, so no dispatch is flagged, got: {issues!r}"
    )


def test_should_not_flag_guarded_callee_that_is_also_a_linear_step() -> None:
    source = (
        "def run(target: object) -> None:\n"
        '    """Validate target, then dispatch event to queue."""\n'
        "    if not validate_target(target):\n"
        "        return\n"
        "    if not dispatch_event_to_queue(target):\n"
        "        return\n"
        "    if target.is_retry:\n"
        "        if not dispatch_event_to_queue(target):\n"
        "            return\n"
    )
    issues = check_docstring_step_enumeration_dispatch_coverage(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        "A guarded callee the body also guards as a linear step is covered by the "
        f"enumeration and must not be flagged, got: {issues!r}"
    )


def test_should_not_flag_plain_branch_logging_call() -> None:
    source = (
        "def run(target: object) -> None:\n"
        '    """Validate target, then dispatch event to queue."""\n'
        "    if not validate_target(target):\n"
        "        return\n"
        "    if not dispatch_event_to_queue(target):\n"
        "        return\n"
        "    if target.is_error:\n"
        "        capture_error_screenshot(target)\n"
        "        log_error_details(target)\n"
    )
    issues = check_docstring_step_enumeration_dispatch_coverage(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        "Plain (unguarded) branch logging and screenshot calls are not control-flow "
        f"dispatch steps and must not be flagged, got: {issues!r}"
    )


def test_should_not_flag_single_token_guarded_branch_callee() -> None:
    source = (
        "def run(target: object) -> None:\n"
        '    """Open the form, then submit the form."""\n'
        "    if not open_the_form(target):\n"
        "        return\n"
        "    if not submit_the_form(target):\n"
        "        return\n"
        "    if target.is_dirty:\n"
        "        if not rollback(target):\n"
        "            return\n"
    )
    issues = check_docstring_step_enumeration_dispatch_coverage(source, PRODUCTION_FILE_PATH)
    assert issues == [], (
        "A single-token guarded branch callee is below the token threshold and must "
        f"not be flagged, got: {issues!r}"
    )


def test_should_flag_guarded_branch_dispatch_step_the_prose_omits() -> None:
    source = (
        "def run(target: object) -> None:\n"
        '    """Validate target, then dispatch event to queue."""\n'
        "    if not validate_target(target):\n"
        "        return\n"
        "    if not dispatch_event_to_queue(target):\n"
        "        return\n"
        "    if target.is_retry:\n"
        "        if not reissue_pending_credential(target):\n"
        "            return\n"
    )
    issues = check_docstring_step_enumeration_dispatch_coverage(source, PRODUCTION_FILE_PATH)
    assert any("reissue_pending_credential" in each for each in issues), (
        "A guarded multi-token branch dispatch step the prose omits must be flagged, "
        f"got: {issues!r}"
    )


def test_should_skip_test_file() -> None:
    issues = check_docstring_step_enumeration_dispatch_coverage(
        _drifted_update_binary_function(), TEST_FILE_PATH
    )
    assert issues == [], f"Test files exempt, got: {issues!r}"


def test_should_skip_hook_infrastructure() -> None:
    issues = check_docstring_step_enumeration_dispatch_coverage(
        _drifted_update_binary_function(), HOOK_INFRASTRUCTURE_PATH
    )
    assert issues == [], f"Hook infrastructure exempt, got: {issues!r}"


def test_should_handle_syntax_error_gracefully() -> None:
    issues = check_docstring_step_enumeration_dispatch_coverage(
        "def fetch(\n", PRODUCTION_FILE_PATH
    )
    assert issues == [], f"Syntax error must yield no issues, got: {issues!r}"


def test_validate_content_surfaces_step_dispatch_drift() -> None:
    issues = validate_content(
        _drifted_update_binary_function(), PRODUCTION_FILE_PATH, old_content=""
    )
    matching_issues = [
        each for each in issues if "cancel_and_reinitiate_update" in each and "O4" in each
    ]
    assert matching_issues, (
        f"Expected validate_content to surface the O4 step-dispatch drift, got: {issues!r}"
    )
