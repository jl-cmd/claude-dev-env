"""Emit formatted bugteam review body markdown to stdout.

Usage:
  python scripts/format_review_body.py --loop 3 --p0-count 2 --p1-count 1 --p2-count 0 [--unanchored-count 0]
"""

from __future__ import annotations

import argparse
import sys


def build_review_heading(
    *,
    loop: int,
    p0_count: int,
    p1_count: int,
    p2_count: int,
) -> str:
    """Build the review heading line.

    Args:
        loop: Loop iteration number.
        p0_count: Number of P0 (critical) findings.
        p1_count: Number of P1 (high) findings.
        p2_count: Number of P2 (medium) findings.

    Returns:
        Formatted heading (e.g. '## /bugteam loop 3 audit: 2P0 / 1P1 / 0P2').
    """
    return f"## /bugteam loop {loop} audit: {p0_count}P0 / {p1_count}P1 / {p2_count}P2"


def build_review_body(
    *,
    loop: int,
    p0_count: int,
    p1_count: int,
    p2_count: int,
    unanchored_count: int = 0,
) -> str:
    """Build the complete review body markdown.

    Args:
        loop: Loop iteration number.
        p0_count: Number of P0 (critical) findings.
        p1_count: Number of P1 (high) findings.
        p2_count: Number of P2 (medium) findings.
        unanchored_count: Number of unanchored findings.

    Returns:
        Complete review body markdown string.
    """
    lines = [
        build_review_heading(
            loop=loop, p0_count=p0_count, p1_count=p1_count, p2_count=p2_count
        )
    ]
    if unanchored_count > 0:
        lines.append("")
        lines.append(
            f"_{unanchored_count} finding(s) could not be anchored to a file:line._"
        )
    return "\n".join(lines)


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        all_argv: Command-line argument list.

    Returns:
        Parsed namespace with loop, counts, and optional unanchored count.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", type=int, required=True)
    parser.add_argument("--p0-count", type=int, required=True)
    parser.add_argument("--p1-count", type=int, required=True)
    parser.add_argument("--p2-count", type=int, required=True)
    parser.add_argument("--unanchored-count", type=int, default=0)
    return parser.parse_args(all_argv)


def main(
    all_arguments: list[str], *, unanchored_count: int | None = None
) -> int:
    """Entry point: emit formatted review body to stdout.

    Args:
        all_arguments: Command-line arguments.
        unanchored_count: Override for unanchored count (default: from CLI).

    Returns:
        0 on success.
    """
    arguments = parse_arguments(all_arguments)
    body = build_review_body(
        loop=arguments.loop,
        p0_count=getattr(arguments, "p0_count"),
        p1_count=getattr(arguments, "p1_count"),
        p2_count=getattr(arguments, "p2_count"),
        unanchored_count=(
            arguments.unanchored_count
            if unanchored_count is None
            else unanchored_count
        ),
    )
    sys.stdout.write(body)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    all_argv = sys.argv[1:]
    arguments = parse_arguments(all_argv)
    raise SystemExit(main(all_argv, unanchored_count=arguments.unanchored_count))
