"""Tests for same-file inline duplicate function-body detection.

PR #470 (JonEcho/python-automation) added ``_wait_for_content_image_to_render``,
a top-level async helper whose body is byte-for-structure identical to a
content-image-wait block already inlined inside ``_wait_for_page_after_account_switch``
in the same module. The cross-file duplicate-body check never compares two
functions in the same file, and it only matches a whole function against a whole
function — so the inlined-block copy slipped past it. This check closes that gap:
a top-level function whose body appears verbatim as a contiguous statement block
inside another function in the same module is flagged so the author calls the
helper from that function instead of repeating the block.

The tests build real source strings and run the check directly, exercising the
in-process AST scan the production enforcer runs.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

_HOOK_DIRECTORY = pathlib.Path(__file__).parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))

_hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIRECTORY / "code_rules_enforcer.py",
)
assert _hook_spec is not None
assert _hook_spec.loader is not None
_hook_module = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(_hook_module)
check_same_file_inline_duplicate_body = _hook_module.check_same_file_inline_duplicate_body


PR_470_SHAPE_SOURCE = (
    "import asyncio\n"
    "\n"
    "\n"
    "async def _wait_for_content_image_to_render(automation: object) -> None:\n"
    '    """Wait for the content image to render before detection."""\n'
    "    assert automation.detector is not None\n"
    "    try:\n"
    "        await automation.detector.wait_for_element(\n"
    "            account_detector_config.content_image_selector,\n"
    "            timeout=page_navigation_delays.account_switch_page_load,\n"
    "        )\n"
    "    except (TimeoutError, RuntimeError) as content_error:\n"
    "        logger.warning('content images did not appear: %s', content_error)\n"
    "\n"
    "\n"
    "async def _wait_for_page_after_account_switch(automation: object) -> None:\n"
    "    await asyncio.to_thread(automation.cdp._navigate_to_url, url)\n"
    "    await asyncio.to_thread(automation.cdp._wait_for_page_load)\n"
    "    assert automation.detector is not None\n"
    "    try:\n"
    "        await automation.detector.wait_for_element(\n"
    "            account_detector_config.content_image_selector,\n"
    "            timeout=page_navigation_delays.account_switch_page_load,\n"
    "        )\n"
    "    except (TimeoutError, RuntimeError) as content_error:\n"
    "        logger.warning('content images did not appear: %s', content_error)\n"
)


def test_should_flag_helper_whose_body_is_inlined_in_another_function() -> None:
    issues = check_same_file_inline_duplicate_body(PR_470_SHAPE_SOURCE, "account_switcher.py")
    assert any("_wait_for_content_image_to_render" in each_issue for each_issue in issues), (
        f"The helper duplicating an inline block must be flagged, got: {issues}"
    )
    assert any("_wait_for_page_after_account_switch" in each_issue for each_issue in issues), (
        f"The enclosing function carrying the inline copy must be named, got: {issues}"
    )


def test_should_not_flag_when_no_function_inlines_the_helper_body() -> None:
    source = (
        "async def _wait_for_content_image_to_render(automation: object) -> None:\n"
        "    assert automation.detector is not None\n"
        "    await automation.detector.wait_for_element(selector)\n"
        "    logger.info('rendered')\n"
        "\n"
        "\n"
        "async def _do_other_work(automation: object) -> None:\n"
        "    await automation.cdp.reload()\n"
        "    logger.info('reloaded')\n"
        "    return None\n"
    )
    issues = check_same_file_inline_duplicate_body(source, "module.py")
    assert issues == [], f"No function inlines the helper body, so nothing must flag, got: {issues}"


def test_should_not_flag_helper_whose_body_is_too_trivial() -> None:
    source = (
        "def small_helper() -> int:\n"
        "    return 7\n"
        "\n"
        "\n"
        "def caller() -> int:\n"
        "    other = 1\n"
        "    again = 2\n"
        "    return 7\n"
    )
    issues = check_same_file_inline_duplicate_body(source, "module.py")
    assert issues == [], (
        f"A body under the minimum statement count is too common to flag, got: {issues}"
    )


def test_should_not_flag_flat_helper_with_no_compound_statement() -> None:
    source = (
        "def assign_pair(target: object) -> None:\n"
        "    target.left = 1\n"
        "    target.right = 2\n"
        "\n"
        "\n"
        "def run(target: object) -> None:\n"
        "    target.begin()\n"
        "    target.left = 1\n"
        "    target.right = 2\n"
        "    target.finish()\n"
    )
    issues = check_same_file_inline_duplicate_body(source, "module.py")
    assert issues == [], (
        "A two-statement helper with no compound statement is too common to be a "
        f"meaningful duplicate and must not flag, got: {issues}"
    )


def test_should_flag_two_statement_helper_with_a_compound_statement() -> None:
    source = (
        "async def _wait_for_render(automation: object) -> None:\n"
        "    assert automation.detector is not None\n"
        "    try:\n"
        "        await automation.detector.wait_for_element(selector)\n"
        "    except (TimeoutError, RuntimeError) as render_error:\n"
        "        logger.warning('did not render: %s', render_error)\n"
        "\n"
        "\n"
        "async def _navigate_then_wait(automation: object) -> None:\n"
        "    await automation.cdp.navigate(url)\n"
        "    assert automation.detector is not None\n"
        "    try:\n"
        "        await automation.detector.wait_for_element(selector)\n"
        "    except (TimeoutError, RuntimeError) as render_error:\n"
        "        logger.warning('did not render: %s', render_error)\n"
    )
    issues = check_same_file_inline_duplicate_body(source, "module.py")
    assert any("_wait_for_render" in each_issue for each_issue in issues), (
        "A two-statement helper carrying a try/except whose body is inlined "
        f"elsewhere is a real duplicate and must flag, got: {issues}"
    )


def test_should_flag_helper_inlined_inside_an_enclosing_finally_block() -> None:
    source = (
        "def _drain_queue(queue: object) -> None:\n"
        "    for each_message in queue.pending:\n"
        "        queue.deliver(each_message)\n"
        "        queue.acknowledge(each_message)\n"
        "\n"
        "\n"
        "def shutdown(queue: object) -> None:\n"
        "    try:\n"
        "        queue.stop_accepting()\n"
        "    finally:\n"
        "        for each_message in queue.pending:\n"
        "            queue.deliver(each_message)\n"
        "            queue.acknowledge(each_message)\n"
    )
    issues = check_same_file_inline_duplicate_body(source, "module.py")
    assert any("_drain_queue" in each_issue for each_issue in issues), (
        "A helper whose loop body is inlined verbatim in an enclosing function's "
        f"finally block is a real duplicate and must flag, got: {issues}"
    )


def test_should_flag_helper_inlined_inside_an_enclosing_except_handler() -> None:
    source = (
        "def _drain_queue(queue: object) -> None:\n"
        "    for each_message in queue.pending:\n"
        "        queue.deliver(each_message)\n"
        "        queue.acknowledge(each_message)\n"
        "\n"
        "\n"
        "def run(queue: object) -> None:\n"
        "    try:\n"
        "        queue.start()\n"
        "    except RuntimeError:\n"
        "        for each_message in queue.pending:\n"
        "            queue.deliver(each_message)\n"
        "            queue.acknowledge(each_message)\n"
    )
    issues = check_same_file_inline_duplicate_body(source, "module.py")
    assert any("_drain_queue" in each_issue for each_issue in issues), (
        "A helper whose loop body is inlined verbatim in an enclosing function's "
        f"except handler is a real duplicate and must flag, got: {issues}"
    )


def test_should_flag_helper_inlined_inside_a_single_top_level_if_guard() -> None:
    source = (
        "def _send_pending(client: object) -> None:\n"
        "    queued = client.collect()\n"
        "    try:\n"
        "        client.transmit(queued)\n"
        "    except (TimeoutError, ConnectionError) as send_error:\n"
        "        logger.warning('send failed: %s', send_error)\n"
        "\n"
        "\n"
        "def flush(client: object) -> None:\n"
        "    if client.enabled:\n"
        "        queued = client.collect()\n"
        "        try:\n"
        "            client.transmit(queued)\n"
        "        except (TimeoutError, ConnectionError) as send_error:\n"
        "            logger.warning('send failed: %s', send_error)\n"
    )
    issues = check_same_file_inline_duplicate_body(source, "module.py")
    assert any("_send_pending" in each_issue for each_issue in issues), (
        "A helper whose two-statement window is inlined inside a single top-level "
        f"if guard is a real duplicate and must flag, got: {issues}"
    )


def test_should_not_flag_structural_twin_peers_wrapped_in_a_compound() -> None:
    source = (
        "def _deliver_left(queue: object) -> None:\n"
        "    for each_message in queue.left:\n"
        "        queue.deliver(each_message)\n"
        "        queue.acknowledge(each_message)\n"
        "\n"
        "\n"
        "def _deliver_right(queue: object) -> None:\n"
        "    for each_message in queue.left:\n"
        "        queue.deliver(each_message)\n"
        "        queue.acknowledge(each_message)\n"
    )
    issues = check_same_file_inline_duplicate_body(source, "module.py")
    assert issues == [], (
        "Two peer helpers that share the same statement shape are structural twins "
        f"left to the cross-file check, so neither must flag, got: {issues}"
    )


def test_should_match_through_a_docstring_only_difference() -> None:
    source = (
        "def render_block(target: object) -> None:\n"
        '    """Render the block."""\n'
        "    target.prepare()\n"
        "    for each_step in target.steps:\n"
        "        each_step.run()\n"
        "    target.finalize()\n"
        "\n"
        "\n"
        "def orchestrate(target: object) -> None:\n"
        "    target.begin()\n"
        "    target.prepare()\n"
        "    for each_step in target.steps:\n"
        "        each_step.run()\n"
        "    target.finalize()\n"
    )
    issues = check_same_file_inline_duplicate_body(source, "module.py")
    assert any("render_block" in each_issue for each_issue in issues), (
        f"A docstring-only difference must not hide the inline duplicate, got: {issues}"
    )


def test_should_skip_test_file_being_written() -> None:
    issues = check_same_file_inline_duplicate_body(PR_470_SHAPE_SOURCE, "test_account_switcher.py")
    assert issues == [], f"Test files are exempt on the writing side, got: {issues}"


def test_should_return_empty_on_syntax_error() -> None:
    issues = check_same_file_inline_duplicate_body("def broken(\n", "module.py")
    assert issues == [], f"Unparseable content must return empty, got: {issues}"


def test_should_not_flag_when_changed_lines_miss_both_functions() -> None:
    leading = (
        "def unrelated(left: int, right: int) -> int:\n"
        "    summed = left + right\n"
        "    tripled = summed * 3\n"
        "    return tripled\n"
        "\n"
        "\n"
    )
    post_edit_content = leading + PR_470_SHAPE_SOURCE
    changed_lines_outside = {1, 2, 3, 4}
    issues = check_same_file_inline_duplicate_body(
        post_edit_content,
        "account_switcher.py",
        all_changed_lines=changed_lines_outside,
    )
    assert issues == [], (
        f"An edit that touches neither the helper nor its inline copy must not block, got: {issues}"
    )


def test_should_flag_when_changed_lines_touch_the_helper() -> None:
    helper_definition_line = (
        PR_470_SHAPE_SOURCE.splitlines().index(
            "async def _wait_for_content_image_to_render(automation: object) -> None:"
        )
        + 1
    )
    issues = check_same_file_inline_duplicate_body(
        PR_470_SHAPE_SOURCE,
        "account_switcher.py",
        all_changed_lines={helper_definition_line + 2},
    )
    assert any("_wait_for_content_image_to_render" in each_issue for each_issue in issues), (
        f"An edit touching the new helper must flag, got: {issues}"
    )


def test_should_return_every_violation_when_scope_deferred_to_caller() -> None:
    leading = (
        "def unrelated(left: int, right: int) -> int:\n"
        "    summed = left + right\n"
        "    tripled = summed * 3\n"
        "    return tripled\n"
        "\n"
        "\n"
    )
    post_edit_content = leading + PR_470_SHAPE_SOURCE
    issues = check_same_file_inline_duplicate_body(
        post_edit_content,
        "account_switcher.py",
        all_changed_lines={1, 2, 3, 4},
        defer_scope_to_caller=True,
    )
    assert any("_wait_for_content_image_to_render" in each_issue for each_issue in issues), (
        "The commit gate scopes by added line, so the check must return every "
        f"violation when scope is deferred, got: {issues}"
    )


NON_ADJACENT_DUPLICATE_SOURCE = (
    "import asyncio\n"
    "\n"
    "\n"
    "async def _wait_for_content_image_to_render(automation: object) -> None:\n"
    '    """Wait for the content image to render before detection."""\n'
    "    assert automation.detector is not None\n"
    "    try:\n"
    "        await automation.detector.wait_for_element(\n"
    "            account_detector_config.content_image_selector,\n"
    "            timeout=page_navigation_delays.account_switch_page_load,\n"
    "        )\n"
    "    except (TimeoutError, RuntimeError) as content_error:\n"
    "        logger.warning('content images did not appear: %s', content_error)\n"
    "\n"
    "\n"
    "def _unrelated_intervening(left: int, right: int) -> int:\n"
    "    summed = left + right\n"
    "    tripled = summed * 3\n"
    "    return tripled\n"
    "\n"
    "\n"
    "async def _wait_for_page_after_account_switch(automation: object) -> None:\n"
    "    await asyncio.to_thread(automation.cdp._navigate_to_url, url)\n"
    "    await asyncio.to_thread(automation.cdp._wait_for_page_load)\n"
    "    assert automation.detector is not None\n"
    "    try:\n"
    "        await automation.detector.wait_for_element(\n"
    "            account_detector_config.content_image_selector,\n"
    "            timeout=page_navigation_delays.account_switch_page_load,\n"
    "        )\n"
    "    except (TimeoutError, RuntimeError) as content_error:\n"
    "        logger.warning('content images did not appear: %s', content_error)\n"
)


def _line_number_of(source: str, needle: str) -> int:
    return source.splitlines().index(needle) + 1


def test_should_not_flag_when_edit_touches_only_a_line_between_the_two_functions() -> None:
    intervening_body_line = (
        _line_number_of(NON_ADJACENT_DUPLICATE_SOURCE, "    summed = left + right")
    )
    issues = check_same_file_inline_duplicate_body(
        NON_ADJACENT_DUPLICATE_SOURCE,
        "account_switcher.py",
        all_changed_lines={intervening_body_line},
    )
    assert issues == [], (
        "An edit confined to an unrelated function that sits strictly between the "
        "helper and its inline copy must not block, even though that line falls in "
        f"the gap between the two duplicate functions, got: {issues}"
    )


def test_should_flag_when_edit_touches_the_helper_in_the_non_adjacent_layout() -> None:
    helper_body_line = (
        _line_number_of(
            NON_ADJACENT_DUPLICATE_SOURCE,
            "    assert automation.detector is not None",
        )
    )
    issues = check_same_file_inline_duplicate_body(
        NON_ADJACENT_DUPLICATE_SOURCE,
        "account_switcher.py",
        all_changed_lines={helper_body_line},
    )
    assert any("_wait_for_content_image_to_render" in each_issue for each_issue in issues), (
        "An edit touching the helper must still flag in the non-adjacent layout, "
        f"got: {issues}"
    )


def test_should_flag_when_edit_touches_the_enclosing_in_the_non_adjacent_layout() -> None:
    enclosing_first_body_line = (
        _line_number_of(
            NON_ADJACENT_DUPLICATE_SOURCE,
            "    await asyncio.to_thread(automation.cdp._navigate_to_url, url)",
        )
    )
    issues = check_same_file_inline_duplicate_body(
        NON_ADJACENT_DUPLICATE_SOURCE,
        "account_switcher.py",
        all_changed_lines={enclosing_first_body_line},
    )
    assert any("_wait_for_page_after_account_switch" in each_issue for each_issue in issues), (
        "An edit touching the enclosing function must still flag in the "
        f"non-adjacent layout, got: {issues}"
    )


def test_should_carry_both_helper_and_enclosing_spans_for_the_commit_gate_scoper() -> None:
    helper_definition_line = _line_number_of(
        PR_470_SHAPE_SOURCE,
        "async def _wait_for_content_image_to_render(automation: object) -> None:",
    )
    enclosing_definition_line = _line_number_of(
        PR_470_SHAPE_SOURCE,
        "async def _wait_for_page_after_account_switch(automation: object) -> None:",
    )
    helper_span_length = 10
    enclosing_span_length = 11
    issues = check_same_file_inline_duplicate_body(
        PR_470_SHAPE_SOURCE,
        "account_switcher.py",
        all_changed_lines=None,
        defer_scope_to_caller=True,
    )
    matching_issues = [
        each_issue
        for each_issue in issues
        if "_wait_for_content_image_to_render" in each_issue
    ]
    assert matching_issues, f"expected an inline-duplicate issue, got: {issues}"
    expected_fragment = (
        f"(inline duplicate body spans: helper at line {helper_definition_line} "
        f"spanning {helper_span_length} lines, enclosing at line "
        f"{enclosing_definition_line} spanning {enclosing_span_length} lines)"
    )
    assert expected_fragment in matching_issues[0], (
        "The commit gate reconstructs scope from the message text, so the inline "
        "duplicate message must carry BOTH the helper and the enclosing spans — "
        "the union the PreToolUse path scopes on — not the helper span alone, "
        f"got: {matching_issues[0]}"
    )
