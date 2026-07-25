"""Tests for slice dependency verification."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from verify_slice_dependencies import (  # noqa: E402
    collect_attribute_reads,
    collect_config_field_definitions,
    collect_imported_names,
    collect_top_level_definitions,
    is_production_path,
    is_python_path,
    parse_source,
    read_source_files,
    verify_slice_dependencies,
)

SETTINGS_SOURCE = """
from dataclasses import dataclass


@dataclass(frozen=True)
class StpFileConfig:
    CLOSE_TAG: str = "</MenuInfoSet>"
    GUID_PATTERN: str = "/IM/"


STP_FILES = StpFileConfig()
"""

READER_ONE_SOURCE = """
from src.config.settings import STP_FILES


def close(text):
    return text.replace(STP_FILES.CLOSE_TAG, "")
"""

READER_TWO_SOURCE = """
from src.config.settings import STP_FILES


def guid(text):
    return STP_FILES.GUID_PATTERN in text
"""

HELPER_SOURCE = """
def shared_helper(value):
    return value
"""

HELPER_CALLER_SOURCE = """
from src.processors.helper import shared_helper


def run(value):
    return shared_helper(value)
"""


def slice_record(index, slug, files):
    """Build a minimal slice record for the verifier."""
    return {"index": index, "slug": slug, "files": list(files)}


class TestCollectors:
    """Cover the AST collectors the verifier builds its graph from."""

    def test_collects_config_dataclass_field_names(self) -> None:
        """Should return the fields of a Config-suffixed dataclass."""
        assert collect_config_field_definitions(SETTINGS_SOURCE) == {
            "CLOSE_TAG",
            "GUID_PATTERN",
        }

    def test_collects_top_level_definitions(self) -> None:
        """Should return module-level bindings, classes, and functions."""
        assert "STP_FILES" in collect_top_level_definitions(SETTINGS_SOURCE)
        assert "StpFileConfig" in collect_top_level_definitions(SETTINGS_SOURCE)
        assert "shared_helper" in collect_top_level_definitions(HELPER_SOURCE)

    def test_collects_attribute_reads_inside_function_bodies(self) -> None:
        """Should see attribute reads the collect-only gate cannot reach."""
        all_reads = collect_attribute_reads(READER_ONE_SOURCE)

        assert "CLOSE_TAG" in all_reads
        assert "replace" in all_reads, "every attribute read is collected"


class TestForwardReferences:
    """Cover the runtime constraint: a definition must not land after its use."""

    def test_flags_a_config_field_read_before_the_slice_that_defines_it(self) -> None:
        """Should flag a reader slice that lands before the settings slice."""
        report = report_for(
            [
                slice_record(1, "reader", ["src/reader_one.py"]),
                slice_record(2, "settings", ["src/config/settings.py"]),
            ],
            {
                "src/reader_one.py": READER_ONE_SOURCE,
                "src/config/settings.py": SETTINGS_SOURCE,
            },
        )

        assert report["is_valid"] is False
        # Both are real forward references: the field read inside the function
        # body, and the module-level import of the object that carries it.
        assert {each["symbol"] for each in report["forward_references"]} == {
            "CLOSE_TAG",
            "STP_FILES",
        }
        field_violation = next(
            each
            for each in report["forward_references"]
            if each["symbol"] == "CLOSE_TAG"
        )
        assert field_violation["referencing_slice"] == 1
        assert field_violation["defining_slice"] == 2

    def test_flags_a_helper_function_defined_in_a_later_slice(self) -> None:
        """Should catch non-constant forward references, not only constants."""
        report = report_for(
            [
                slice_record(1, "caller", ["src/caller.py"]),
                slice_record(2, "helper", ["src/processors/helper.py"]),
            ],
            {
                "src/caller.py": HELPER_CALLER_SOURCE,
                "src/processors/helper.py": HELPER_SOURCE,
            },
        )

        assert report["is_valid"] is False
        assert [each["symbol"] for each in report["forward_references"]] == [
            "shared_helper"
        ]

    def test_accepts_a_definition_that_lands_in_the_same_slice(self) -> None:
        """Should pass when the definition travels with its reader."""
        report = report_for(
            [
                slice_record(
                    1, "together", ["src/config/settings.py", "src/reader_one.py"]
                ),
                slice_record(2, "later-reader", ["src/reader_two.py"]),
            ],
            {
                "src/config/settings.py": SETTINGS_SOURCE,
                "src/reader_one.py": READER_ONE_SOURCE,
                "src/reader_two.py": READER_TWO_SOURCE,
            },
        )

        assert report["forward_references"] == []

    def test_ignores_a_name_that_no_changed_file_defines(self) -> None:
        """Should ignore names already on the base branch."""
        report = report_for(
            [slice_record(1, "reader", ["src/reader_one.py"])],
            {"src/reader_one.py": READER_ONE_SOURCE},
        )

        assert report["forward_references"] == []


class TestUnreadConfigFields:
    """Cover the gate constraint: a config field needs a production reader."""

    def test_flags_a_settings_slice_whose_readers_all_land_later(self) -> None:
        """Should reproduce the dead-config-field rejection at plan time."""
        report = report_for(
            [
                slice_record(1, "settings", ["src/config/settings.py"]),
                slice_record(2, "reader-one", ["src/reader_one.py"]),
                slice_record(3, "reader-two", ["src/reader_two.py"]),
            ],
            {
                "src/config/settings.py": SETTINGS_SOURCE,
                "src/reader_one.py": READER_ONE_SOURCE,
                "src/reader_two.py": READER_TWO_SOURCE,
            },
        )

        assert report["is_valid"] is False
        assert {each["field"] for each in report["unread_config_fields"]} == {
            "CLOSE_TAG",
            "GUID_PATTERN",
        }

    def test_a_test_module_reader_does_not_keep_a_field_live(self) -> None:
        """Should match the hook, which counts production readers only."""
        report = report_for(
            [
                slice_record(
                    1, "settings", ["src/config/settings.py", "tests/test_reader.py"]
                ),
                slice_record(2, "reader-one", ["src/reader_one.py"]),
                slice_record(3, "reader-two", ["src/reader_two.py"]),
            ],
            {
                "src/config/settings.py": SETTINGS_SOURCE,
                "tests/test_reader.py": READER_ONE_SOURCE,
                "src/reader_one.py": READER_ONE_SOURCE,
                "src/reader_two.py": READER_TWO_SOURCE,
            },
        )

        assert "CLOSE_TAG" in {
            each["field"] for each in report["unread_config_fields"]
        }


class TestCoalesceSuggestion:
    """Cover the resolution the operator is offered when both edges conflict."""

    def test_suggests_the_minimum_readers_that_cover_every_field(self) -> None:
        """Should name settings plus the fewest readers covering all fields."""
        report = report_for(
            [
                slice_record(1, "settings", ["src/config/settings.py"]),
                slice_record(2, "reader-one", ["src/reader_one.py"]),
                slice_record(3, "reader-two", ["src/reader_two.py"]),
            ],
            {
                "src/config/settings.py": SETTINGS_SOURCE,
                "src/reader_one.py": READER_ONE_SOURCE,
                "src/reader_two.py": READER_TWO_SOURCE,
            },
        )

        assert report["coalesce_suggestion"] == [
            "src/config/settings.py",
            "src/reader_one.py",
            "src/reader_two.py",
        ]

    def test_reports_valid_when_the_ordering_satisfies_both_constraints(self) -> None:
        """Should pass and suggest nothing when readers ship with settings."""
        report = report_for(
            [
                slice_record(
                    1,
                    "foundation",
                    [
                        "src/config/settings.py",
                        "src/reader_one.py",
                        "src/reader_two.py",
                    ],
                ),
            ],
            {
                "src/config/settings.py": SETTINGS_SOURCE,
                "src/reader_one.py": READER_ONE_SOURCE,
                "src/reader_two.py": READER_TWO_SOURCE,
            },
        )

        assert report["is_valid"] is True
        assert report["coalesce_suggestion"] == []
        assert report["errors"] == []


class TestNonPythonFiles:
    """Cover files the analysis cannot parse."""

    def test_ignores_documentation_and_unparsable_files(self) -> None:
        """Should skip non-Python paths rather than fail the plan."""
        report = report_for(
            [slice_record(1, "docs", ["docs/readme.md", "src/reader_one.py"])],
            {"docs/readme.md": "# not python", "src/reader_one.py": READER_ONE_SOURCE},
        )

        assert report["is_valid"] is True


BASE_SETTINGS_SOURCE = """
from dataclasses import dataclass


@dataclass(frozen=True)
class StpFileConfig:
    CLOSE_TAG: str = "</MenuInfoSet>"


STP_FILES = StpFileConfig()
"""

BASE_HELPER_SOURCE = """
def shared_helper(value):
    return value
"""


class TestBaseBranchAwareness:
    """Cover subtraction of symbols the base branch already carries."""

    def test_does_not_flag_a_symbol_the_base_already_defines(self) -> None:
        """Should ignore a name present on the base from slice one."""
        report = report_for(
            [
                slice_record(1, "caller", ["src/caller.py"]),
                slice_record(2, "helper", ["src/processors/helper.py"]),
            ],
            {
                "src/caller.py": HELPER_CALLER_SOURCE,
                "src/processors/helper.py": HELPER_SOURCE,
            },
            {"src/processors/helper.py": BASE_HELPER_SOURCE},
        )

        assert report["forward_references"] == []
        assert report["is_valid"] is True

    def test_does_not_flag_a_config_field_that_is_not_new(self) -> None:
        """Should judge only fields this change adds."""
        report = report_for(
            [
                slice_record(1, "settings", ["src/config/settings.py"]),
                slice_record(2, "reader-one", ["src/reader_one.py"]),
                slice_record(3, "reader-two", ["src/reader_two.py"]),
            ],
            {
                "src/config/settings.py": SETTINGS_SOURCE,
                "src/reader_one.py": READER_ONE_SOURCE,
                "src/reader_two.py": READER_TWO_SOURCE,
            },
            {"src/config/settings.py": BASE_SETTINGS_SOURCE},
        )

        assert {each["field"] for each in report["unread_config_fields"]} == {
            "GUID_PATTERN"
        }, "CLOSE_TAG already existed on the base and is not this change's problem"


class TestPathClassification:
    """Cover the path predicates that scope the analysis."""

    def test_recognises_python_paths_only(self) -> None:
        """Should accept .py files and reject other extensions."""
        assert is_python_path("src/a.py") is True
        assert is_python_path("docs/a.md") is False

    def test_excludes_test_and_migration_modules_as_readers(self) -> None:
        """Should match the hook, which counts production readers only."""
        assert is_production_path("src/processors/a.py") is True
        assert is_production_path("tests/test_a.py") is False
        assert is_production_path("src/config/migrations/add_a.py") is False


class TestParsing:
    """Cover tolerance of files the analysis cannot read."""

    def test_returns_none_for_unparsable_source(self) -> None:
        """Should return None rather than raise on a syntax error."""
        assert parse_source("def broken(:\n") is None

    def test_returns_a_module_whose_body_carries_the_statements(self) -> None:
        """Should return a module a caller can walk for definitions."""
        tree = parse_source("x = 1\n")

        assert [type(each_statement).__name__ for each_statement in tree.body] == [
            "Assign"
        ]


class TestImportedNames:
    """Cover from-import collection."""

    def test_collects_named_imports(self) -> None:
        """Should return each name a from-import binds."""
        assert collect_imported_names(
            "from src.config.settings import STP_FILES, OTHER\n"
        ) == {"STP_FILES", "OTHER"}

    def test_ignores_star_imports(self) -> None:
        """Should skip a star import, which binds no single name."""
        assert collect_imported_names("from src.config.settings import *\n") == set()


class TestReadSourceFiles:
    """Cover reading changed files out of a branch."""

    def test_reads_tracked_paths_and_skips_missing_ones(self, tmp_path: Path) -> None:
        """Should return only the paths the branch actually carries."""
        subprocess.run(["git", "init", "--initial-branch=main", str(tmp_path)], check=True, capture_output=True)
        for each_argument in (
            ["config", "user.email", "t@example.com"],
            ["config", "user.name", "Test"],
            ["config", "commit.gpgsign", "false"],
        ):
            subprocess.run(["git", *each_argument], cwd=tmp_path, check=True, capture_output=True)
        (tmp_path / "present.py").write_text("VALUE = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
        # Point hooks at an empty directory so a globally configured pre-commit
        # hook cannot run against this throwaway fixture repository.
        empty_hooks = tmp_path / "empty-hooks"
        empty_hooks.mkdir()
        subprocess.run(
            ["git", "-c", f"core.hooksPath={empty_hooks}", "commit", "-m", "seed"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        all_sources = read_source_files(tmp_path, "main", ["present.py", "absent.py"])

        assert "VALUE = 1" in all_sources["present.py"]
        assert "absent.py" not in all_sources


def report_for(
    all_slices: list,
    all_sources_by_path: dict,
    all_base_sources_by_path: dict | None = None,
) -> dict:
    """Run the verifier, defaulting the base branch to an empty mapping."""
    return verify_slice_dependencies(
        all_slices, all_sources_by_path, all_base_sources_by_path or {}
    )
