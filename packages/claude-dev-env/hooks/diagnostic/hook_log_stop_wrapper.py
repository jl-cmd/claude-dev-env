#!/usr/bin/env python3
"""Disabled Stop-hook wrapper for the hook-log extractor.

The wrapper is off the Stop dispatcher roster and exits 0 without spawning
the extractor or writing debounce state. Git history holds the prior
debounce-and-spawn implementation if Neon-backed extraction returns.
"""

from __future__ import annotations

import sys
from pathlib import Path

if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hooks_constants.hook_log_extractor_constants import EXIT_CODE_SUCCESS


def main() -> int:
    """Exit success without spawning the extractor."""
    return EXIT_CODE_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
