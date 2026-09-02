"""Tests for notify_ntfy — argument parsing, payload shape, and delivery."""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from copilot_finding_triage_constants.config.notify_ntfy_constants import (
    DEFAULT_PRIORITY_NAME,
    DEFAULT_SERVER_URL,
    SERVER_ENVIRONMENT_VARIABLE_NAME,
    TOPIC_ENVIRONMENT_VARIABLE_NAME,
)
from notify_ntfy import (
    build_request,
    main,
    parse_arguments,
    resolve_server,
    resolve_topic,
)


class TestParseArguments:
    def test_reads_the_required_arguments(self) -> None:
        parsed = parse_arguments(
            ["--title", "PR 743", "--message", "one concern", "--click-url", "u"]
        )
        assert parsed.title == "PR 743"
        assert parsed.message == "one concern"
        assert parsed.click_url == "u"

    def test_priority_defaults_to_high(self) -> None:
        parsed = parse_arguments(["--title", "t", "--message", "m", "--click-url", "u"])
        assert parsed.priority == DEFAULT_PRIORITY_NAME

    def test_rejects_an_unknown_priority(self) -> None:
        try:
            parse_arguments(
                [
                    "--title",
                    "t",
                    "--message",
                    "m",
                    "--click-url",
                    "u",
                    "--priority",
                    "x",
                ]
            )
        except SystemExit as exit_error:
            assert exit_error.code != 0
            return
        raise AssertionError("expected SystemExit for an unknown priority")


class TestResolveEnvironment:
    def test_topic_reads_from_the_environment(self) -> None:
        assert resolve_topic({TOPIC_ENVIRONMENT_VARIABLE_NAME: "converge-743"}) == (
            "converge-743"
        )

    def test_topic_is_empty_when_unset(self) -> None:
        assert resolve_topic({}) == ""

    def test_server_falls_back_to_the_default(self) -> None:
        assert resolve_server({}) == DEFAULT_SERVER_URL

    def test_server_override_wins(self) -> None:
        override = {SERVER_ENVIRONMENT_VARIABLE_NAME: "https://ntfy.example.com"}
        assert resolve_server(override) == "https://ntfy.example.com"


class TestBuildRequest:
    def test_builds_a_post_to_the_topic_endpoint(self) -> None:
        request = build_request(
            "PR 743", "body", "https://review", "high", "topic-a", DEFAULT_SERVER_URL
        )
        assert request.method == "POST"
        assert request.full_url == "https://ntfy.sh/topic-a"

    def test_carries_the_title_priority_and_click_headers(self) -> None:
        request = build_request(
            "PR 743", "body", "https://review", "urgent", "topic-a", DEFAULT_SERVER_URL
        )
        assert request.get_header("Title") == "PR 743"
        assert request.get_header("Priority") == "5"
        assert request.get_header("Click") == "https://review"

    def test_encodes_the_message_as_the_body(self) -> None:
        request = build_request(
            "t", "the body text", "u", "high", "topic-a", DEFAULT_SERVER_URL
        )
        assert request.data == b"the body text"


class _RecordingHandler(BaseHTTPRequestHandler):
    received_path: str = ""
    received_body: bytes = b""
    received_title: str = ""

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        _RecordingHandler.received_path = self.path
        _RecordingHandler.received_body = self.rfile.read(content_length)
        _RecordingHandler.received_title = self.headers.get("Title", "")
        self.send_response(200)
        self.end_headers()

    def log_message(self, format_string: str, *format_arguments: object) -> None:
        return None


class TestMainDelivers:
    def test_missing_topic_returns_one(self) -> None:
        exit_code = main(["--title", "t", "--message", "m", "--click-url", "u"], {})
        assert exit_code == 1

    def test_posts_the_notification_to_a_local_server(self) -> None:
        server = HTTPServer(("127.0.0.1", 0), _RecordingHandler)
        server_thread = threading.Thread(target=server.handle_request)
        server_thread.start()
        server_port = server.server_address[1]
        server_url = f"http://127.0.0.1:{server_port}"
        exit_code = main(
            [
                "--title",
                "PR 743",
                "--message",
                "one code concern",
                "--click-url",
                "https://review",
            ],
            {
                TOPIC_ENVIRONMENT_VARIABLE_NAME: "converge-743",
                SERVER_ENVIRONMENT_VARIABLE_NAME: server_url,
            },
        )
        server_thread.join(timeout=5)
        server.server_close()
        assert exit_code == 0
        assert _RecordingHandler.received_path == "/converge-743"
        assert _RecordingHandler.received_body == b"one code concern"
        assert _RecordingHandler.received_title == "PR 743"
