"""Tests for the verdict-directory shell guard.

The verified-commit gate trusts that only the minter hook writes verdict
files. The Write/Edit/MultiEdit deny rules in settings.json stop the file
tools, but a shell command (``python -c``, a redirect, an Out-File) reaches
the same directory unless a Bash/PowerShell guard blocks it. These tests
exercise that guard: every shell spelling that targets the verdict directory
is denied, and commands that touch unrelated paths pass.
"""

import importlib.util
import json
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

guard_spec = importlib.util.spec_from_file_location(
    "verdict_directory_write_blocker",
    _HOOK_DIR / "verdict_directory_write_blocker.py",
)
assert guard_spec is not None
assert guard_spec.loader is not None
guard_module = importlib.util.module_from_spec(guard_spec)
guard_spec.loader.exec_module(guard_module)
references_verdict_directory = guard_module.references_verdict_directory
decision_for_payload = guard_module.decision_for_payload

constants_spec = importlib.util.spec_from_file_location(
    "verified_commit_constants",
    _HOOK_DIR / "config" / "verified_commit_constants.py",
)
assert constants_spec is not None
assert constants_spec.loader is not None
constants_module = importlib.util.module_from_spec(constants_spec)
constants_spec.loader.exec_module(constants_module)
ROOT_KEY_HEX_LENGTH = constants_module.ROOT_KEY_HEX_LENGTH


def test_python_write_text_into_verdict_directory_is_flagged() -> None:
    command_text = (
        'python -c "import pathlib; '
        "pathlib.Path.home().joinpath('.claude','verification','x.json')"
        ".write_text('{}')\""
    )
    assert references_verdict_directory(command_text) is True


def test_home_var_redirect_into_verdict_directory_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "echo forged > $HOME/.claude/verification/abc.json"
        )
        is True
    )


def test_tilde_redirect_into_verdict_directory_is_flagged() -> None:
    assert (
        references_verdict_directory("echo forged > ~/.claude/verification/abc.json")
        is True
    )


def test_powershell_out_file_into_verdict_directory_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "'{}' | Out-File $HOME/.claude/verification/abc.json"
        )
        is True
    )


def test_backslash_verdict_path_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "echo forged > C:\\Users\\jon\\.claude\\verification\\abc.json"
        )
        is True
    )


def test_unrelated_claude_path_is_not_flagged() -> None:
    assert (
        references_verdict_directory(
            "python $HOME/.claude/hooks/blocking/verified_commit_gate.py"
        )
        is False
    )


def test_plain_git_commit_is_not_flagged() -> None:
    assert references_verdict_directory("git commit -m x") is False


def test_cd_then_tilde_relative_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude && echo x > verification/a.json"
        )
        is True
    )


def test_cd_then_absolute_relative_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd /home/u/.claude && echo x > verification/a.json"
        )
        is True
    )


def test_cd_with_trailing_slash_then_relative_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude/ ; echo x > verification/x.json"
        )
        is True
    )


def test_pushd_then_relative_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "pushd $HOME/.claude; echo x > verification/abc.json"
        )
        is True
    )


def test_set_location_then_relative_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "Set-Location ~/.claude; 'x' | Out-File verification/abc.json"
        )
        is True
    )


def test_relative_verdict_filename_shape_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "echo forged > verification/0123456789abcdef.json"
        )
        is True
    )


def test_verdict_filename_of_root_key_length_is_flagged() -> None:
    root_key_length_name = "a" * ROOT_KEY_HEX_LENGTH
    assert (
        references_verdict_directory(
            f"echo forged > verification/{root_key_length_name}.json"
        )
        is True
    )


def test_verdict_filename_one_hex_short_of_root_key_length_is_not_flagged() -> None:
    too_short_name = "a" * (ROOT_KEY_HEX_LENGTH - 1)
    assert (
        references_verdict_directory(
            f"echo forged > verification/{too_short_name}.json"
        )
        is False
    )


def test_verdict_file_pattern_quantifier_tracks_root_key_length() -> None:
    expected_quantifier = "{" + str(ROOT_KEY_HEX_LENGTH) + "}"
    assert expected_quantifier in constants_module.VERDICT_FILE_RELATIVE_REFERENCE_PATTERN


def test_cd_into_verdict_directory_then_bare_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude/verification && echo x > 0123456789abcdef.json"
        )
        is True
    )


def test_pushd_into_verdict_directory_then_bare_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "pushd $HOME/.claude/verification; echo x > 0123456789abcdef.json"
        )
        is True
    )


def test_set_location_into_verdict_directory_then_bare_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "Set-Location ~/.claude/verification; 'x' | Out-File 0123456789abcdef.json"
        )
        is True
    )


def test_cd_into_verdict_directory_with_trailing_slash_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude/verification/ && echo x > 0123456789abcdef.json"
        )
        is True
    )


def test_set_location_path_option_into_verdict_directory_then_bare_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "Set-Location -Path ~/.claude/verification; "
            "echo forged > 0123456789abcdef.json"
        )
        is True
    )


def test_set_location_literal_path_option_into_verdict_directory_then_bare_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "Set-Location -LiteralPath ~/.claude/verification; "
            "echo forged > 0123456789abcdef.json"
        )
        is True
    )


def test_set_location_path_option_into_claude_home_then_relative_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "Set-Location -Path ~/.claude; 'x' | Out-File verification/abc.json"
        )
        is True
    )


def test_cd_double_dash_terminator_into_verdict_directory_then_bare_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd -- ~/.claude/verification && echo forged > 0123456789abcdef.json"
        )
        is True
    )


def test_set_location_path_option_into_unrelated_directory_then_write_is_not_flagged() -> None:
    assert (
        references_verdict_directory(
            "Set-Location -Path ~/.claude/hooks; echo x > note.txt"
        )
        is False
    )


def test_cd_into_verdict_directory_then_cp_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude/verification && cp /tmp/forged.json 0123456789abcdef.json"
        )
        is True
    )


def test_cd_into_verdict_directory_then_mv_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude/verification && mv /tmp/forged.json 0123456789abcdef.json"
        )
        is True
    )


def test_cd_into_verdict_directory_then_tee_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude/verification && echo '{}' | tee 0123456789abcdef.json"
        )
        is True
    )


def test_cd_into_verdict_directory_then_python_write_text_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude/verification && "
            "python -c \"import pathlib; "
            "pathlib.Path('0123456789abcdef.json').write_text('{}')\""
        )
        is True
    )


def test_cd_into_verdict_directory_then_install_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude/verification && install /tmp/forged.json 0123456789abcdef.json"
        )
        is True
    )


def test_cd_into_verdict_directory_ampersand_abutting_tee_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude/verification&& echo {} | tee 8a482d8ecd29493f.json"
        )
        is True
    )


def test_cd_into_verdict_directory_pipe_abutting_cp_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude/verification|cp /tmp/f.json 8a482d8ecd29493f.json"
        )
        is True
    )


def test_cd_into_claude_home_ampersand_abutting_relative_write_is_flagged() -> None:
    assert (
        references_verdict_directory("cd ~/.claude&& echo x > verification/a.json")
        is True
    )


def test_cd_into_claude_home_pipe_abutting_relative_write_is_flagged() -> None:
    assert (
        references_verdict_directory("cd ~/.claude|tee verification/a.json")
        is True
    )


def test_add_content_obfuscated_path_write_is_flagged() -> None:
    probe_command = (
        "$p = bytes.fromhex('2e636c61756465').decode() ; Add-Content $p '{}'"
    )
    assert references_verdict_directory(probe_command) is True


def test_char_cast_obfuscated_path_write_is_flagged() -> None:
    probe_command = (
        "$p = [char]46 + [char[]]@(99,108,97,117,100,101) ; Set-Content $p '{}'"
    )
    assert references_verdict_directory(probe_command) is True


def test_chr_built_path_write_is_flagged() -> None:
    probe_command = (
        "python -c \"import os; "
        "open(os.path.join(os.path.expanduser(chr(126)),chr(46)+'claude',"
        "'verification','a.json'),'w')\""
    )
    assert references_verdict_directory(probe_command) is True


def test_pure_chr_chain_verdict_path_forge_is_flagged() -> None:
    chr_chain = "+".join(
        f"chr({each_byte})"
        for each_byte in b"/.claude/verification/a"
    )
    probe_command = f"python -c \"open({chr_chain},chr(119)).write(chr(48))\""
    assert references_verdict_directory(probe_command) is True


def test_pure_chr_chain_verification_segment_forge_is_flagged() -> None:
    chr_chain = "+".join(f"chr({each_byte})" for each_byte in b"verification")
    probe_command = f"python -c \"open({chr_chain},'w')\""
    assert references_verdict_directory(probe_command) is True


def test_bytes_fromhex_path_write_is_flagged() -> None:
    probe_command = (
        "python -c \"import os; "
        "open(bytes.fromhex('2e636c61756465').decode(),'w')\""
    )
    assert references_verdict_directory(probe_command) is True


def test_base64_decoded_path_write_is_flagged() -> None:
    probe_command = (
        "python -c \"import base64; "
        "open(base64.b64decode('LmNsYXVkZQ==').decode(),'w')\""
    )
    assert references_verdict_directory(probe_command) is True


def test_int_list_bytes_path_write_is_flagged() -> None:
    claude_segment_codes = ",".join(str(each_byte) for each_byte in b".claude")
    probe_command = (
        f"python -c \"open(bytes([{claude_segment_codes}]).decode(),'w')\""
    )
    assert references_verdict_directory(probe_command) is True


def test_int_list_bytearray_path_write_is_flagged() -> None:
    verification_segment_codes = ",".join(
        str(each_byte) for each_byte in b"verification"
    )
    probe_command = (
        f"python -c \"open(bytearray([{verification_segment_codes}]).decode(),'w')\""
    )
    assert references_verdict_directory(probe_command) is True


def test_int_list_full_verdict_path_forge_is_flagged() -> None:
    verdict_path_codes = ",".join(
        str(each_byte)
        for each_byte in b"/home/u/.claude/verification/0123456789abcdef.json"
    )
    probe_command = (
        f'python3 -c "f=open(bytes([{verdict_path_codes}]).decode(),'
        "'w');f.write('{}')\""
    )
    assert references_verdict_directory(probe_command) is True


def test_int_list_bytes_to_unrelated_file_is_not_flagged() -> None:
    unrelated_segment_codes = ",".join(str(each_byte) for each_byte in b"ab")
    probe_command = (
        f"python -c \"open(bytes([{unrelated_segment_codes}]).decode(),'w')\""
    )
    assert references_verdict_directory(probe_command) is False


def test_chr_without_write_primitive_is_not_flagged() -> None:
    assert references_verdict_directory("python -c \"print(chr(126))\"") is False


def test_chr_write_to_unrelated_path_is_not_flagged() -> None:
    assert (
        references_verdict_directory('python -c "print(chr(65))" > /tmp/out.txt')
        is False
    )


def test_base64_decode_to_unrelated_file_is_not_flagged() -> None:
    assert (
        references_verdict_directory(
            'python -c "import base64,sys; '
            "open('decoded.bin','wb').write(base64.b64decode(sys.argv[1]))\""
        )
        is False
    )


def test_set_content_char_to_unrelated_file_is_not_flagged() -> None:
    assert references_verdict_directory("Set-Content out.txt ([char]65)") is False


def test_bytes_fromhex_to_unrelated_file_is_not_flagged() -> None:
    assert (
        references_verdict_directory(
            "python -c \"open(bytes.fromhex('6162').decode(),'w')\""
        )
        is False
    )


def test_obfuscated_write_to_unrelated_path_with_incidental_verification_word_is_not_flagged() -> None:
    assert (
        references_verdict_directory(
            "python -c \"open(chr(47)+chr(116)); print('verification done')\""
        )
        is False
    )


def test_obfuscated_write_with_decoded_segment_after_separator_stays_flagged() -> None:
    assert (
        references_verdict_directory(
            "python -c \"open(bytes.fromhex('2e636c61756465').decode(),'w'); "
            "print('saved')\""
        )
        is True
    )


def test_obfuscated_write_with_incidental_claude_word_after_separator_is_not_flagged() -> None:
    assert (
        references_verdict_directory(
            "python -c \"open(chr(47)+chr(116)); print('claude run complete')\""
        )
        is False
    )


def test_base64_encoded_verification_segment_obfuscated_write_is_flagged() -> None:
    probe_command = (
        "python -c \"import base64; "
        "open(base64.b64decode('dmVyaWZpY2F0aW9u').decode(),'w')\""
    )
    assert references_verdict_directory(probe_command) is True


def test_hex_encoded_verification_segment_obfuscated_write_is_flagged() -> None:
    probe_command = (
        "python -c \"open(bytes.fromhex('766572696669636174696f6e').decode(),'w')\""
    )
    assert references_verdict_directory(probe_command) is True


def test_split_cd_into_verdict_directory_then_bare_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude && cd verification && echo x > 0123456789abcdef.json"
        )
        is True
    )


def test_split_cd_into_unrelated_subdirectory_then_write_is_not_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude && cd hooks && echo x > note.txt"
        )
        is False
    )


def test_split_cd_into_verdict_directory_then_copy_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude && cd verification && cp /tmp/f.json out.json"
        )
        is True
    )


def test_split_cd_into_verdict_directory_then_move_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "cd ~/.claude && cd verification && mv /tmp/f.json out.json"
        )
        is True
    )


def test_split_cd_into_unrelated_subdirectory_then_copy_is_not_flagged() -> None:
    assert (
        references_verdict_directory("cd ~/.claude && cd hooks && cp a b") is False
    )


def test_concatenated_string_literal_verdict_path_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "python -c \"open(str(pathlib.Path.home())+'/.claude'+'/verification'"
            "+'/a.json','w')\""
        )
        is True
    )


def test_concatenated_absolute_verdict_path_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "python -c \"open('/home/u/.claude'+'/verification/a.json','w')\""
        )
        is True
    )


def test_shell_variable_home_then_verdict_path_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "p=~/.claude; echo x > $p/verification/a.json"
        )
        is True
    )


def test_shell_variable_verdict_directory_name_write_is_flagged() -> None:
    assert (
        references_verdict_directory(
            "VDIR=verification; cd ~/.claude && echo x > $VDIR/a.json"
        )
        is True
    )


def test_write_without_obfuscation_primitive_is_not_flagged() -> None:
    assert (
        references_verdict_directory("echo hello > /tmp/notes.txt")
        is False
    )


def test_unrelated_claude_path_with_no_obfuscation_stays_unflagged() -> None:
    assert (
        references_verdict_directory(
            "python $HOME/.claude/hooks/blocking/verified_commit_gate.py"
        )
        is False
    )


def test_cd_outside_claude_then_relative_write_is_not_flagged() -> None:
    assert (
        references_verdict_directory("cd /tmp/work && echo x > verification/a.json")
        is False
    )


def test_sibling_verification_directory_is_not_flagged() -> None:
    assert (
        references_verdict_directory("cat ~/.claude/verification-docs/readme.md")
        is False
    )


def test_commit_message_naming_verdict_path_is_not_flagged() -> None:
    assert (
        references_verdict_directory('git commit -m "fix .claude/verification gate"')
        is False
    )


def test_verdict_write_with_path_separator_stays_flagged() -> None:
    assert (
        references_verdict_directory("echo x > ~/.claude/verification/a.json")
        is True
    )


def test_benign_redirect_mentioning_both_words_in_message_is_not_flagged() -> None:
    assert (
        references_verdict_directory(
            'echo "note: updated .claude docs about the verification flow"'
            " > /tmp/notes.txt"
        )
        is False
    )


def test_benign_single_quoted_message_mentioning_both_words_is_not_flagged() -> None:
    assert (
        references_verdict_directory(
            "echo 'see .claude and verification notes' > /tmp/out.txt"
        )
        is False
    )


def test_commit_message_naming_verdict_path_with_redirect_is_not_flagged() -> None:
    assert (
        references_verdict_directory(
            'git commit -m "fix .claude/verification gate" > /tmp/commit.log'
        )
        is False
    )


def test_decision_for_bash_verdict_write_denies() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo x > ~/.claude/verification/a.json"},
    }
    decision = decision_for_payload(payload)
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_decision_for_powershell_verdict_write_denies() -> None:
    payload = {
        "tool_name": "PowerShell",
        "tool_input": {
            "command": "'x' | Set-Content $HOME/.claude/verification/a.json"
        },
    }
    decision = decision_for_payload(payload)
    assert decision is not None
    assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_decision_for_unrelated_bash_command_is_none() -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "git status"}}
    assert decision_for_payload(payload) is None


def test_decision_for_non_shell_tool_is_none() -> None:
    payload = {
        "tool_name": "Read",
        "tool_input": {"command": "echo x > ~/.claude/verification/a.json"},
    }
    assert decision_for_payload(payload) is None


def _hooks_manifest_path() -> pathlib.Path:
    return _HOOK_DIR.parent / "hooks.json"


def _pretooluse_commands_for_matcher(matcher_substring: str) -> list[str]:
    manifest_record = json.loads(_hooks_manifest_path().read_text(encoding="utf-8"))
    matching_commands: list[str] = []
    for each_group in manifest_record["hooks"]["PreToolUse"]:
        if matcher_substring not in each_group.get("matcher", ""):
            continue
        for each_hook in each_group.get("hooks", []):
            matching_commands.append(each_hook.get("command", ""))
    return matching_commands


def test_guard_is_registered_on_bash() -> None:
    assert any(
        "verdict_directory_write_blocker.py" in each_command
        for each_command in _pretooluse_commands_for_matcher("Bash")
    )


def test_guard_is_registered_on_powershell() -> None:
    assert any(
        "verdict_directory_write_blocker.py" in each_command
        for each_command in _pretooluse_commands_for_matcher("PowerShell")
    )
