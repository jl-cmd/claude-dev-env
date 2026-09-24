"""Decode a subprocess stream text payload captured in text or bytes mode."""

from __future__ import annotations


def decode_stream_text(
    stream_payload: str | bytes | None,
    *,
    encoding: str,
    errors: str,
) -> str:
    """Decode a captured subprocess stream text payload, whichever mode captured it.

    Args:
        stream_payload: The captured stream content, or None when nothing
            was captured.
        encoding: The text encoding to use when the payload is bytes.
        errors: The decode error handler to use when the payload is bytes.

    Returns:
        The decoded text, an empty string when stream_payload is None, or
        stream_payload unchanged when it is already text.
    """
    if stream_payload is None:
        return ""
    if isinstance(stream_payload, bytes):
        return stream_payload.decode(encoding, errors=errors)
    return stream_payload
