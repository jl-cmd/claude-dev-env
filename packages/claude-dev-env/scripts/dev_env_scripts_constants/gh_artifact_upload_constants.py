"""Constants for the gh_artifact_upload script.

Per the project's configuration conventions, script-level scalar constants
live in dev_env_scripts_constants alongside timing.py.
"""

ARTIFACTS_RELEASE_TAG: str = "artifacts"
"""Release tag that holds durable post artifacts."""

ARTIFACTS_RELEASE_TITLE: str = "Durable post artifacts"
"""Human-readable title for the artifacts release."""

ARTIFACTS_RELEASE_NOTES: str = (
    "Permanent storage for binary artifacts linked from GitHub issue and pull "
    "request posts. Job scratch directories are ephemeral and get cleaned soon "
    "after a run; assets uploaded to this prerelease persist so a durable post "
    "can link a stable URL."
)
"""Release body written when the artifacts release is first created."""

GH_BINARY_NAME: str = "gh"
"""The GitHub CLI executable name."""

ASSET_NAME_TIMESTAMP_FORMAT: str = "%Y%m%d_%H%M%S"
"""strftime format for the timestamp prefix on an uploaded asset name."""

ASSET_NAME_TEMPLATE: str = "{timestamp}_{basename}"
"""Template joining the timestamp prefix and the source file basename."""

RELEASE_ASSETS_JSON_KEY: str = "assets"
"""``gh release view --json`` field holding the release's asset list."""

ASSET_URL_JSON_KEY: str = "url"
"""Asset field carrying the browser download URL GitHub serves."""

ASSET_CREATED_AT_JSON_KEY: str = "createdAt"
"""Asset field carrying the ISO 8601 creation timestamp."""

NOTES_FILE_SUFFIX: str = ".md"
"""Suffix for the temporary release-notes file."""

UTF8_ENCODING: str = "utf-8"
"""Text encoding for subprocess output and temp files."""

PNG_SUFFIX: str = ".png"
"""Suffix of a file the upload shrinks with oxipng before it sends."""

OXIPNG_BINARY_NAME: str = "oxipng"
"""The oxipng executable name, looked up on PATH."""

ALL_OXIPNG_LOSSLESS_ARGUMENTS: tuple[str, ...] = (
    "--opt",
    "4",
    "--strip",
    "none",
    "--quiet",
)
"""Oxipng options: a slow lossless search that keeps every PNG chunk."""

OXIPNG_MISSING_MESSAGE: str = (
    "oxipng is not on PATH. Install the release binary from "
    "https://github.com/oxipng/oxipng/releases, then upload again."
)
"""Failure text when a PNG upload finds no oxipng to shrink it first."""

SIZE_REPORT_TEMPLATE: str = "{name}: {original_size} -> {optimized_size} bytes"
"""Line naming an upload and its size before and after oxipng."""
