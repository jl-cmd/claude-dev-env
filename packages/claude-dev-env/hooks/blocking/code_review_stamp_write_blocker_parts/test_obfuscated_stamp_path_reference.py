"""Behavioral tests for the obfuscated-stamp-path matcher.

The matcher blocks a command that assembles a stamp path from hex, base64, or
``chr(<int>)`` codes and pairs it with a non-redirect file write, while a
decode-to-other-path one-liner passes.
"""

from __future__ import annotations

from code_review_stamp_write_blocker_parts.obfuscated_stamp_path_reference import (
    references_obfuscated_stamp_path,
)

STAMP_PATH_TEXT = "/.claude/code-review-stamps/a.json"
BENIGN_PATH_TEXT = "/tmp/x"


def _hex_forge_command(path_text: str) -> str:
    return f"python -c \"open(bytes.fromhex('{path_text.encode().hex()}'),'w').write('x')\""


def _chr_chain_forge_command(path_text: str) -> str:
    chr_chain = "+".join(f"chr({ord(each_character)})" for each_character in path_text)
    return f"python -c \"open({chr_chain},'w').write('x')\""


def _character_code_forge_command(path_text: str) -> str:
    comma_separated_codes = ",".join(str(ord(each_character)) for each_character in path_text)
    return f"python -c \"open(bytes([{comma_separated_codes}]),'w').write('x')\""


def test_hex_assembled_stamp_path_write_is_blocked() -> None:
    assert references_obfuscated_stamp_path(_hex_forge_command(STAMP_PATH_TEXT))


def test_character_code_assembled_stamp_path_write_is_blocked() -> None:
    assert references_obfuscated_stamp_path(_character_code_forge_command(STAMP_PATH_TEXT))


def test_chr_chain_assembled_stamp_path_write_is_blocked() -> None:
    assert references_obfuscated_stamp_path(_chr_chain_forge_command(STAMP_PATH_TEXT))


def test_decode_to_other_path_write_is_not_blocked() -> None:
    assert not references_obfuscated_stamp_path(_hex_forge_command(BENIGN_PATH_TEXT))


def test_redirect_only_stamp_reference_is_left_to_literal_matchers() -> None:
    assert not references_obfuscated_stamp_path("echo x > ~/.claude/code-review-stamps/a.json")
