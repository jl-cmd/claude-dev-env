"""Content hashing for manifest entries."""

import hashlib


def sha256_bytes(content_bytes: bytes) -> str:
    return hashlib.sha256(content_bytes).hexdigest()
