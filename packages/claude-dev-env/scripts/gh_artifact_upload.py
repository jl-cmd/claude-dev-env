#!/usr/bin/env python3
"""Upload a file to a repo's durable 'artifacts' release and print its URL.

A durable GitHub post (issue, PR, comment, review) must not link a file under a
job scratch directory or worktree, because that scratch is cleaned soon after
the run while the post lives forever. Binary artifacts belong in a permanent
place instead. This tool ensures the repo has a prerelease tagged ``artifacts``,
uploads the given file under a timestamped asset name, and prints the permanent
download URL a post can safely link. The timestamped name keeps each upload a
distinct asset. An upload never overwrites an earlier one. A same-name collision
fails loudly instead of replacing the bytes an existing URL already serves.

Usage::

    python3 gh_artifact_upload.py <file-path> <owner/repo>
    -> https://github.com/<owner>/<repo>/releases/download/artifacts/20260707_140233_contact_sheet.png
"""

from __future__ import annotations

import argparse
import datetime
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dev_env_scripts_constants.gh_artifact_upload_constants import (
    ARTIFACTS_RELEASE_NOTES,
    ARTIFACTS_RELEASE_TAG,
    ARTIFACTS_RELEASE_TITLE,
    ASSET_DOWNLOAD_URL_TEMPLATE,
    ASSET_NAME_TEMPLATE,
    ASSET_NAME_TIMESTAMP_FORMAT,
    GH_BINARY_NAME,
    NOTES_FILE_SUFFIX,
    UTF8_ENCODING,
)


class ArtifactUploadError(Exception):
    """Raised when creating the release or uploading the asset fails."""


def _run_gh(all_arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [GH_BINARY_NAME, *all_arguments],
        capture_output=True,
        text=True,
        encoding=UTF8_ENCODING,
        check=False,
    )


def artifacts_release_exists(repository: str) -> bool:
    """Return whether the durable artifacts release already exists in the repo.

    Args:
        repository: The ``owner/repo`` slug.

    Returns:
        True when ``gh release view`` finds the ``artifacts`` release.
    """
    completion = _run_gh(
        [
            "release",
            "view",
            ARTIFACTS_RELEASE_TAG,
            "--repo",
            repository,
            "--json",
            "tagName",
        ]
    )
    return completion.returncode == 0


def ensure_artifacts_release(repository: str) -> None:
    """Create the artifacts prerelease when the repo does not already have it.

    Args:
        repository: The ``owner/repo`` slug.

    Raises:
        ArtifactUploadError: When the release cannot be created.
    """
    if artifacts_release_exists(repository):
        return
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=NOTES_FILE_SUFFIX, delete=False, encoding=UTF8_ENCODING
    ) as notes_file:
        notes_file.write(ARTIFACTS_RELEASE_NOTES)
        notes_path = notes_file.name
    completion = _run_gh(
        [
            "release",
            "create",
            ARTIFACTS_RELEASE_TAG,
            "--repo",
            repository,
            "--prerelease",
            "--title",
            ARTIFACTS_RELEASE_TITLE,
            "--notes-file",
            notes_path,
        ]
    )
    Path(notes_path).unlink(missing_ok=True)
    if completion.returncode != 0:
        raise ArtifactUploadError(completion.stderr.strip())


def timestamped_asset_name(file_path: str) -> str:
    """Return ``YYYYMMDD_HHMMSS_<basename>`` for the given file path.

    Args:
        file_path: The source file to be uploaded.

    Returns:
        The asset name that prefixes the basename with the current timestamp.
    """
    current_timestamp = datetime.datetime.now().strftime(ASSET_NAME_TIMESTAMP_FORMAT)
    return ASSET_NAME_TEMPLATE.format(
        timestamp=current_timestamp, basename=Path(file_path).name
    )


def build_asset_url(repository: str, asset_name: str) -> str:
    """Return the permanent download URL for an uploaded asset.

    Args:
        repository: The ``owner/repo`` slug.
        asset_name: The uploaded asset's name.

    Returns:
        The stable release-download URL for the asset.
    """
    return ASSET_DOWNLOAD_URL_TEMPLATE.format(
        repo=repository, tag=ARTIFACTS_RELEASE_TAG, asset_name=asset_name
    )


def upload_artifact(file_path: str, repository: str) -> str:
    """Upload a file to the artifacts release and return its permanent URL.

    Args:
        file_path: The source file to upload.
        repository: The ``owner/repo`` slug.

    Returns:
        The permanent download URL for the uploaded asset.

    Raises:
        ArtifactUploadError: When the file is missing or the upload fails.
    """
    source_path = Path(file_path)
    if not source_path.is_file():
        raise ArtifactUploadError(f"file not found: {file_path}")
    ensure_artifacts_release(repository)
    asset_name = timestamped_asset_name(file_path)
    with tempfile.TemporaryDirectory() as staging_directory:
        staged_asset_path = Path(staging_directory) / asset_name
        shutil.copyfile(source_path, staged_asset_path)
        completion = _run_gh(
            [
                "release",
                "upload",
                ARTIFACTS_RELEASE_TAG,
                str(staged_asset_path),
                "--repo",
                repository,
            ]
        )
    if completion.returncode != 0:
        raise ArtifactUploadError(completion.stderr.strip())
    return build_asset_url(repository, asset_name)


def main() -> int:
    """Parse arguments, upload the file, and print the permanent asset URL.

    Returns:
        ``0`` when the upload succeeds, ``1`` when it fails.
    """
    parser = argparse.ArgumentParser(
        description="Upload a file to a repo's durable 'artifacts' release."
    )
    parser.add_argument("file_path", help="Path to the file to upload.")
    parser.add_argument(
        "repository", metavar="owner/repo", help="Target GitHub repository slug."
    )
    parsed_arguments = parser.parse_args()
    try:
        asset_url = upload_artifact(
            parsed_arguments.file_path, parsed_arguments.repository
        )
    except ArtifactUploadError as upload_error:
        print(f"gh-artifact-upload failed: {upload_error}", file=sys.stderr)
        return 1
    print(asset_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
