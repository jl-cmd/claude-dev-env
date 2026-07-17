"""Regression tests for the verified-commit constants bootstrap.

These prove the shared constants module resolves to the sibling
``config/verified_commit_constants.py`` file even when a foreign ``config``
package sits ahead of ``blocking`` on ``sys.path``, and that a registration a
caller placed first is left untouched.
"""

import subprocess
from collections.abc import Callable

RunUnderConfigShadow = Callable[[str], subprocess.CompletedProcess[str]]


def test_register_binds_dotted_name_to_sibling_constants_file(
    run_under_config_shadow: RunUnderConfigShadow,
) -> None:
    completed_probe = run_under_config_shadow(
        "import verified_commit_config_bootstrap as bootstrap\n"
        "bootstrap.register_verified_commit_constants()\n"
        "import config.verified_commit_constants as loaded\n"
        "print(loaded.__file__)\n"
        "print(loaded.DETACHED_HEAD_LABEL)\n"
    )
    assert completed_probe.returncode == 0, completed_probe.stderr
    assert "IS_DECOY_CONFIG" not in completed_probe.stdout
    resolved_file_line, detached_head_line = completed_probe.stdout.splitlines()[:2]
    assert resolved_file_line.replace("\\", "/").endswith(
        "blocking/config/verified_commit_constants.py"
    )
    assert detached_head_line == "HEAD"


def test_register_binds_gate_output_constants_module(
    run_under_config_shadow: RunUnderConfigShadow,
) -> None:
    completed_probe = run_under_config_shadow(
        "import verified_commit_config_bootstrap as bootstrap\n"
        "bootstrap.register_verified_commit_constants()\n"
        "import config.verified_commit_gate_output_constants as loaded\n"
        "print(loaded.__file__)\n"
        "print(loaded.DENY_PERMISSION_DECISION)\n"
    )
    assert completed_probe.returncode == 0, completed_probe.stderr
    resolved_file_line, deny_decision_line = completed_probe.stdout.splitlines()[:2]
    assert resolved_file_line.replace("\\", "/").endswith(
        "blocking/config/verified_commit_gate_output_constants.py"
    )
    assert deny_decision_line == "deny"


def test_register_leaves_an_already_cached_module_untouched(
    run_under_config_shadow: RunUnderConfigShadow,
) -> None:
    completed_probe = run_under_config_shadow(
        "import sys\n"
        "import types\n"
        "sentinel = types.ModuleType('config.verified_commit_constants')\n"
        "sentinel.ORIGIN = 'caller-seeded'\n"
        "sys.modules['config.verified_commit_constants'] = sentinel\n"
        "import verified_commit_config_bootstrap as bootstrap\n"
        "bootstrap.register_verified_commit_constants()\n"
        "import config.verified_commit_constants as loaded\n"
        "print(getattr(loaded, 'ORIGIN', 'displaced'))\n"
    )
    assert completed_probe.returncode == 0, completed_probe.stderr
    assert completed_probe.stdout.strip().splitlines()[-1] == "caller-seeded"
