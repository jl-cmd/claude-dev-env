from review_router import load_route_policy, resolve_route


def test_load_route_policy_returns_versioned_policy() -> None:
    assert load_route_policy()["version"] == 1


def test_e_simplify_route_and_unsupported_e_code_review() -> None:
    assert resolve_route("e-simplify", "T1")["status"] == "SUPPORTED"
    assert resolve_route("e-code-review", "T1")["status"] == "UNSUPPORTED_ROUTE"


def test_route_has_only_current_dispatch_fields() -> None:
    route_result = resolve_route("e-simplify", "T1")
    assert route_result["dispatch"]["pass_ids"] == ["simplify-01"]
    assert "advisor" not in route_result
    assert "same_executor_redirect" not in route_result


def test_t3_has_six_ordered_slots() -> None:
    assert resolve_route("e-simplify", "T3")["dispatch"]["pass_ids"] == [
        "simplify-01", "simplify-02", "simplify-03", "simplify-04", "simplify-05", "simplify-06"
    ]
