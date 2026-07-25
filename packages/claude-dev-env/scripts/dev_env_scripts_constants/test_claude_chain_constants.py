"""Behavioral tests for the claude fallback-chain constants module.

These drive the exported guidance template and the codec-keyword helper the
chain runner and its subprocess wrappers consume.
"""

from __future__ import annotations

from dev_env_scripts_constants import claude_chain_constants as chain_constants

_A_CONFIG_PATH = "/home/pilot/.claude/claude-chain.json"
_A_TIMEOUT_KEYWORD = "timeout"
_A_TIMEOUT_VALUE = 30


def test_missing_config_without_fallback_message_names_every_input() -> None:
    guidance = chain_constants.CONFIG_MISSING_NO_FALLBACK_MESSAGE_TEMPLATE.format(
        config_path=_A_CONFIG_PATH,
        fallback_command=chain_constants.FALLBACK_CHAIN_COMMAND,
        example_filename=chain_constants.EXAMPLE_CONFIG_FILENAME,
    )
    assert _A_CONFIG_PATH in guidance
    assert chain_constants.FALLBACK_CHAIN_COMMAND in guidance
    assert chain_constants.EXAMPLE_CONFIG_FILENAME in guidance


def test_collect_forwarded_text_codec_keeps_only_codec_keywords() -> None:
    all_forwarded = chain_constants.collect_forwarded_text_codec(
        {
            chain_constants.SUBPROCESS_ENCODING_KEYWORD: (
                chain_constants.UTF8_ENCODING
            ),
            _A_TIMEOUT_KEYWORD: _A_TIMEOUT_VALUE,
        }
    )
    assert all_forwarded == {
        chain_constants.SUBPROCESS_ENCODING_KEYWORD: chain_constants.UTF8_ENCODING
    }
