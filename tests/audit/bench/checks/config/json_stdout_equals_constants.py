"""Constants for the JSON stdout comparison check.

::

    harness exit            ->   the check could not run
    minimum argument count  ->   expected JSON text, plus one command word
    command timeout seconds ->   bound on the graded command

"""

from __future__ import annotations

HARNESS_EXIT = 3
MINIMUM_ARGUMENT_COUNT = 2
COMMAND_TIMEOUT_SECONDS = 60
