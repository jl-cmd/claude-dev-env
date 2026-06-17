from __future__ import annotations

import importlib.util
from pathlib import Path

ENFORCER_PATH = Path(__file__).resolve().parent / "code_rules_enforcer.py"
specification = importlib.util.spec_from_file_location("code_rules_enforcer", ENFORCER_PATH)
assert specification is not None and specification.loader is not None
code_rules_enforcer = importlib.util.module_from_spec(specification)
specification.loader.exec_module(code_rules_enforcer)

PRODUCTION_FILE_PATH = "packages/app/services/render_report.py"
TEST_FILE_PATH = "packages/app/services/test_render_report.py"
MIGRATION_FILE_PATH = "packages/app/migrations/0001_initial.py"


def _check(source: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_dead_argparse_arguments(source, file_path)


def test_should_flag_optional_argument_whose_dest_is_never_read() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', default='.')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    print('done')\n"
    )
    issues = _check(source, PRODUCTION_FILE_PATH)
    assert any("'repo'" in each_issue for each_issue in issues), (
        f"Expected dead '--repo' argument flagged, got: {issues}"
    )
    assert any("Line 5" in each_issue for each_issue in issues), (
        f"Expected the add_argument line reported, got: {issues}"
    )


def test_should_not_flag_when_dest_is_read_via_attribute_access() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> str:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', default='.')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    return parsed_arguments.repo\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_not_flag_a_positional_argument() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('path')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    print('done')\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_not_flag_help_action_argument() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser(add_help=False)\n"
        "    argument_parser.add_argument('--help', action='help')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    print('done')\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_not_flag_version_action_argument() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--version', action='version', version='1.0')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    print('done')\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_respect_explicit_dest_when_unread() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', dest='repository')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    print('done')\n"
    )
    issues = _check(source, PRODUCTION_FILE_PATH)
    assert any("'repository'" in each_issue for each_issue in issues), (
        f"Expected the explicit dest flagged, got: {issues}"
    )
    assert not any("'repo'" in each_issue for each_issue in issues), (
        f"The option string must not be flagged when dest is explicit, got: {issues}"
    )


def test_should_respect_explicit_dest_when_read() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> str:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', dest='repository')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    return parsed_arguments.repository\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_derive_dest_from_dashed_long_option() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> bool:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--dry-run', action='store_true')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    return parsed_arguments.dry_run\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_flag_dashed_long_option_when_dest_unread() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--dry-run', action='store_true')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    print('done')\n"
    )
    issues = _check(source, PRODUCTION_FILE_PATH)
    assert any("'dry_run'" in each_issue for each_issue in issues), (
        f"Expected the dashed long option dest flagged, got: {issues}"
    )


def test_should_derive_dest_from_long_option_when_short_precedes() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('-r', '--repo')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    print('done')\n"
    )
    issues = _check(source, PRODUCTION_FILE_PATH)
    assert any("'repo'" in each_issue for each_issue in issues), (
        f"Expected dest derived from the long option, got: {issues}"
    )


def test_should_suppress_when_namespace_is_forwarded_to_a_call() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def run(parsed_arguments: argparse.Namespace) -> None:\n"
        "    print('run')\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', default='.')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    run(parsed_arguments)\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_when_tuple_unpacked_namespace_is_forwarded() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def main(parsed_arguments: argparse.Namespace) -> None:\n"
        "    print('run')\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--verbose', action='store_true')\n"
        "    parsed_arguments, remaining = argument_parser.parse_known_args()\n"
        "    main(parsed_arguments)\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_when_aliased_namespace_is_forwarded() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def run(parsed_arguments: argparse.Namespace) -> None:\n"
        "    print('run')\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', default='.')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    alias = parsed_arguments\n"
        "    run(alias)\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_when_namespace_consumed_by_vars() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> dict:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', default='.')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    return vars(parsed_arguments)\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_when_namespace_dict_accessed() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> dict:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', default='.')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    return parsed_arguments.__dict__\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_be_silent_for_test_files() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', default='.')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    print('done')\n"
    )
    assert _check(source, TEST_FILE_PATH) == []


def test_should_be_silent_for_migration_files() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', default='.')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    print('done')\n"
    )
    assert _check(source, MIGRATION_FILE_PATH) == []


def test_should_tolerate_syntax_error() -> None:
    assert _check("def broken(:\n", PRODUCTION_FILE_PATH) == []


def test_should_return_empty_when_no_add_argument_present() -> None:
    source = "def build() -> int:\n    return 1\n"
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_when_namespace_unpacked_with_double_star() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def run(repo: str) -> None:\n"
        "    print(repo)\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', default='.')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    run(**vars(parsed_arguments))\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_not_flag_when_dest_read_via_literal_getattr() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> str:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', default='.')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    return getattr(parsed_arguments, 'repo')\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_when_namespace_stored_on_attribute_target() -> None:
    source = (
        "import argparse\n"
        "\n"
        "class App:\n"
        "    def build(self) -> None:\n"
        "        argument_parser = argparse.ArgumentParser()\n"
        "        argument_parser.add_argument('--repo', default='.')\n"
        "        argument_parser.add_argument('--verbose', action='store_true')\n"
        "        self.parsed_arguments = argument_parser.parse_args()\n"
        "\n"
        "    def run(self) -> dict:\n"
        "        return dict(**vars(self.parsed_arguments))\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_when_parse_method_is_aliased() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def run(parsed_arguments: argparse.Namespace) -> None:\n"
        "    print('run')\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', default='.')\n"
        "    parse = argument_parser.parse_args\n"
        "    parsed_arguments = parse()\n"
        "    run(parsed_arguments)\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_should_suppress_when_namespace_forwarded_inside_container() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def run(payload: dict) -> None:\n"
        "    print('run')\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', default='.')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    run({'args': parsed_arguments})\n"
    )
    assert _check(source, PRODUCTION_FILE_PATH) == []


def test_validate_content_runs_dead_argparse_check() -> None:
    source = (
        "import argparse\n"
        "\n"
        "def build() -> None:\n"
        "    argument_parser = argparse.ArgumentParser()\n"
        "    argument_parser.add_argument('--repo', default='.')\n"
        "    parsed_arguments = argument_parser.parse_args()\n"
        "    print('done')\n"
    )
    issues = code_rules_enforcer.validate_content(source, PRODUCTION_FILE_PATH)
    assert any("'repo'" in each_issue for each_issue in issues), (
        f"Expected the enforcer dispatch to surface the dead argument, got: {issues}"
    )
