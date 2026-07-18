"""Regression tests for the code-review enforcement constants bootstrap.

These prove the shared constants module resolves to the sibling
``config/code_review_enforcement_constants.py`` file even when a foreign
``config`` package sits ahead of ``blocking`` on ``sys.path``, and that a
registration a caller placed first is left untouched.
"""

import subprocess
from collections.abc import Callable

RunUnderConfigShadow = Callable[[str], subprocess.CompletedProcess[str]]


def test_register_binds_dotted_name_to_sibling_constants_file(
    run_under_config_shadow: RunUnderConfigShadow,
) -> None:
    completed_probe = run_under_config_shadow(
        "import code_review_enforcement_config_bootstrap as bootstrap\n"
        "bootstrap.register_code_review_enforcement_constants()\n"
        "import config.code_review_enforcement_constants as loaded\n"
        "print(loaded.__file__)\n"
        "print(loaded.STAMP_DIRECTORY_NAME)\n"
    )
    assert completed_probe.returncode == 0, completed_probe.stderr
    assert "IS_DECOY_CONFIG" not in completed_probe.stdout
    resolved_file_line, stamp_directory_line = completed_probe.stdout.splitlines()[:2]
    assert resolved_file_line.replace("\\", "/").endswith(
        "blocking/config/code_review_enforcement_constants.py"
    )
    assert stamp_directory_line == "code-review-stamps"


def test_register_binds_push_required_effort(
    run_under_config_shadow: RunUnderConfigShadow,
) -> None:
    completed_probe = run_under_config_shadow(
        "import code_review_enforcement_config_bootstrap as bootstrap\n"
        "bootstrap.register_code_review_enforcement_constants()\n"
        "import config.code_review_enforcement_constants as loaded\n"
        "print(loaded.PUSH_REQUIRED_EFFORT)\n"
    )
    assert completed_probe.returncode == 0, completed_probe.stderr
    assert completed_probe.stdout.strip().splitlines()[-1] == "low"


def test_register_leaves_an_already_cached_module_untouched(
    run_under_config_shadow: RunUnderConfigShadow,
) -> None:
    completed_probe = run_under_config_shadow(
        "import sys\n"
        "import types\n"
        "sentinel = types.ModuleType('config.code_review_enforcement_constants')\n"
        "sentinel.ORIGIN = 'caller-seeded'\n"
        "sys.modules['config.code_review_enforcement_constants'] = sentinel\n"
        "import code_review_enforcement_config_bootstrap as bootstrap\n"
        "bootstrap.register_code_review_enforcement_constants()\n"
        "import config.code_review_enforcement_constants as loaded\n"
        "print(getattr(loaded, 'ORIGIN', 'displaced'))\n"
    )
    assert completed_probe.returncode == 0, completed_probe.stderr
    assert completed_probe.stdout.strip().splitlines()[-1] == "caller-seeded"
