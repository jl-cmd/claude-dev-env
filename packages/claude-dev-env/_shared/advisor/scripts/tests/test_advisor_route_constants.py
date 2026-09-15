import importlib
import sys
from pathlib import Path

import pytest

config_root = str(Path(__file__).parent.parent / "config")
if config_root not in sys.path:
    sys.path.insert(0, config_root)

advisor_route_constants = importlib.import_module(
    "advisor_scripts_constants.advisor_route_constants"
)


def test_installed_advisor_uses_the_owned_agents_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed_file = (
        tmp_path
        / ".claude"
        / "_shared"
        / "advisor"
        / "scripts"
        / "config"
        / "advisor_scripts_constants"
        / "advisor_route_constants.py"
    )
    monkeypatch.setattr(advisor_route_constants, "__file__", str(installed_file))
    assert advisor_route_constants._policy_path_candidates() == (
        tmp_path / ".agents" / "rules" / "subagent-model-policy.json",
    )


def test_profile_advisor_uses_its_matching_agents_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed_file = (
        tmp_path
        / "named-profile"
        / "_shared"
        / "advisor"
        / "scripts"
        / "config"
        / "advisor_scripts_constants"
        / "advisor_route_constants.py"
    )
    monkeypatch.setattr(advisor_route_constants, "__file__", str(installed_file))
    assert advisor_route_constants._policy_path_candidates() == (
        tmp_path / "named-profile.agents" / "rules" / "subagent-model-policy.json",
    )
