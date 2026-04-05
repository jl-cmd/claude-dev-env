"""Output formatting for validators.

Provides:
- Colored terminal output
- Contextual diff display
- Progress indicators
- JSON output for CI
"""

import json
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, TypedDict


class ViolationDict(TypedDict):
    file: str
    line: int
    message: str


class ValidatorResultDict(TypedDict):
    name: str
    checks: str
    passed: bool
    output: str


class OutputMode(Enum):
    TEXT = "text"
    JSON = "json"
    COMPACT = "compact"


def colorize(text: str, color: str, enabled: bool = True) -> str:
    """Add ANSI color codes to text.

    Args:
        text: Text to colorize
        color: Color name (red, green, yellow, blue)
        enabled: Whether to apply colors

    Returns:
        Colorized text or original if disabled
    """
    if not enabled:
        return text

    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "bold": "\033[1m",
        "reset": "\033[0m",
    }

    color_code = colors.get(color, "")
    reset = colors["reset"]

    return f"{color_code}{text}{reset}"


def format_violation_with_context(
    source: str,
    line_num: int,
    message: str,
    context_lines: int = 2,
    use_colors: bool = True,
) -> str:
    """Format a violation with surrounding code context.

    Args:
        source: Full source code
        line_num: Line number of violation (1-indexed)
        message: Violation message
        context_lines: Number of context lines before/after
        use_colors: Whether to use ANSI colors

    Returns:
        Formatted violation with context
    """
    lines = source.splitlines()
    start = max(0, line_num - context_lines - 1)
    end = min(len(lines), line_num + context_lines)

    output_lines: List[str] = []
    output_lines.append(colorize(f"  {message}", "red", use_colors))
    output_lines.append("")

    for i in range(start, end):
        line_number = i + 1
        line_content = lines[i]
        prefix = ">" if line_number == line_num else " "

        if line_number == line_num:
            formatted = colorize(
                f"  {prefix} {line_number:4d} | {line_content}",
                "red",
                use_colors,
            )
        else:
            formatted = f"    {line_number:4d} | {line_content}"

        output_lines.append(formatted)

    output_lines.append("")
    return "\n".join(output_lines)


@dataclass(frozen=True)
class OutputFormatter:
    """Formats validator output for display."""

    mode: OutputMode = OutputMode.TEXT
    use_colors: bool = True
    show_context: bool = True
    context_lines: int = 2

    @property
    def effective_use_colors(self) -> bool:
        """Return whether colors should be used, accounting for TTY detection."""
        return self.use_colors and sys.stdout.isatty()

    def format_header(self, title: str) -> str:
        """Format a section header."""
        if self.mode == OutputMode.JSON:
            return ""

        separator = "=" * 60
        return f"\n{separator}\n{title}\n{separator}\n"

    def format_progress(self, current: int, total: int, name: str) -> str:
        """Format a progress indicator."""
        if self.mode == OutputMode.JSON:
            return ""

        bar_width = 20
        filled = int(bar_width * current / total)
        bar = "#" * filled + "-" * (bar_width - filled)

        return f"[{bar}] {current}/{total} {name}"

    def format_result(
        self,
        name: str,
        checks: str,
        passed: bool,
        output: str,
    ) -> str:
        """Format a single validator result."""
        if self.mode == OutputMode.JSON:
            return ""

        use_colors = self.effective_use_colors
        status = colorize("[PASS]", "green", use_colors) if passed else colorize("[FAIL]", "red", use_colors)

        lines = [f"{status} {name} (checks {checks})"]

        if not passed and output:
            for line in output.strip().split("\n"):
                if line:
                    lines.append(f"       {line}")

        return "\n".join(lines)

    def format_results(self, results: List[ValidatorResultDict]) -> str:
        """Format all validator results."""
        if self.mode == OutputMode.JSON:
            return json.dumps({"results": results}, indent=2)

        output_lines: List[str] = []

        for result in results:
            output_lines.append(
                self.format_result(
                    name=result["name"],
                    checks=result.get("checks", ""),
                    passed=result["passed"],
                    output=result.get("output", ""),
                )
            )

        return "\n".join(output_lines)

    def format_summary(self, passed: int, failed: int) -> str:
        """Format the final summary."""
        if self.mode == OutputMode.JSON:
            return ""

        use_colors = self.effective_use_colors
        separator = "=" * 60

        if failed == 0:
            verdict = colorize("READY TO PUSH", "green", use_colors)
            detail = "All automated checks passed"
        else:
            verdict = colorize("VIOLATIONS FOUND", "red", use_colors)
            detail = f"{failed} check(s) failed"

        return f"\n{separator}\nVERDICT: {verdict} - {detail}\n{separator}\n"

    def format_stats(
        self,
        files_checked: int,
        violations_found: int,
        time_elapsed: float,
    ) -> str:
        """Format statistics."""
        if self.mode == OutputMode.JSON:
            return ""

        return (
            f"\nStats: {files_checked} files checked, "
            f"{violations_found} violations found, "
            f"{time_elapsed:.2f}s elapsed\n"
        )


def group_violations_by_file(violations: List[ViolationDict]) -> Dict[str, List[ViolationDict]]:
    """Group violations by file path.

    Args:
        violations: List of violation dicts with 'file' key

    Returns:
        Dict mapping file paths to their violations
    """
    grouped: Dict[str, List[ViolationDict]] = {}

    for violation in violations:
        file_path = violation.get("file", "unknown")
        if file_path not in grouped:
            grouped[file_path] = []
        grouped[file_path].append(violation)

    return grouped


def format_grouped_violations(
    grouped: Dict[str, List[ViolationDict]],
    use_colors: bool = True,
) -> str:
    """Format violations grouped by file.

    Args:
        grouped: Dict from group_violations_by_file
        use_colors: Whether to use ANSI colors

    Returns:
        Formatted string with file headers
    """
    output_lines: List[str] = []

    for file_path, violations in sorted(grouped.items()):
        output_lines.append("")
        output_lines.append(colorize(f"  {file_path}", "bold", use_colors))
        output_lines.append("  " + "-" * (len(file_path) + 2))

        for violation in sorted(violations, key=lambda v: v.get("line", 0)):
            line = violation.get("line", "?")
            message = violation.get("message", "Unknown violation")
            output_lines.append(f"    Line {line}: {message}")

    return "\n".join(output_lines)
