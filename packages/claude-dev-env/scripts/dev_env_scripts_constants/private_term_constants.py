"""Digests of the private organization names this public repository never names.

The names stay out of the tree. Each entry holds the SHA-256 digest of one
name after normalization, which keeps only ASCII letters and digits in lower
case::

    "Acme-Widgets, Inc."          -> "acmewidgetsinc"
    "pat@acmewidgets.example.com" -> "patacmewidgetsexamplecom"

A scan hashes every window of the normalized text whose length matches an
entry, so any case, spacing, or punctuation of a name matches. To add a name,
append the digest of its normalized form and its length.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrivateTermDigest:
    """The length and SHA-256 hex digest of one normalized private name."""

    length: int
    sha256: str


ALL_PRIVATE_TERM_DIGESTS: frozenset[PrivateTermDigest] = frozenset(
    {
        PrivateTermDigest(
            length=10,
            sha256="c2a70b3186691a74dece4ca824bec178bfaec83be119be28faedd14aa392233f",
        ),
    }
)
PRIVATE_TERM_TEXT_ENCODING = "utf-8"
PRIVATE_TERM_FINDING_CODE = "private-term"
PRIVATE_TERM_MESSAGE_TEMPLATE = (
    "Line {line_number} names a private organization. "
    "Describe it in general terms and drop any link to it."
)
ALL_EVENT_TEXT_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("pull_request", "title", "pull request title"),
    ("pull_request", "body", "pull request body"),
    ("issue", "title", "issue title"),
    ("issue", "body", "issue body"),
    ("comment", "body", "comment body"),
    ("review", "body", "review body"),
    ("release", "name", "release name"),
    ("release", "body", "release body"),
)
FINDING_LINE_TEMPLATE = "{label}: {message}"
COMMIT_LABEL_TEMPLATE = "commit {short_sha} {part}"
COMMIT_IDENTITY_PART = "identity"
COMMIT_MESSAGE_PART = "message"
SHORT_SHA_LENGTH = 12
COMMIT_FIELD_SEPARATOR = "\x1f"
COMMIT_RECORD_SEPARATOR = "\x1e"
COMMIT_FIELD_SPLIT_LIMIT = 2
COMMIT_LOG_FORMAT = "--format=%H%x1f%an <%ae> %cn <%ce>%x1f%B%x1e"
