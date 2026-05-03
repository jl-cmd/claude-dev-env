"""Unit tests for banned-identifier check in code_rules_enforcer hook."""

import importlib.util
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIR / "code_rules_enforcer.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
check_banned_identifiers = hook_module.check_banned_identifiers

PRODUCTION_FILE_PATH = "packages/app/services/loader.py"
TEST_FILE_PATH = "packages/app/services/test_loader.py"


def test_should_flag_result_assignment() -> None:
    content = "def load():\n    result = compute()\n    return result\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("result" in issue for issue in issues)


def test_should_flag_data_assignment() -> None:
    content = "def fetch():\n    data = read()\n    return data\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("data" in issue for issue in issues)


def test_should_flag_output_assignment() -> None:
    content = "def render():\n    output = build()\n    return output\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("output" in issue for issue in issues)


def test_should_flag_response_assignment() -> None:
    content = "def call():\n    response = send()\n    return response\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("response" in issue for issue in issues)


def test_should_flag_value_assignment() -> None:
    content = "def read():\n    value = lookup()\n    return value\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("value" in issue for issue in issues)


def test_should_flag_item_assignment() -> None:
    content = "def pick():\n    item = first()\n    return item\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("item" in issue for issue in issues)


def test_should_flag_temp_assignment() -> None:
    content = "def swap():\n    temp = holder()\n    return temp\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("temp" in issue for issue in issues)


def test_should_flag_annotated_assignment() -> None:
    content = "def build() -> dict:\n    data: dict = {}\n    return data\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("data" in issue for issue in issues)


def test_should_not_flag_descriptive_names() -> None:
    content = (
        "def summarize_orders():\n"
        "    all_users = load_users()\n"
        "    is_valid = True\n"
        "    price_by_product = {}\n"
        "    for each_order in all_users:\n"
        "        pass\n"
    )
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_not_flag_name_containing_banned_substring() -> None:
    content = (
        "def aggregate():\n"
        "    result_set = fetch()\n"
        "    data_map = {}\n"
        "    value_counts = []\n"
        "    return result_set, data_map, value_counts\n"
    )
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_skip_test_files() -> None:
    content = "def test_thing():\n    result = compute()\n    assert result\n"
    issues = check_banned_identifiers(content, TEST_FILE_PATH)
    assert issues == []


def test_should_skip_hook_infrastructure() -> None:
    hook_path = "/home/user/.claude/hooks/some-hook.py"
    content = "def run():\n    data = gather()\n    return data\n"
    issues = check_banned_identifiers(content, hook_path)
    assert issues == []


def test_should_cap_at_three_issues() -> None:
    content = (
        "def many_bad():\n"
        "    result = 1\n"
        "    data = 2\n"
        "    output = 3\n"
        "    response = 4\n"
        "    value = 5\n"
        "    return result\n"
    )
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 3


def test_should_include_line_number_and_name() -> None:
    content = "def run():\n    result = 1\n    return result\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "Line 2" in issues[0]
    assert "'result'" in issues[0]


def test_should_handle_syntax_error_gracefully() -> None:
    content = "def broken(\n    this is not python\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert issues == []


def test_should_flag_tuple_unpacking_target() -> None:
    content = "def run():\n    result, err = compute()\n    return result, err\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'result'" in issue for issue in issues)


def test_should_flag_list_unpacking_target() -> None:
    content = "def run():\n    [data, meta] = fetch()\n    return data, meta\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'data'" in issue for issue in issues)


def test_should_flag_starred_unpacking_target() -> None:
    content = "def run():\n    head, *data = fetch()\n    return head, data\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'data'" in issue for issue in issues)


def test_should_flag_for_loop_target() -> None:
    content = "def run(orders):\n    for result in orders:\n        pass\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'result'" in issue for issue in issues)


def test_should_flag_async_for_loop_target() -> None:
    content = (
        "async def run(orders):\n"
        "    async for data in orders:\n"
        "        pass\n"
    )
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'data'" in issue for issue in issues)


def test_should_flag_list_comprehension_target() -> None:
    content = "def run(rows):\n    seen = [x for data in rows]\n    return seen\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'data'" in issue for issue in issues)


def test_should_flag_dict_comprehension_target() -> None:
    content = "def run(rows):\n    mapping = {k: v for value in rows}\n    return mapping\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'value'" in issue for issue in issues)


def test_should_flag_generator_expression_target() -> None:
    content = "def run(rows):\n    stream = (x for item in rows)\n    return stream\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'item'" in issue for issue in issues)


def test_should_flag_with_as_target() -> None:
    content = (
        "def run():\n"
        "    with open('a') as data:\n"
        "        return data.read()\n"
    )
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'data'" in issue for issue in issues)


def test_should_flag_walrus_target() -> None:
    content = "def run(source):\n    if (data := source()):\n        return data\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'data'" in issue for issue in issues)


def test_should_return_issues_in_source_line_order() -> None:
    content = (
        "def outer():\n"
        "    def inner():\n"
        "        result = 1\n"
        "        data = 2\n"
        "        return result\n"
        "    output = inner()\n"
        "    return output\n"
    )
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 3
    assert "Line 3" in issues[0]
    assert "Line 4" in issues[1]
    assert "Line 6" in issues[2]


def test_should_emit_stderr_advisory_on_syntax_error(
    capsys: "object",
) -> None:
    content = "def broken(\n    this is not python\n"
    check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "banned-identifier check skipped" in captured.err
    assert PRODUCTION_FILE_PATH in captured.err


def test_should_flag_argv_assignment() -> None:
    content = "def parse_command():\n    argv = collect()\n    return argv\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'argv'" in each_issue for each_issue in issues), (
        f"Expected 'argv' flagged — use arguments_list, got: {issues}"
    )


def test_should_flag_args_assignment() -> None:
    content = "def parse_command():\n    args = collect()\n    return args\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'args'" in each_issue for each_issue in issues), (
        f"Expected 'args' flagged — use arguments, got: {issues}"
    )


def test_should_flag_kwargs_assignment() -> None:
    content = "def parse_command():\n    kwargs = collect()\n    return kwargs\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'kwargs'" in each_issue for each_issue in issues), (
        f"Expected 'kwargs' flagged — use keyword_arguments, got: {issues}"
    )


def test_should_flag_argc_assignment() -> None:
    content = "def parse_command():\n    argc = count()\n    return argc\n"
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert any("'argc'" in each_issue for each_issue in issues), (
        f"Expected 'argc' flagged — use argument_count, got: {issues}"
    )


def test_should_not_flag_args_as_function_parameter() -> None:
    content = (
        "def passthrough(*args, **kwargs):\n"
        "    return args, kwargs\n"
    )
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"*args/**kwargs parameters are Python convention, must not flag, got: {issues}"
    )


def test_should_not_flag_argv_substring_in_local_name() -> None:
    content = (
        "def parse_command():\n"
        "    parsed_argv_entries = []\n"
        "    return parsed_argv_entries\n"
    )
    issues = check_banned_identifiers(content, PRODUCTION_FILE_PATH)
    assert issues == [], (
        f"Substring 'argv' inside parsed_argv_entries must not flag, got: {issues}"
    )
