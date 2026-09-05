from review_tier import (
    build_decision,
    calculate_tier,
    canonical_json_hash,
    effective_tier,
    load_policy,
    policy_hash,
)


def test_public_policy_functions_return_behavior() -> None:
    tier_policy = load_policy()
    assert policy_hash(tier_policy)
    assert canonical_json_hash(tier_policy) == policy_hash(tier_policy)
    decision = build_decision({}, "base", "head", ".", "digest", requested_override="T1")
    assert decision["effective_tier"] == "T1"


def test_tier_boundaries_and_hard_trigger() -> None:
    assert calculate_tier({"packages": 0, "risk": 0}) == "T1"
    assert calculate_tier({"hard_triggers": ["security"]}) == "T3"


def test_all_axes_accept_zero_one_two_boundaries() -> None:
    axes = ("packages", "risk", "public_api", "dependencies")
    assert calculate_tier({axis: 0 for axis in axes}) == "T1"
    assert calculate_tier({axis: 1 for axis in axes}) == "T3"
    assert calculate_tier({axis: 2 for axis in axes}) == "T3"


def test_upward_and_approved_downward_override() -> None:
    assert effective_tier("T1", "T3") == "T3"
    assert effective_tier("T3", "T1") == "T1"
