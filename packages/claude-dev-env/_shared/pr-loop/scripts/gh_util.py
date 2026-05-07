"""Shared helpers for invoking GitHub CLI with basic resiliency."""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

sys.modules.pop("config", None)
if str(Path(__file__).absolute().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).absolute().parent))

from config.gh_util_constants import (
    ALL_AUTH_ERROR_MARKERS,
    ALL_TRANSIENT_ERROR_MARKERS,
    DEFAULT_BACKOFF_SECONDS,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT_SECONDS,
    EXPONENTIAL_BACKOFF_BASE,
    GH_TIMEOUT_RETURN_CODE,
    INLINE_REVIEW_COMMENTS_PATH_TEMPLATE,
)


def _positive_int(raw_value: str) -> int:
    """Argparse type that accepts only positive integers."""
    parsed_int = int(raw_value)
    if parsed_int < 1:
        raise argparse.ArgumentTypeError(
            f"value must be a positive integer, got {parsed_int}"
        )
    return parsed_int


def _is_transient_error(message: str) -> bool:
    lowered = message.lower()
    return any(each_marker in lowered for each_marker in ALL_TRANSIENT_ERROR_MARKERS)


def _is_auth_error(message: str) -> bool:
    lowered = message.lower()
    return any(each_marker in lowered for each_marker in ALL_AUTH_ERROR_MARKERS)
