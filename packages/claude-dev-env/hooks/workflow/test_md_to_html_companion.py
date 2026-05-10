"""Tests for md_to_html_companion hook.

This test suite validates that the md-to-html companion hook correctly
generates HTML from markdown input, handles edge cases, and produces
valid HTML output.
"""

import json
import os
import subprocess
import sys
import tempfile


HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "md_to_html_companion.py")


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
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
        py_path = os.path.join(tmp, "main.py")
        html_path = os.path.join(tmp, "main.html")


        with open(py_path, "w", encoding="utf-8") as f:
            f.write("x = 1")

        result = _run_hook("Write", {"file_path": py_path, "content": "x = 1"})
        assert result.returncode == 0
        assert not os.path.exists(html_path)


def test_skips_claude_dir():
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("This is **bold** text.")

        _run_hook("Write", {"file_path": md_path, "content": "This is **bold** text."})
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert "<strong>bold</strong>" in html


def test_escapes_html_special_chars():
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("```python\nx = 1\n```")

        _run_hook("Write", {"file_path": md_path, "content": "```python\nx = 1\n```"})
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert 'class="language-python"' in html


def test_language_class_skips_invalid():
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
        md_path = os.path.join(tmp, "guide.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("```c++\nint x = 1;\n```")

        _run_hook("Write", {"file_path": md_path, "content": "```c++\nint x = 1;\n```"})
        html_path = os.path.join(tmp, "guide.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        assert 'class="language-c++"' in html


def test_link_text_asterisks_remain_literal():
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
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
    with tempfile.TemporaryDirectory() as tmp:
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
