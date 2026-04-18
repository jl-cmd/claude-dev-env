"""Tests for magic value detection."""

import ast
import tempfile
from pathlib import Path

import pytest

from .magic_value_checks import (
    check_magic_values,
    validate_file,
)
from .validator_base import Violation


MAGIC_NUMBER_SOURCE = "x = 42\n"
NON_TEST_TEMPDIR_PREFIX = "src_"


GOOD_NAMED_CONSTANTS = '''
API_TIMEOUT_MS = 5000
HASH_DELIMITER = "__"

def process():
    timeout = API_TIMEOUT_MS
    return f"key{HASH_DELIMITER}value"
'''

BAD_MAGIC_NUMBER = '''
def process():
    timeout = 5000
    return timeout
'''

ALLOWED_SMALL_NUMBERS = '''
def process():
    count = 0
    increment = 1
    negative = -1
    return count + increment + negative
'''

ALLOWED_NEGATIVE_ONE_IN_BINARY_EXPRESSION = '''
def process(total):
    return total * -1
'''

ALLOWED_NEGATIVE_ONE_IN_RETURN = '''
def process():
    return -1
'''

BAD_NEGATIVE_LITERAL_TWO = '''
def process():
    return total * -2
'''

ALLOWED_EMPTY_STRING = '''
def process():
    result = ""
    return result
'''

BAD_LITERAL_TWO = '''
def process():
    doubled = something * 2
    return doubled
'''

BAD_LITERAL_ONE_HUNDRED = '''
def process():
    percentage = fraction * 100
    return percentage
'''

ALLOWED_NEGATIVE_UPPER_CONSTANT_ASSIGNMENT = '''
LIMIT = -100
OFFSET = -5
'''

ALLOWED_TYPED_NEGATIVE_UPPER_CONSTANT = '''
LIMIT: int = -100
OFFSET: int = -5
'''

DOUBLE_NEGATED_LITERAL = '''
def process():
    return --5
'''

DICT_VALUED_CONSTANT = '''
SETTINGS = {"timeout": 30, "retries": 5}
'''

TUPLE_VALUED_CONSTANT = '''
RETRY_DELAYS = (2, 4, 8)
'''

LIST_VALUED_CONSTANT = '''
PORTS = [8080, 8443, 9000]
'''

NESTED_DICT_VALUED_CONSTANT = '''
CONFIG = {"db": {"port": 5432}}
'''

ANNOTATED_SCALAR_CONSTANT = '''
TIMEOUT_MS: int = 5000
'''

ANNOTATED_DICT_VALUED_CONSTANT = '''
SETTINGS: dict[str, int] = {"timeout": 30}
'''

NON_CONSTANT_ASSIGNMENT_IN_FUNCTION = '''
def configure():
    delay = 30
    return delay
'''

SCALAR_MAGIC_NUMBER_OUTSIDE_CONSTANT = '''
def compute():
    return 30 + 5000
'''

LEADING_UNDERSCORE_TARGET = '''
_PRIVATE = {"timeout": 30}
'''

DOUBLE_UNDERSCORE_TARGET = '''
__PRIVATE = {"timeout": 30}
'''

NON_CONTAINER_RHS_CALL = '''
CONFIG = some_factory(30, retries=5)
'''

NON_CONTAINER_RHS_BINOP = '''
WINDOW = base + 5000
'''

TUPLE_TARGET_ASSIGNMENT = '''
A, B = 1, 30
'''

AUG_ASSIGN_UPPER_SNAKE = '''
COUNTER = 0
COUNTER += 30
'''

CLASS_BODY_UPPER_SNAKE_CONSTANT = '''
class Foo:
    TIMEOUT = 30
'''

ANNOTATED_LITERAL_TYPE = '''
X: Literal[42] = 42
'''

TRUE_LITERAL_IN_FUNCTION = '''
def configure():
    is_enabled = True
    return is_enabled
'''

FALSE_LITERAL_IN_FUNCTION = '''
def configure():
    is_disabled = False
    return is_disabled
'''


class TestMagicValues:
    def test_named_constants_pass(self) -> None:
        tree = ast.parse(GOOD_NAMED_CONSTANTS)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_magic_number_fails(self) -> None:
        tree = ast.parse(BAD_MAGIC_NUMBER)
        violations = check_magic_values(tree, "test.py")
        assert len(violations) == 1
        assert "5000" in violations[0].message

    def test_small_numbers_allowed(self) -> None:
        tree = ast.parse(ALLOWED_SMALL_NUMBERS)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_negative_one_allowed_in_binary_expression(self) -> None:
        tree = ast.parse(ALLOWED_NEGATIVE_ONE_IN_BINARY_EXPRESSION)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_negative_one_allowed_in_return_expression(self) -> None:
        tree = ast.parse(ALLOWED_NEGATIVE_ONE_IN_RETURN)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_negative_literal_two_is_flagged_with_signed_value(self) -> None:
        tree = ast.parse(BAD_NEGATIVE_LITERAL_TWO)
        violations = check_magic_values(tree, "test.py")
        assert len(violations) == 1
        assert "-2" in violations[0].message

    def test_empty_string_allowed(self) -> None:
        tree = ast.parse(ALLOWED_EMPTY_STRING)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_check_magic_values_should_flag_literal_two_in_function_body(self) -> None:
        tree = ast.parse(BAD_LITERAL_TWO)
        violations = check_magic_values(tree, "test.py")
        assert len(violations) == 1
        assert "2" in violations[0].message

    def test_check_magic_values_should_flag_literal_one_hundred_in_function_body(self) -> None:
        tree = ast.parse(BAD_LITERAL_ONE_HUNDRED)
        violations = check_magic_values(tree, "test.py")
        assert len(violations) == 1
        assert "100" in violations[0].message

    def test_negative_upper_constant_assignment_allowed(self) -> None:
        tree = ast.parse(ALLOWED_NEGATIVE_UPPER_CONSTANT_ASSIGNMENT)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_typed_negative_upper_constant_allowed(self) -> None:
        tree = ast.parse(ALLOWED_TYPED_NEGATIVE_UPPER_CONSTANT)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_double_negation_reports_collapsed_positive_value(self) -> None:
        tree = ast.parse(DOUBLE_NEGATED_LITERAL)
        violations = check_magic_values(tree, "test.py")
        assert len(violations) == 1
        assert "5" in violations[0].message
        assert "-5" not in violations[0].message

    def test_should_exempt_numbers_inside_dict_valued_constant(self) -> None:
        tree = ast.parse(DICT_VALUED_CONSTANT)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_should_exempt_numbers_inside_tuple_valued_constant(self) -> None:
        tree = ast.parse(TUPLE_VALUED_CONSTANT)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_should_exempt_numbers_inside_list_valued_constant(self) -> None:
        tree = ast.parse(LIST_VALUED_CONSTANT)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_should_exempt_numbers_inside_nested_dict_valued_constant(self) -> None:
        tree = ast.parse(NESTED_DICT_VALUED_CONSTANT)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_should_exempt_numbers_inside_annotated_upper_snake_constant(self) -> None:
        tree = ast.parse(ANNOTATED_SCALAR_CONSTANT)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_should_exempt_numbers_inside_annotated_dict_valued_constant(self) -> None:
        tree = ast.parse(ANNOTATED_DICT_VALUED_CONSTANT)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_should_still_flag_numbers_in_function_body_assignments(self) -> None:
        tree = ast.parse(NON_CONSTANT_ASSIGNMENT_IN_FUNCTION)
        violations = check_magic_values(tree, "test.py")
        assert len(violations) == 1
        assert "30" in violations[0].message

    def test_should_still_flag_scalar_magic_number_outside_constant(self) -> None:
        tree = ast.parse(SCALAR_MAGIC_NUMBER_OUTSIDE_CONSTANT)
        violations = check_magic_values(tree, "test.py")
        flagged_numbers = {violation.message for violation in violations}
        assert any("30" in message for message in flagged_numbers)
        assert any("5000" in message for message in flagged_numbers)

    def test_should_flag_literal_under_single_leading_underscore_target(self) -> None:
        tree = ast.parse(LEADING_UNDERSCORE_TARGET)
        violations = check_magic_values(tree, "test.py")
        assert any("30" in violation.message for violation in violations)

    def test_should_flag_literal_under_double_leading_underscore_target(self) -> None:
        tree = ast.parse(DOUBLE_UNDERSCORE_TARGET)
        violations = check_magic_values(tree, "test.py")
        assert any("30" in violation.message for violation in violations)

    def test_should_flag_literal_under_non_container_call_rhs(self) -> None:
        tree = ast.parse(NON_CONTAINER_RHS_CALL)
        violations = check_magic_values(tree, "test.py")
        flagged_numbers = {violation.message for violation in violations}
        assert any("30" in message for message in flagged_numbers)
        assert any("5" in message for message in flagged_numbers)

    def test_should_flag_literal_under_non_container_binop_rhs(self) -> None:
        tree = ast.parse(NON_CONTAINER_RHS_BINOP)
        violations = check_magic_values(tree, "test.py")
        assert any("5000" in violation.message for violation in violations)

    def test_tuple_target_assignment_flags_literal_when_no_upper_snake_target(
        self,
    ) -> None:
        tree = ast.parse(TUPLE_TARGET_ASSIGNMENT)
        violations = check_magic_values(tree, "test.py")
        assert any("30" in violation.message for violation in violations)

    def test_aug_assign_on_upper_snake_target_is_not_exempt(self) -> None:
        tree = ast.parse(AUG_ASSIGN_UPPER_SNAKE)
        violations = check_magic_values(tree, "test.py")
        assert any("30" in violation.message for violation in violations)

    def test_class_body_upper_snake_constant_is_exempt(self) -> None:
        tree = ast.parse(CLASS_BODY_UPPER_SNAKE_CONSTANT)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_annotated_literal_type_flags_literal_inside_subscript_annotation(
        self,
    ) -> None:
        tree = ast.parse(ANNOTATED_LITERAL_TYPE)
        violations = check_magic_values(tree, "test.py")
        assert any("42" in violation.message for violation in violations)

    def test_check_magic_values_should_not_flag_True_literal(self) -> None:
        tree = ast.parse(TRUE_LITERAL_IN_FUNCTION)
        violations = check_magic_values(tree, "test.py")
        assert violations == []

    def test_check_magic_values_should_not_flag_False_literal(self) -> None:
        tree = ast.parse(FALSE_LITERAL_IN_FUNCTION)
        violations = check_magic_values(tree, "test.py")
        assert violations == []


class TestValidateFilePathExemptions:
    def test_validate_file_should_skip_test_underscore_py_files(
        self, tmp_path: Path
    ) -> None:
        tests_directory = tmp_path / "tests"
        tests_directory.mkdir()
        test_module_path = tests_directory / "test_foo.py"
        test_module_path.write_text(MAGIC_NUMBER_SOURCE, encoding="utf-8")

        assert validate_file(test_module_path) == []

    def test_validate_file_should_skip_config_directory(
        self, tmp_path: Path
    ) -> None:
        config_directory = tmp_path / "config"
        config_directory.mkdir()
        constants_path = config_directory / "constants.py"
        constants_path.write_text(MAGIC_NUMBER_SOURCE, encoding="utf-8")

        assert validate_file(constants_path) == []

    def test_validate_file_should_skip_settings_py(self, tmp_path: Path) -> None:
        settings_path = tmp_path / "settings.py"
        settings_path.write_text(MAGIC_NUMBER_SOURCE, encoding="utf-8")

        assert validate_file(settings_path) == []

    def test_validate_file_should_skip_uppercase_config_directory(
        self, tmp_path: Path
    ) -> None:
        """Case-insensitive match so Config/ on case-preserving filesystems skips."""
        uppercase_config_directory = tmp_path / "Config"
        uppercase_config_directory.mkdir()
        constants_path = uppercase_config_directory / "constants.py"
        constants_path.write_text(MAGIC_NUMBER_SOURCE, encoding="utf-8")

        assert validate_file(constants_path) == []

    def test_validate_file_should_skip_mixed_case_tests_directory(
        self, tmp_path: Path
    ) -> None:
        """Case-insensitive match so src/Tests/ short-circuits the same way src/tests/ does."""
        mixed_case_tests_directory = tmp_path / "Tests"
        mixed_case_tests_directory.mkdir()
        test_module_path = mixed_case_tests_directory / "test_foo.py"
        test_module_path.write_text(MAGIC_NUMBER_SOURCE, encoding="utf-8")

        assert validate_file(test_module_path) == []

    def test_validate_file_should_skip_conftest_helpers(
        self, tmp_path: Path
    ) -> None:
        """Naked ``conftest`` substring matches conftest_helpers.py and similar."""
        conftest_helpers_path = tmp_path / "conftest_helpers.py"
        conftest_helpers_path.write_text(MAGIC_NUMBER_SOURCE, encoding="utf-8")

        assert validate_file(conftest_helpers_path) == []

    def test_validate_file_should_still_scan_production_py_files(self) -> None:
        """Use tempfile with a non-test prefix instead of the pytest tmp_path fixture.

        pytest's tmp_path produces directories like ``pytest-of-<user>/pytest-N/
        test_validate_file_should_still_scan_production_py_files0/`` whose names
        contain ``test_`` and ``pytest-`` -- both match TEST_PATH_PATTERNS, so
        validate_file would short-circuit via is_test_file and make this
        regression a false green.
        """
        with tempfile.TemporaryDirectory(
            prefix=NON_TEST_TEMPDIR_PREFIX
        ) as temporary_root:
            source_directory = Path(temporary_root) / "src"
            source_directory.mkdir()
            production_path = source_directory / "app.py"
            production_path.write_text(MAGIC_NUMBER_SOURCE, encoding="utf-8")

            violations = validate_file(production_path)
            assert len(violations) == 1
            assert "42" in violations[0].message
