"""Tests for post_audit_thread_constants.py extracted constant set."""

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_constants_module() -> ModuleType:
    module_path = (
        Path(__file__).parent.parent
        / "pr_loop_shared_constants"
        / "post_audit_thread_constants.py"
    )
    specification = importlib.util.spec_from_file_location(
        "pr_loop_shared_constants.post_audit_thread_constants", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


constants_module = _load_constants_module()


def test_http_request_content_type_is_application_json() -> None:
    assert constants_module.HTTP_REQUEST_CONTENT_TYPE == "application/json"


def test_http_method_post_constant_is_post() -> None:
    assert constants_module.HTTP_METHOD_POST == "POST"


def test_http_header_authorization_constant_is_authorization() -> None:
    assert constants_module.HTTP_HEADER_AUTHORIZATION == "Authorization"


def test_http_header_accept_constant_is_accept() -> None:
    assert constants_module.HTTP_HEADER_ACCEPT == "Accept"


def test_http_header_content_type_constant_is_content_type() -> None:
    assert constants_module.HTTP_HEADER_CONTENT_TYPE == "Content-Type"


def test_http_header_github_api_version_constant_is_x_github_api_version() -> None:
    assert constants_module.HTTP_HEADER_GITHUB_API_VERSION == "X-GitHub-Api-Version"


def test_http_header_user_agent_constant_is_user_agent() -> None:
    assert constants_module.HTTP_HEADER_USER_AGENT == "User-Agent"


def test_http_authorization_bearer_prefix_is_bearer_with_trailing_space() -> None:
    prefix = constants_module.HTTP_AUTHORIZATION_BEARER_PREFIX
    assert prefix == "Bearer "
    assert prefix.endswith(" ")


def test_http_request_timeout_seconds_is_positive_int() -> None:
    timeout_seconds = constants_module.HTTP_REQUEST_TIMEOUT_SECONDS
    assert isinstance(timeout_seconds, int)
    assert timeout_seconds > 0


def test_error_response_preview_chars_is_positive_int() -> None:
    preview_chars = constants_module.ERROR_RESPONSE_PREVIEW_CHARS
    assert isinstance(preview_chars, int)
    assert preview_chars > 0


def test_single_review_api_path_template_uses_pr_number_placeholder() -> None:
    template_text = constants_module.SINGLE_REVIEW_API_PATH_TEMPLATE
    assert "{owner}" in template_text
    assert "{repo}" in template_text
    assert "{pr_number}" in template_text
    assert "{review_id}" in template_text


def test_single_review_comments_api_path_template_uses_pr_number_placeholder() -> None:
    template_text = constants_module.SINGLE_REVIEW_COMMENTS_API_PATH_TEMPLATE
    assert "{owner}" in template_text
    assert "{repo}" in template_text
    assert "{pr_number}" in template_text
    assert "{review_id}" in template_text
    assert template_text.endswith("/comments")


def test_audit_body_skeleton_marker_tokens_present() -> None:
    open_marker = constants_module.AUDIT_BODY_SKELETON_OPEN_MARKER
    close_marker = constants_module.AUDIT_BODY_SKELETON_CLOSE_MARKER
    assert open_marker.startswith("<!--") and open_marker.endswith("-->")
    assert close_marker.startswith("<!--") and close_marker.endswith("-->")
    assert open_marker != close_marker


def test_template_path_resolves_to_existing_markdown_file() -> None:
    resolved_path = constants_module.template_path()
    assert resolved_path.is_file(), f"missing: {resolved_path}"
    assert resolved_path.suffix == ".md"


def test_template_contains_skeleton_markers() -> None:
    resolved_path = constants_module.template_path()
    template_text = resolved_path.read_text(encoding="utf-8")
    assert constants_module.AUDIT_BODY_SKELETON_OPEN_MARKER in template_text
    assert constants_module.AUDIT_BODY_SKELETON_CLOSE_MARKER in template_text


def test_live_test_fixture_names_are_not_exposed_from_production_config_module() -> None:
    forbidden_attribute_names = [
        "LIVE_TEST_OWNER",
        "LIVE_TEST_REPO",
        "LIVE_TEST_BRANCH_PREFIX",
        "LIVE_TEST_PR_TITLE",
        "LIVE_TEST_PR_BODY",
        "LIVE_TEST_BASE_BRANCH",
        "LIVE_TEST_FIXTURE_FILENAME",
        "LIVE_TEST_FIXTURE_CONTENT",
        "LIVE_TEST_FIXTURE_LINE_FOR_FINDING_ONE",
        "LIVE_TEST_FIXTURE_LINE_FOR_FINDING_TWO",
        "LIVE_TEST_FIXTURE_LINE_FOR_FINDING_THREE",
    ]
    for each_attribute_name in forbidden_attribute_names:
        assert not hasattr(constants_module, each_attribute_name), (
            f"production config module exposes test-only fixture "
            f"{each_attribute_name!r}; move it to test_post_audit_thread.py"
        )
