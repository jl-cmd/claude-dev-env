import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]

def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True)


def test_package() -> None:
    finished = run("scripts/validate-package.py")
    assert finished.returncode == 0, finished.stdout + finished.stderr


def test_template_svg() -> None:
    finished = run("scripts/validate-artifact.py", "templates/svg-base.svg")
    assert finished.returncode == 0, finished.stdout + finished.stderr


def test_valid_html_passes() -> None:
    finished = run("scripts/validate-artifact.py", "tests/fixtures/valid.html")
    assert finished.returncode == 0, finished.stdout + finished.stderr


def test_invalid_fixture_fails() -> None:
    finished = run("scripts/validate-artifact.py", "tests/fixtures/invalid.svg")
    assert finished.returncode != 0, finished.stdout + finished.stderr


def test_css_variable_fixture_fails() -> None:
    finished = run("scripts/validate-artifact.py", "tests/fixtures/css-var.svg")
    assert finished.returncode != 0, finished.stdout + finished.stderr


def test_dead_reference_fixture_fails() -> None:
    finished = run("scripts/validate-artifact.py", "tests/fixtures/dead-ref.svg")
    assert finished.returncode != 0, finished.stdout + finished.stderr


def test_large_canvas_fixture_passes() -> None:
    finished = run("scripts/validate-artifact.py", "tests/fixtures/large-canvas.svg")
    assert finished.returncode == 0, finished.stdout + finished.stderr


def test_connector_inheriting_group_fill_passes() -> None:
    finished = run("scripts/validate-artifact.py", "tests/fixtures/inherited-fill.svg")
    assert finished.returncode == 0, finished.stdout + finished.stderr


def test_filled_glyph_without_markers_passes() -> None:
    finished = run("scripts/validate-artifact.py", "tests/fixtures/filled-glyph.svg")
    assert finished.returncode == 0, finished.stdout + finished.stderr


def test_connector_with_solid_fill_fails() -> None:
    finished = run("scripts/validate-artifact.py", "tests/fixtures/unfilled-connector.svg")
    assert finished.returncode != 0, finished.stdout + finished.stderr
    assert "connectors need fill=none" in finished.stdout
