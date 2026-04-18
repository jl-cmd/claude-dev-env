"""Tests for file structure validation checks."""

import tempfile
from pathlib import Path
from typing import List

import pytest

from .file_structure_checks import (
    Violation,
    check_multiple_requirements_txt,
    check_empty_init_files,
    main,
)


class TestMultipleRequirementsTxt:
    """Test detection of multiple requirements.txt files."""

    def test_single_requirements_txt_passes(self, tmp_path: Path) -> None:
        """Single requirements.txt at root should pass."""
        (tmp_path / "requirements.txt").write_text("pytest==7.4.0\n")

        violations = check_multiple_requirements_txt(tmp_path)

        assert violations == []

    def test_multiple_requirements_txt_fails(self, tmp_path: Path) -> None:
        """Multiple requirements.txt files should fail."""
        (tmp_path / "requirements.txt").write_text("pytest==7.4.0\n")
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "requirements.txt").write_text("requests==2.31.0\n")

        violations = check_multiple_requirements_txt(tmp_path)

        assert len(violations) == 1
        assert "multiple requirements.txt" in violations[0].message.lower()
        assert "tools/requirements.txt" in violations[0].message

    def test_no_requirements_txt_passes(self, tmp_path: Path) -> None:
        """No requirements.txt files should pass (not our concern)."""
        violations = check_multiple_requirements_txt(tmp_path)

        assert violations == []

    def test_excludes_venv_directories(self, tmp_path: Path) -> None:
        """Should ignore requirements.txt in venv/node_modules."""
        (tmp_path / "requirements.txt").write_text("pytest==7.4.0\n")

        venv_dir = tmp_path / ".venv" / "lib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "requirements.txt").write_text("ignored")

        node_dir = tmp_path / "node_modules" / "package"
        node_dir.mkdir(parents=True)
        (node_dir / "requirements.txt").write_text("ignored")

        violations = check_multiple_requirements_txt(tmp_path)

        assert violations == []

    def test_three_requirements_files_reports_all(self, tmp_path: Path) -> None:
        """Should report all extra requirements.txt files."""
        (tmp_path / "requirements.txt").write_text("pytest==7.4.0\n")
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "requirements.txt").write_text("requests==2.31.0\n")
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "requirements.txt").write_text("pandas==2.0.0\n")

        violations = check_multiple_requirements_txt(tmp_path)

        assert len(violations) == 1
        assert "tools/requirements.txt" in violations[0].message
        assert "scripts/requirements.txt" in violations[0].message


class TestEmptyInitFiles:
    """Test detection of empty __init__.py files."""

    def test_no_init_files_passes(self, tmp_path: Path) -> None:
        """No __init__.py files should pass."""
        violations = check_empty_init_files(tmp_path)

        assert violations == []

    def test_non_empty_init_passes(self, tmp_path: Path) -> None:
        """__init__.py with content should pass."""
        package_dir = tmp_path / "mypackage"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("from .module import func\n")

        violations = check_empty_init_files(tmp_path)

        assert violations == []

    def test_empty_init_fails(self, tmp_path: Path) -> None:
        """Empty __init__.py should fail."""
        package_dir = tmp_path / "mypackage"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("")

        violations = check_empty_init_files(tmp_path)

        assert len(violations) == 1
        assert violations[0].file == "mypackage/__init__.py"
        assert violations[0].line == 1
        assert "empty" in violations[0].message.lower()

    def test_whitespace_only_init_fails(self, tmp_path: Path) -> None:
        """__init__.py with only whitespace should fail."""
        package_dir = tmp_path / "mypackage"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("   \n\n  \t\n")

        violations = check_empty_init_files(tmp_path)

        assert len(violations) == 1
        assert "empty" in violations[0].message.lower()

    def test_multiple_empty_init_files(self, tmp_path: Path) -> None:
        """Should detect all empty __init__.py files."""
        (tmp_path / "pkg1").mkdir()
        (tmp_path / "pkg1" / "__init__.py").write_text("")

        (tmp_path / "pkg2").mkdir()
        (tmp_path / "pkg2" / "__init__.py").write_text("  ")

        (tmp_path / "pkg3").mkdir()
        (tmp_path / "pkg3" / "__init__.py").write_text("# comment\n")

        violations = check_empty_init_files(tmp_path)

        assert len(violations) == 2
        files = [v.file for v in violations]
        assert "pkg1/__init__.py" in files
        assert "pkg2/__init__.py" in files

    def test_excludes_venv_directories(self, tmp_path: Path) -> None:
        """Should ignore __init__.py in excluded directories."""
        venv_dir = tmp_path / ".venv" / "lib" / "package"
        venv_dir.mkdir(parents=True)
        (venv_dir / "__init__.py").write_text("")

        node_dir = tmp_path / "node_modules" / "package"
        node_dir.mkdir(parents=True)
        (node_dir / "__init__.py").write_text("")

        violations = check_empty_init_files(tmp_path)

        assert violations == []

    def test_excludes_django_migrations_init(self, tmp_path: Path) -> None:
        """Should ignore empty __init__.py in Django migrations directory."""
        migrations_dir = tmp_path / "myapp" / "migrations"
        migrations_dir.mkdir(parents=True)
        (migrations_dir / "__init__.py").write_text("")

        violations = check_empty_init_files(tmp_path)

        assert violations == []

    def test_excludes_django_management_init(self, tmp_path: Path) -> None:
        """Should ignore empty __init__.py in Django management directory."""
        mgmt_dir = tmp_path / "myapp" / "management"
        mgmt_dir.mkdir(parents=True)
        (mgmt_dir / "__init__.py").write_text("")

        violations = check_empty_init_files(tmp_path)

        assert violations == []

    def test_excludes_django_commands_init(self, tmp_path: Path) -> None:
        """Should ignore empty __init__.py in Django commands directory."""
        cmd_dir = tmp_path / "myapp" / "management" / "commands"
        cmd_dir.mkdir(parents=True)
        (cmd_dir / "__init__.py").write_text("")

        violations = check_empty_init_files(tmp_path)

        assert violations == []

    def test_excludes_django_templatetags_init(self, tmp_path: Path) -> None:
        """Should ignore empty __init__.py in Django templatetags directory."""
        tags_dir = tmp_path / "myapp" / "templatetags"
        tags_dir.mkdir(parents=True)
        (tags_dir / "__init__.py").write_text("")

        violations = check_empty_init_files(tmp_path)

        assert violations == []

    def test_still_catches_non_django_empty_init(self, tmp_path: Path) -> None:
        """Should still catch empty __init__.py in non-Django directories."""
        # Django directory - should be skipped
        migrations_dir = tmp_path / "myapp" / "migrations"
        migrations_dir.mkdir(parents=True)
        (migrations_dir / "__init__.py").write_text("")

        # Non-Django directory - should be caught
        utils_dir = tmp_path / "myapp" / "utils"
        utils_dir.mkdir(parents=True)
        (utils_dir / "__init__.py").write_text("")

        violations = check_empty_init_files(tmp_path)

        assert len(violations) == 1
        assert "utils/__init__.py" in violations[0].file

    def test_excludes_django_app_with_models(self, tmp_path: Path) -> None:
        """Should ignore empty __init__.py in Django app directory with models.py."""
        app_dir = tmp_path / "myapp"
        app_dir.mkdir()
        (app_dir / "__init__.py").write_text("")
        (app_dir / "models.py").write_text("from django.db import models\n")

        violations = check_empty_init_files(tmp_path)

        assert violations == []

    def test_excludes_django_app_with_views(self, tmp_path: Path) -> None:
        """Should ignore empty __init__.py in Django app directory with views.py."""
        app_dir = tmp_path / "myapp"
        app_dir.mkdir()
        (app_dir / "__init__.py").write_text("")
        (app_dir / "views.py").write_text("from django.http import HttpResponse\n")

        violations = check_empty_init_files(tmp_path)

        assert violations == []

    def test_excludes_django_app_with_apps(self, tmp_path: Path) -> None:
        """Should ignore empty __init__.py in Django app directory with apps.py."""
        app_dir = tmp_path / "myapp"
        app_dir.mkdir()
        (app_dir / "__init__.py").write_text("")
        (app_dir / "apps.py").write_text("from django.apps import AppConfig\n")

        violations = check_empty_init_files(tmp_path)

        assert violations == []

    def test_excludes_django_settings_module(self, tmp_path: Path) -> None:
        """Should ignore empty __init__.py in Django settings module."""
        settings_dir = tmp_path / "myproject"
        settings_dir.mkdir()
        (settings_dir / "__init__.py").write_text("")
        (settings_dir / "settings.py").write_text("DEBUG = True\n")

        violations = check_empty_init_files(tmp_path)

        assert violations == []


class TestMain:
    """Test main function integration."""

    def test_main_no_violations_exits_zero(self, tmp_path: Path, capsys) -> None:
        """main() should exit 0 when no violations found."""
        (tmp_path / "requirements.txt").write_text("pytest==7.4.0\n")

        with pytest.raises(SystemExit) as exc_info:
            main([str(tmp_path)])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_main_with_violations_exits_one(self, tmp_path: Path, capsys) -> None:
        """main() should exit 1 and print violations when found."""
        package_dir = tmp_path / "mypackage"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("")

        with pytest.raises(SystemExit) as exc_info:
            main([str(tmp_path)])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "mypackage/__init__.py:1:" in captured.out
        assert "empty" in captured.out.lower()

    def test_main_prints_all_violations(self, tmp_path: Path, capsys) -> None:
        """main() should print all violations in file:line: format."""
        (tmp_path / "requirements.txt").write_text("pytest==7.4.0\n")
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "requirements.txt").write_text("requests==2.31.0\n")

        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "__init__.py").write_text("")

        with pytest.raises(SystemExit) as exc_info:
            main([str(tmp_path)])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "requirements.txt:1:" in captured.out
        assert "pkg/__init__.py:1:" in captured.out

    def test_main_requires_project_root_arg(self, capsys) -> None:
        """main() should exit 1 if no project root provided."""
        with pytest.raises(SystemExit) as exc_info:
            main([])

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "usage" in captured.out.lower()
