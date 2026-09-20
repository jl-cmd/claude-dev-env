"""Constants for the defective-variant detection check.

::

    harness exit            ->   the check could not run
    pytest harness exits    ->   pytest usage error, or no test collected
    expected argument count ->   module to swap, variant to swap over it
    pytest timeout seconds  ->   bound on the pytest run

"""

from __future__ import annotations

HARNESS_EXIT = 3
ALL_PYTEST_HARNESS_EXITS = (3, 4, 5)
EXPECTED_ARGUMENT_COUNT = 2
PYTEST_TIMEOUT_SECONDS = 110
