"""Constants for the gist_upload utility.

GIST_HOST_PREFIX: anchor for parsing gh's emitted gist URL into user + id.
PREVIEW_URL_TEMPLATE: the htmlpreview.github.io shape that renders a raw gist file.
GIST_DEFAULT_FILENAME: filename used when input is stdin (no filename to inherit).
MINIMUM_GIST_URL_PARTS: gh's gist URL is /<user>/<id>; need at least these many segments.
"""

GIST_HOST_PREFIX = "https://gist.github.com/"
PREVIEW_URL_TEMPLATE = (
    "https://htmlpreview.github.io/?https://gist.githubusercontent.com/"
    "{user}/{gist_id}/raw/{filename}"
)
GIST_DEFAULT_FILENAME = "doc.html"
MINIMUM_GIST_URL_PARTS = 2
UPLOAD_TIMEOUT_SECONDS = 45
