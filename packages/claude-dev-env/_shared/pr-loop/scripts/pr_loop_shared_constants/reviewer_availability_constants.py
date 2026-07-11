"""Configuration constants for the unified reviewer-availability pre-check.

The down code is 3 so a deliberate reviewer-down report stays distinguishable
from a generic interpreter crash (exit 1) and an argparse usage error
(exit 2). A caller that gates on the down code treats any other non-zero exit
as a broken check, not a down reviewer, and fails open.
"""

from __future__ import annotations

EXIT_CODE_REVIEWER_AVAILABLE: int = 0
EXIT_CODE_REVIEWER_DOWN: int = 3
