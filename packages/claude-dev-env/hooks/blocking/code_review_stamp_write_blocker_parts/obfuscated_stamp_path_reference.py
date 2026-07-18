"""Decide whether a command builds a stamp path with obfuscation and writes.

A path-obfuscation forge hides ``.claude`` or ``code-review-stamps`` inside hex
digits, a base64 token, a comma-separated character-code sequence, or a run of
``+``-joined ``chr(<int>)`` calls, then pairs the assembled path with a
non-redirect file write (``open(``, ``write_text``, ``Out-File``,
``Set-Content``, ``Add-Content``, ``tee``). The literal path matchers miss such
a path because it carries no plain ``code-review-stamps`` substring, so this
module decodes each embedded token and looks for a stamp-path segment either in
the decoded text or inside the write call's argument region. A bare ``>``
redirect to the stamp path is caught by the literal-path matchers, so a command
whose only write is a redirect is left alone here.

The entry hook registers the constant packages before importing this module, so
the ``from config...`` imports below resolve against the sibling ``config/``
package without a bootstrap call here.
"""

from __future__ import annotations

import base64
import binascii
import re

from config.code_review_enforcement_constants import (
    ALL_STAMP_PATH_SEGMENT_BODIES,
    ALL_STAMP_PATH_SEGMENT_NAMES,
)
from config.verified_commit_constants import (
    BASE64_TOKEN_PATTERN,
    CHARACTER_CODE_SEQUENCE_PATTERN,
    CHR_CALL_CHAIN_PATTERN,
    CHR_CALL_CODE_PATTERN,
    HEX_DIGITS_PER_BYTE,
    HEX_TOKEN_PATTERN,
    NON_REDIRECT_FILE_WRITE_PRIMITIVE_PATTERN,
    PATH_OBFUSCATION_PRIMITIVE_PATTERN,
    WRITE_CALL_REGION_PATTERN,
)

_ASCII_ENCODING = "ascii"


def _decode_hex_token(hex_token: str) -> str:
    """Decode a hex-digit token to text, returning empty text on failure.

    Args:
        hex_token: A run of hex digits taken from the command.

    Returns:
        The decoded ASCII text, or empty text when the token is odd-length,
        not valid hex, or not decodable as ASCII.
    """
    odd_hex_token_remainder = 1
    if len(hex_token) % HEX_DIGITS_PER_BYTE == odd_hex_token_remainder:
        return ""
    try:
        return bytes.fromhex(hex_token).decode(_ASCII_ENCODING)
    except (ValueError, binascii.Error):
        return ""


def _decode_base64_token(base64_token: str) -> str:
    """Decode a base64 token to text, returning empty text on failure.

    Args:
        base64_token: A base64-shaped token taken from the command.

    Returns:
        The decoded ASCII text, or empty text when the token is not valid
        base64 or not decodable as ASCII.
    """
    try:
        return base64.b64decode(base64_token, validate=True).decode(_ASCII_ENCODING)
    except (ValueError, binascii.Error):
        return ""


def _decode_character_code_sequence(code_sequence: str) -> str:
    """Decode a comma-separated character-code sequence to text.

    Args:
        code_sequence: A comma-separated run of decimal character codes, each
            within the three-digit range the source pattern admits.

    Returns:
        The decoded text.
    """
    character_code_separator = ","
    decoded_characters: list[str] = []
    for each_code in code_sequence.split(character_code_separator):
        code_point = int(each_code.strip())
        decoded_characters.append(chr(code_point))
    return "".join(decoded_characters)


def _decode_chr_call_chain(chr_chain: str) -> str:
    """Decode a run of ``+``-joined ``chr(<int>)`` calls to text.

    Args:
        chr_chain: A run of two or more ``+``-joined ``chr(<int>)`` calls taken
            from the command, each code within the three-digit source range.

    Returns:
        The decoded text.
    """
    decoded_characters: list[str] = []
    for each_code in re.findall(CHR_CALL_CODE_PATTERN, chr_chain, re.IGNORECASE):
        decoded_characters.append(chr(int(each_code)))
    return "".join(decoded_characters)


def _append_when_present(all_decoded_texts: list[str], decoded_text: str) -> None:
    """Append the lowercase decoded text when it is non-empty.

    Args:
        all_decoded_texts: The running list of decoded texts to extend.
        decoded_text: One token's decoded text, empty when the token failed.

    Returns:
        None. The list is extended in place when the text is non-empty.
    """
    if decoded_text:
        all_decoded_texts.append(decoded_text.lower())


def _decoded_texts_from_command(command_text: str) -> list[str]:
    """Decode every hex, base64, character-code, and chr-chain token a command embeds.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        The lowercase decoded text for every token that decodes cleanly;
        tokens that fail to decode or carry an out-of-range code are skipped.
    """
    all_decoded_texts: list[str] = []
    for each_hex_token in re.findall(HEX_TOKEN_PATTERN, command_text, re.IGNORECASE):
        _append_when_present(all_decoded_texts, _decode_hex_token(each_hex_token))
    for each_base64_token in re.findall(BASE64_TOKEN_PATTERN, command_text):
        _append_when_present(all_decoded_texts, _decode_base64_token(each_base64_token))
    for each_code_sequence in re.findall(CHARACTER_CODE_SEQUENCE_PATTERN, command_text):
        _append_when_present(all_decoded_texts, _decode_character_code_sequence(each_code_sequence))
    for each_chr_chain in re.findall(CHR_CALL_CHAIN_PATTERN, command_text, re.IGNORECASE):
        _append_when_present(all_decoded_texts, _decode_chr_call_chain(each_chr_chain))
    return all_decoded_texts


def _decoded_token_references_stamp_segment(command_text: str) -> bool:
    """Decide whether a decodable token in a command hides a stamp-path segment.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when a decodable token decodes to a stamp-path segment body
        (``claude`` or ``code-review-stamps``).
    """
    all_decoded_texts = _decoded_texts_from_command(command_text)
    return any(
        each_segment_body in each_decoded_text
        for each_decoded_text in all_decoded_texts
        for each_segment_body in ALL_STAMP_PATH_SEGMENT_BODIES
    )


def _write_call_region_names_stamp_segment(command_text: str) -> bool:
    """Decide whether a write call's argument region names a stamp-path segment.

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when a stamp-path segment name appears inside a non-redirect write
        call's argument region.
    """
    write_call_region_pattern = re.compile(WRITE_CALL_REGION_PATTERN, re.IGNORECASE)
    for each_region_match in write_call_region_pattern.finditer(command_text):
        lowercased_region = each_region_match.group(0).lower()
        if any(each_name in lowercased_region for each_name in ALL_STAMP_PATH_SEGMENT_NAMES):
            return True
    return False


def references_obfuscated_stamp_path(command_text: str) -> bool:
    """Decide whether a command pairs path obfuscation with a stamp-path write.

    ::

        python -c "open(bytes.fromhex('...code-review-stamps...'),'w')"  -> True
        open(bytes.fromhex('2f746d702f78'),'w')                          -> False

    Args:
        command_text: The raw command string from the tool payload.

    Returns:
        True when the command holds a path-obfuscation primitive, a
        non-redirect file write, and a stamp-path segment reachable by that
        write — either a decoded token anywhere in the command or a plain-text
        segment inside the write call's argument region.
    """
    has_obfuscation_primitive = (
        re.search(PATH_OBFUSCATION_PRIMITIVE_PATTERN, command_text) is not None
    )
    has_non_redirect_write = (
        re.search(NON_REDIRECT_FILE_WRITE_PRIMITIVE_PATTERN, command_text) is not None
    )
    if not (has_obfuscation_primitive and has_non_redirect_write):
        return False
    if _decoded_token_references_stamp_segment(command_text):
        return True
    return _write_call_region_names_stamp_segment(command_text)
