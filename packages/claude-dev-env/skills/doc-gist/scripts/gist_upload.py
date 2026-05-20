"""Upload an HTML file as a secret GitHub gist and emit the htmlpreview URL.

Single-purpose transport. Takes HTML on stdin or via `--input <path>`, runs
`gh gist create` (secret by default), parses the gist URL from gh's output,
composes the htmlpreview.github.io preview URL, optionally opens it in the
default browser, and prints both URLs.

Designed to compose with anything that produces HTML — pipe in the output of
a script, the contents of a hand-authored file, or have the auto-publish
hook invoke it on a file Claude just wrote. The script does not opine on
HTML shape, structure, or styling.

Usage:
    gist_upload.py --input <path>
    gist_upload.py --input - --filename writeup.html < some.html
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path
from urllib.parse import quote

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)

from doc_gist_scripts_constants.gist_upload_constants import (  # noqa: E402
    GIST_DEFAULT_FILENAME,
    GIST_HOST_PREFIX,
    MINIMUM_GIST_URL_PARTS,
    PREVIEW_URL_TEMPLATE,
    UPLOAD_TIMEOUT_SECONDS,
)


def _read_html(input_argument: str) -> str:
    """Read HTML content from stdin (when input is '-') or a file path.

    Reads the full stdin stream when input_argument is '-'. Callers piping
    content through an external process should ensure bounded input.
    """
    if input_argument == "-":
        return sys.stdin.read()
    try:
        return Path(input_argument).expanduser().resolve().read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise SystemExit(f"Cannot read {input_argument}: {error}")


def _resolve_filename(input_argument: str, override: str | None) -> str:
    """Pick the filename gh will use for the gist file."""
    default_filename = GIST_DEFAULT_FILENAME
    if override:
        return Path(override).name
    if input_argument != "-":
        return Path(input_argument).name
    return default_filename


def _write_to_temp(html_text: str, filename: str, parent_directory: Path) -> Path:
    """Write HTML to a temp file inside parent_directory with the given filename."""
    target_path = parent_directory / filename
    target_path.write_text(html_text, encoding="utf-8")
    return target_path


def _create_secret_gist(html_path: Path, description: str) -> str:
    """Run `gh gist create` against html_path and return the gist URL."""
    try:
        completed = subprocess.run(
            ["gh", "gist", "create", str(html_path), "--desc", description],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=UPLOAD_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        raise SystemExit(
            "gh CLI not found. Install GitHub CLI (https://cli.github.com) and run `gh auth login`."
        )
    except subprocess.TimeoutExpired:
        raise SystemExit(
            f"gh gist create timed out after {UPLOAD_TIMEOUT_SECONDS}s. Check network and retry."
        )
    if completed.returncode != 0:
        message_text = completed.stderr.strip() or completed.stdout.strip()
        raise SystemExit(
            f"gh gist create failed:\n{message_text}\nRun `gh auth login` and retry."
        )
    output_lines = completed.stdout.strip().splitlines()
    if not output_lines:
        raise SystemExit("gh gist create produced no output.")
    last_line = output_lines[-1].strip()
    if not last_line.startswith(GIST_HOST_PREFIX):
        raise SystemExit(f"Unexpected gh gist create output: {last_line!r}")
    return last_line


def _compose_preview_url(gist_url: str, filename: str) -> str:
    """Build the htmlpreview.github.io URL from the gist URL and the gist filename."""
    minimum_parts = MINIMUM_GIST_URL_PARTS
    preview_template = PREVIEW_URL_TEMPLATE
    path_after_host = gist_url[len(GIST_HOST_PREFIX) :]
    parts = path_after_host.split("/")
    if len(parts) < minimum_parts:
        raise SystemExit(f"Cannot parse gist URL: {gist_url!r}")
    return preview_template.format(user=parts[0], gist_id=parts[1], filename=quote(filename, safe=""))


def _open_in_browser(url: str) -> None:
    """Open the URL in the default browser, deferring to OS-native behavior on Windows."""
    if sys.platform.startswith("win"):
        os.startfile(url)
        return
    webbrowser.open(url)


def main() -> int:
    """Entry point — read HTML, upload as secret gist, print URLs, open preview.

    Returns:
        Process exit code (0 on success).
    """
    parser = argparse.ArgumentParser(
        description="Upload HTML as a secret gist; print gist + htmlpreview URLs."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to an .html file, or '-' for stdin.",
    )
    parser.add_argument(
        "--filename",
        default=None,
        help="Filename inside the gist. Defaults to the input filename, or 'doc.html' for stdin.",
    )
    parser.add_argument(
        "--description",
        default="HTML artifact",
        help="Gist description.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Skip opening the preview URL in the default browser.",
    )
    arguments = parser.parse_args()

    html_text = _read_html(arguments.input)
    filename = _resolve_filename(arguments.input, arguments.filename)

    with tempfile.TemporaryDirectory(prefix="gist-upload-") as temp_directory:
        upload_path = _write_to_temp(html_text, filename, Path(temp_directory))
        gist_url = _create_secret_gist(upload_path, arguments.description)
        preview_url = _compose_preview_url(gist_url, filename)

    print(f"Gist: {gist_url}", file=sys.stderr)
    print(f"Preview: {preview_url}", file=sys.stderr)

    if not arguments.no_open:
        _open_in_browser(preview_url)
        print("Opened preview in default browser.", file=sys.stderr)

    print(preview_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
