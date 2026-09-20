"""Constants the deterministic benchmark graders import.

::

    a command spec with no timeout   ->   the default command timeout
    a stdout line the grader quotes  ->   cut at the detail character limit

A grader reads one spec from ``cases.json``, so the two bounds it needs when
the spec stays silent live here.
"""

from __future__ import annotations

DEFAULT_COMMAND_TIMEOUT_SECONDS = 120
DETAIL_CHARACTER_LIMIT = 120
