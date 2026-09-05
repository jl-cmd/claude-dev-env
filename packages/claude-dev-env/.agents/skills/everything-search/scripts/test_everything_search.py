import importlib
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

search = importlib.import_module("everything_search")

KNOWN_PATH = "Y:\\Projects\\my-repo"
REGISTRY = {"my-repo": KNOWN_PATH}


def test_expand_search_arguments_rewrites_bare_registry_token() -> None:
    assert search.expand_search_arguments(["my-repo", "config.py"], REGISTRY) == [
        KNOWN_PATH,
        "config.py",
    ]


def test_expand_search_arguments_rewrites_exact_placeholder_token() -> None:
    assert search.expand_search_arguments(["{my-repo}", "config.py"], REGISTRY) == [
        KNOWN_PATH,
        "config.py",
    ]


def test_expand_search_arguments_preserves_unknown_tokens_and_spaces() -> None:
    all_arguments = ["unknown-name", "foo bar", "config.py"]
    assert search.expand_search_arguments(all_arguments, REGISTRY) == all_arguments


@pytest.mark.parametrize(
    "absolute_path",
    [
        "C:/Users/example/file.py",
        "\\\\server\\share\\folder",
        "/mnt/c/Projects/repo",
    ],
)
def test_expand_search_arguments_preserves_absolute_paths(absolute_path: str) -> None:
    assert search.expand_search_arguments([absolute_path], REGISTRY) == [absolute_path]


def test_expand_search_arguments_preserves_embedded_flag_tokens() -> None:
    all_arguments = ["--flag={my-repo}", "--regex=^{my-repo}$"]
    assert search.expand_search_arguments(all_arguments, REGISTRY) == all_arguments


def test_load_registry_returns_empty_mapping_for_missing_file(tmp_path: Path) -> None:
    assert search.load_registry(tmp_path / "missing.json") == {}


@pytest.mark.parametrize(
    "registry_bytes",
    [
        b"\xff",
        b"{not valid",
        json.dumps({"my-repo": 42}).encode(),
        json.dumps({"my-repo": ""}).encode(),
        json.dumps({"my-repo": "relative/path"}).encode(),
    ],
)
def test_load_registry_reports_invalid_input(
    tmp_path: Path, registry_bytes: bytes
) -> None:
    registry_path = tmp_path / "project-paths.json"
    registry_path.write_bytes(registry_bytes)
    with pytest.raises(search.RegistryRunFatal, match="(Malformed|Invalid)"):
        search.load_registry(registry_path)


def test_main_runs_direct_search_without_registry_or_shell() -> None:
    completed_process = search.subprocess.CompletedProcess(
        args=["es.exe", "foo bar"],
        returncode=0,
        stdout="found path\n",
        stderr="",
    )
    captured_stdout = io.StringIO()
    with (
        patch.object(search, "load_registry", return_value={}),
        patch.object(search.shutil, "which", return_value="es.exe"),
        patch.object(
            search.subprocess, "run", return_value=completed_process
        ) as run_process,
        patch.object(search.sys, "stdout", captured_stdout),
    ):
        exit_code = search.main(["foo bar"])
    assert exit_code == 0
    assert captured_stdout.getvalue() == "found path\n"
    run_process.assert_called_once_with(
        ["es.exe", "foo bar"],
        capture_output=True,
        check=False,
        encoding="utf-8",
        shell=False,
        text=True,
    )


def test_main_passes_through_child_exit_status() -> None:
    completed_process = search.subprocess.CompletedProcess(
        args=["es.exe", "config.py"], returncode=7, stdout="", stderr="failed\n"
    )
    captured_stderr = io.StringIO()
    with (
        patch.object(search, "load_registry", return_value={}),
        patch.object(search.shutil, "which", return_value="es.exe"),
        patch.object(search.subprocess, "run", return_value=completed_process),
        patch.object(search.sys, "stderr", captured_stderr),
    ):
        exit_code = search.main(["config.py"])
    assert exit_code == 7
    assert captured_stderr.getvalue() == "failed\n"


def test_main_reports_missing_executable() -> None:
    captured_stderr = io.StringIO()
    with (
        patch.object(search, "load_registry", return_value={}),
        patch.object(search.shutil, "which", return_value=None),
        patch.object(search.sys, "stderr", captured_stderr),
    ):
        exit_code = search.main(["config.py"])
    assert exit_code != 0
    assert "es.exe" in captured_stderr.getvalue()


def test_main_reports_empty_search_arguments() -> None:
    captured_stderr = io.StringIO()
    with patch.object(search.sys, "stderr", captured_stderr):
        exit_code = search.main([])
    assert exit_code == search.INVALID_INPUT_EXIT_CODE
    assert "search argument" in captured_stderr.getvalue()


@pytest.mark.parametrize("all_arguments", [["-n", "50"], [""], ["   "]])
def test_main_rejects_unscoped_search_without_launching_child(
    all_arguments: list[str],
) -> None:
    captured_stderr = io.StringIO()
    with (
        patch.object(search.subprocess, "run") as run_process,
        patch.object(search.sys, "stderr", captured_stderr),
    ):
        exit_code = search.main(all_arguments)
    assert exit_code == search.INVALID_INPUT_EXIT_CODE
    assert "first search argument" in captured_stderr.getvalue().lower()
    run_process.assert_not_called()


def test_main_allows_version_information_operation() -> None:
    completed_process = search.subprocess.CompletedProcess(
        args=["es.exe", "-version"], returncode=0, stdout="1.1.0.30\n", stderr=""
    )
    with (
        patch.object(search, "load_registry", return_value={}),
        patch.object(search.shutil, "which", return_value="es.exe"),
        patch.object(
            search.subprocess, "run", return_value=completed_process
        ) as run_process,
    ):
        exit_code = search.main(["-version"])
    assert exit_code == 0
    run_process.assert_called_once()
