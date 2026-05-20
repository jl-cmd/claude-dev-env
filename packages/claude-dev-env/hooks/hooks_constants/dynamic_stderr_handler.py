"""Logging handler that resolves sys.stderr at emit time for testability."""

from __future__ import annotations

import logging
import sys


class DynamicStderrHandler(logging.Handler):
    """Logging handler that resolves sys.stderr at emit time, not at init time.

    This allows tests that patch sys.stderr to capture log output emitted
    from this handler without needing to re-import the module.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            formatted_line = self.format(record)
            sys.stderr.write(formatted_line + "\n")
            sys.stderr.flush()
        except Exception:
            self.handleError(record)
