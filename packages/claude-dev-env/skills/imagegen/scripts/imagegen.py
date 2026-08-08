"""Command-line entry point for exact-resolution image generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from config.constants import ALL_SUPPORTED_BACKENDS, ALL_SUPPORTED_RESIZE_POLICIES
from imagegen_core import ImagegenError, generate_image, parse_size


def build_parser() -> argparse.ArgumentParser:
    """Build the imagegen command-line parser.

    Returns:
        Parser for the imagegen command-line contract.
    """
    parser = argparse.ArgumentParser(description="Generate an exact-resolution image")
    parser.add_argument("--backend", choices=ALL_SUPPORTED_BACKENDS, required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--size", required=True)
    parser.add_argument("--output", dest="destination_path", type=Path, required=True)
    parser.add_argument("--resize-policy", choices=ALL_SUPPORTED_RESIZE_POLICIES, default=ALL_SUPPORTED_RESIZE_POLICIES[0])
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    """Run the CLI and return a process status.

    Returns:
        Zero for a published artifact and one for a generation failure.
    """
    arguments = build_parser().parse_args()
    try:
        all_receipt = generate_image(arguments.prompt, arguments.backend, parse_size(arguments.size), arguments.destination_path, arguments.resize_policy, arguments.overwrite)
    except ImagegenError as error:
        print(f"ERROR: {error}")
        return 1
    print(f"Generated {arguments.destination_path} ({all_receipt['transformation']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
