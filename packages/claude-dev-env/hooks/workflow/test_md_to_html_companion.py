"""Tests for md_to_html_companion hook.

This test suite validates that the md-to-html companion hook correctly
generates HTML from markdown input, handles edge cases, and produces
valid HTML output.

Sandbox parent is created lazily by a session-scoped fixture rather than at
module import time, so test collection has no side effect on the filesystem.
The sandbox is rooted in a per-session unique directory created via
`tempfile.mkdtemp` so the OS-temp exemption (which the companion shares with
the blocker) does not silently skip the hook during tests.
"""

import functools
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "md_to_html_companion.py")


def _strip_read_only_and_retry(removal_function, target_path, *_exc_info):
    try:
        os.chmod(target_path, stat.S_IWRITE)
        removal_function(target_path)
    except OSError:
        pass


def _force_rmtree(target_path: str) -> None:
    handler_kw = (
        {"onexc": _strip_read_only_and_retry}
        if sys.version_info >= (3, 12)
        else {"onerror": _strip_read_only_and_retry}
    )
    try:
        shutil.rmtree(target_path, **handler_kw)
    except OSError:
        pass


@functools.lru_cache(maxsize=1)
def _get_sandbox_parent_directory() -> str:
    return tempfile.mkdtemp(prefix="pytest_md_companion_", dir=str(Path.home()))


@pytest.fixture(scope="session", autouse=True)
def _cleanup_sandbox_parent_directory():
    yield
    if _get_sandbox_parent_directory.cache_info().currsize:
        _force_rmtree(_get_sandbox_parent_directory())
        _get_sandbox_parent_directory.cache_clear()


def _make_sandbox() -> tempfile.TemporaryDirectory:
    """Return a TemporaryDirectory rooted outside the OS temp directory.

    The companion exempts the OS temp directory (mirroring the blocker), so
    the default `tempfile.TemporaryDirectory()` would prevent the test hook
    invocation generating any HTML sidecar at all.
    """
    return tempfile.TemporaryDirectory(dir=_get_sandbox_parent_directory())


class _RunHook:
    def __call__(self, tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        return subprocess.run(
            [sys.executable, HOOK_SCRIPT_PATH],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )


_run_hook = _RunHook()


def test_generates_html_companion():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        html_path = os.path.join(tmp, "guide.html")


        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Hello\n\nThis is a test.")

        result = _run_hook(
            "Write", {"file_path": md_path, "content": "# Hello\n\nThis is a test."}
        )
        assert result.returncode == 0
        assert os.path.exists(html_path)


def test_html_contains_heading():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Hello World")

        _run_hook("Write", {"file_path": md_path, "content": "# Hello World"})
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "<h1>" in html
        assert "Hello World" in html


def test_html_wraps_in_template():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("plain text")

        _run_hook("Write", {"file_path": md_path, "content": "plain text"})
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "<!DOCTYPE html>" in html
        assert "<style>" in html


def test_skips_non_md_files():
    with _make_sandbox() as tmp:
        py_path = os.path.join(tmp, "main.py")
        html_path = os.path.join(tmp, "main.html")


        with open(py_path, "w", encoding="utf-8") as f:
            f.write("x = 1")

        result = _run_hook("Write", {"file_path": py_path, "content": "x = 1"})
        assert result.returncode == 0
        assert not os.path.exists(html_path)


def test_skips_claude_dir():
    with _make_sandbox() as tmp:
        claude_dir = os.path.join(tmp, ".claude")
        md_path = os.path.join(claude_dir, "CLAUDE.md")
        html_path = os.path.join(claude_dir, "CLAUDE.html")

        os.makedirs(claude_dir, exist_ok=True)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# CLAUDE.md")

        result = _run_hook("Write", {"file_path": md_path, "content": "# CLAUDE.md"})
        assert result.returncode == 0
        assert not os.path.exists(html_path)


def test_unknown_tool_passes():
    result = _run_hook("Grep", {"pattern": "foo"})
    assert result.returncode == 0
    assert result.stdout == ""


def test_empty_file_path_passes():
    result = _run_hook("Write", {"file_path": "", "content": "# Hello"})
    assert result.returncode == 0
    assert result.stdout == ""


def test_nonexistent_md_passes():
    result = _run_hook(
        "Write",
        {"file_path": "/nonexistent/path/guide.md", "content": "# Hello"},
    )
    assert result.returncode == 0


def test_converts_code_fence():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("```python\nprint('hi')\n```")

        _run_hook(
            "Write", {"file_path": md_path, "content": "```python\nprint('hi')\n```"}
        )
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "<pre>" in html
        assert "<code" in html
        assert "print(&#x27;hi&#x27;)" in html


def test_converts_bold():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("This is **bold** text.")

        _run_hook("Write", {"file_path": md_path, "content": "This is **bold** text."})
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "<strong>bold</strong>" in html


def test_escapes_html_special_chars():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("Use <div> for layout & choose \"text\" for quotes.")

        _run_hook(
            "Write",
            {
                "file_path": md_path,
                "content": "Use <div> for layout & choose \"text\" for quotes.",
            },
        )
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "&lt;div&gt;" in html
        assert "&amp;" in html
        assert "<div>" not in html


def test_escapes_code_block_content():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("```\nif x < 5 and y > 3:\n    print('hello')\n```")

        _run_hook(
            "Write",
            {
                "file_path": md_path,
                "content": "```\nif x < 5 and y > 3:\n    print('hello')\n```",
            },
        )
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "&lt;" in html
        assert "if x" in html


def test_lists_are_wrapped_in_ul():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("- item one\n- item two\n- item three")

        _run_hook(
            "Write",
            {
                "file_path": md_path,
                "content": "- item one\n- item two\n- item three",
            },
        )
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "<ul>" in html
        assert "</ul>" in html
        assert html.index("<ul>") < html.index("<li>item one</li>")
        assert html.index("</li>") < html.index("</ul>")


def test_ordered_lists_are_wrapped_in_ol():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("1. first\n2. second")

        _run_hook(
            "Write",
            {"file_path": md_path, "content": "1. first\n2. second"},
        )
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "<ol>" in html
        assert "</ol>" in html


def test_handles_curly_braces_in_body():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# JS Example\n\nUse `{ foo: 1 }` in code.")

        _run_hook(
            "Write",
            {
                "file_path": md_path,
                "content": "# JS Example\n\nUse `{ foo: 1 }` in code.",
            },
        )
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "{ foo: 1 }" in html
        assert "{{" not in html
        assert "JS Example" in html


def test_escapes_title_in_html_output():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Hackers <3 Markdown & <scripts>")

        _run_hook(
            "Write",
            {
                "file_path": md_path,
                "content": "# Hackers <3 Markdown & <scripts>",
            },
        )
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "<title>Hackers &lt;3 Markdown &amp; &lt;scripts&gt;</title>" in html
        assert "<script>" not in html


def test_skips_root_readme():
    with _make_sandbox() as tmp:
        Path(tmp, ".git").touch()
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp)
            for each_name in ("README.md", "readme.md"):
                with open(each_name, "w", encoding="utf-8") as f:
                    f.write("# Test")
                result = _run_hook(
                    "Write", {"file_path": each_name, "content": "# Test"}
                )
                assert result.returncode == 0
                expected_html = each_name.replace(".md", ".html")
                assert not os.path.exists(expected_html)
        finally:
            os.chdir(original_cwd)


def test_skips_root_changelog():
    with _make_sandbox() as tmp:
        Path(tmp, ".git").touch()
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp)
            for each_name in ("CHANGELOG.md", "changelog.md"):
                with open(each_name, "w", encoding="utf-8") as f:
                    f.write("# Test")
                result = _run_hook(
                    "Write", {"file_path": each_name, "content": "# Test"}
                )
                assert result.returncode == 0
                expected_html = each_name.replace(".md", ".html")
                assert not os.path.exists(expected_html)
        finally:
            os.chdir(original_cwd)


def test_language_class_valid():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("```python\nx = 1\n```")

        _run_hook("Write", {"file_path": md_path, "content": "```python\nx = 1\n```"})
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert 'class="language-python"' in html


def test_language_class_skips_invalid():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("```my lang\nx = 1\n```")

        _run_hook("Write", {"file_path": md_path, "content": "```my lang\nx = 1\n```"})
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "<pre><code>" in html
        assert 'class="language-' not in html


def test_language_class_allows_valid_chars():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("```c++\nint x = 1;\n```")

        _run_hook("Write", {"file_path": md_path, "content": "```c++\nint x = 1;\n```"})
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert 'class="language-c++"' in html


def test_link_text_asterisks_remain_literal():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("See [text *not italic*](url).")

        _run_hook(
            "Write",
            {"file_path": md_path, "content": "See [text *not italic*](url)."},
        )
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert '<a href="url">text *not italic*</a>' in html
        assert "<em>" not in html


def test_handles_parentheses_in_links():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(
                "See [Python]"
                "(https://en.wikipedia.org/wiki/Python_(programming_language))."
            )

        _run_hook(
            "Write",
            {
                "file_path": md_path,
                "content": "See [Python]"
                "(https://en.wikipedia.org/wiki/Python_(programming_language)).",
            },
        )
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert (
            'href="https://en.wikipedia.org/wiki/Python_(programming_language)"'
            in html
        )


def test_does_not_skip_nested_readme():
    with _make_sandbox() as tmp:
        nested_dir = os.path.join(tmp, "docs")
        os.makedirs(nested_dir)
        md_path = os.path.join(nested_dir, "README.md")
        html_path = os.path.join(nested_dir, "README.html")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Nested README")

        result = _run_hook(
            "Write",
            {"file_path": md_path, "content": "# Nested README"},
        )
        assert result.returncode == 0
        assert os.path.exists(html_path)


def test_inline_code_preserves_asterisks():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("Type `**bold**` in a docstring.")

        _run_hook(
            "Write",
            {
                "file_path": md_path,
                "content": "Type `**bold**` in a docstring.",
            },
        )
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "<code>**bold**</code>" in html
        assert "<strong>" not in html


def test_blocks_javascript_url_scheme():
    with _make_sandbox() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("[click me](javascript:alert(1))")

        _run_hook(
            "Write",
            {
                "file_path": md_path,
                "content": "[click me](javascript:alert(1))",
            },
        )
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "javascript:" not in html
        assert "click me" in html
        assert "<a" not in html


def test_companion_skips_home_session_log_directory(tmp_path, monkeypatch):
    synthetic_home_directory = tmp_path / "synthetic_home"
    synthetic_home_directory.mkdir()
    monkeypatch.setenv("HOME", str(synthetic_home_directory))
    monkeypatch.setenv("USERPROFILE", str(synthetic_home_directory))
    session_log_directory = synthetic_home_directory / "SessionLog" / "decisions"
    session_log_directory.mkdir(parents=True)
    md_path = str(session_log_directory / "companion_exempt_test.md")
    html_path = str(session_log_directory / "companion_exempt_test.html")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Note")
    result = _run_hook(
        "Write",
        {"file_path": md_path, "content": "# Note"},
    )
    assert result.returncode == 0
    assert not os.path.exists(html_path)


def test_companion_skips_skill_md_anywhere():
    with _make_sandbox() as tmp:
        nested_directory = os.path.join(tmp, "packages", "dev-env", "skills", "foo")
        os.makedirs(nested_directory, exist_ok=True)
        md_path = os.path.join(nested_directory, "SKILL.md")
        html_path = os.path.join(nested_directory, "SKILL.html")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Skill")
        result = _run_hook(
            "Write",
            {"file_path": md_path, "content": "# Skill"},
        )
        assert result.returncode == 0
        assert not os.path.exists(html_path)


def test_companion_skips_agents_directory_anywhere():
    with _make_sandbox() as tmp:
        agents_directory = os.path.join(tmp, "packages", "dev-env", "agents")
        os.makedirs(agents_directory, exist_ok=True)
        md_path = os.path.join(agents_directory, "pr-description-writer.md")
        html_path = os.path.join(
            agents_directory, "pr-description-writer.html"
        )
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Agent")
        result = _run_hook(
            "Write",
            {"file_path": md_path, "content": "# Agent"},
        )
        assert result.returncode == 0
        assert not os.path.exists(html_path)


def test_companion_skips_claude_plugin_directory():
    with _make_sandbox() as tmp:
        plugin_directory = os.path.join(tmp, ".claude-plugin")
        os.makedirs(plugin_directory, exist_ok=True)
        md_path = os.path.join(plugin_directory, "manifest.md")
        html_path = os.path.join(plugin_directory, "manifest.html")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Manifest")
        result = _run_hook(
            "Write",
            {"file_path": md_path, "content": "# Manifest"},
        )
        assert result.returncode == 0
        assert not os.path.exists(html_path)


def test_companion_still_fires_for_ordinary_docs_md_file():
    with _make_sandbox() as tmp:
        docs_directory = os.path.join(tmp, "docs")
        os.makedirs(docs_directory, exist_ok=True)
        md_path = os.path.join(docs_directory, "regular.md")
        html_path = os.path.join(docs_directory, "regular.html")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Regular")
        result = _run_hook(
            "Write",
            {"file_path": md_path, "content": "# Regular"},
        )
        assert result.returncode == 0
        assert os.path.exists(html_path)


def test_companion_skips_system_temp_directory():
    temp_directory = tempfile.gettempdir()
    md_path = os.path.join(temp_directory, "companion_temp_exempt_test.md")
    html_path = os.path.join(temp_directory, "companion_temp_exempt_test.html")
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Scratch")
        result = _run_hook(
            "Write",
            {"file_path": md_path, "content": "# Scratch"},
        )
        assert result.returncode == 0
        assert not os.path.exists(html_path)
    finally:
        for each_path in (md_path, html_path):
            if os.path.exists(each_path):
                os.remove(each_path)
