import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "validate-artifact.py"
HEADER = (
    '<svg width="100%" viewBox="0 0 680 120" role="img"><title>T</title><desc>D</desc>'
)


def check(artifact: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(artifact)], text=True, capture_output=True
    )


def write_svg(directory: Path, name: str, body: str) -> Path:
    artifact = directory / name
    artifact.write_text(body, encoding="utf-8")
    return artifact


def test_text_floor_reports_tiny_text_when_the_viewbox_is_unreadable(
    tmp_path: Path,
) -> None:
    artifact = write_svg(
        tmp_path,
        "no-viewbox.svg",
        '<svg role="img"><title>T</title><desc>D</desc><text font-size="4">tiny</text></svg>',
    )
    finished = check(artifact)
    assert "text below" in finished.stdout, finished.stdout + finished.stderr


def test_commented_out_connector_is_not_reported(tmp_path: Path) -> None:
    artifact = write_svg(
        tmp_path,
        "commented.svg",
        f'{HEADER}\n<!-- <line fill="red" marker-end="url(#a)"/> -->\n</svg>',
    )
    finished = check(artifact)
    assert finished.returncode == 0, finished.stdout + finished.stderr


def test_live_connector_after_a_comment_is_still_reported(tmp_path: Path) -> None:
    artifact = write_svg(
        tmp_path,
        "after-comment.svg",
        f"{HEADER}\n<!-- an explanatory note -->\n"
        '<defs><marker id="a" markerUnits="userSpaceOnUse"><path d="M2 1L8 5"/></marker></defs>\n'
        '<line x1="10" y1="10" x2="90" y2="10" fill="red" marker-end="url(#a)"/>\n</svg>',
    )
    finished = check(artifact)
    assert "connectors need fill=none" in finished.stdout, (
        finished.stdout + finished.stderr
    )


def test_connector_error_names_the_offending_tag(tmp_path: Path) -> None:
    artifact = write_svg(
        tmp_path,
        "named.svg",
        f"{HEADER}\n"
        '<defs><marker id="a" markerUnits="userSpaceOnUse"><path d="M2 1L8 5"/></marker></defs>\n'
        '<line x1="10" y1="10" x2="90" y2="10" fill="red" marker-end="url(#a)"/>\n</svg>',
    )
    finished = check(artifact)
    connector_error = [
        line for line in finished.stdout.splitlines() if "fill=none" in line
    ]
    assert connector_error and "line" in connector_error[0], (
        finished.stdout + finished.stderr
    )
