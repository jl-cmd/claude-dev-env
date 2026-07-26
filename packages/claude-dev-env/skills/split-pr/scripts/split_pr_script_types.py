"""Type aliases shared by every split-pr script.

::

    from split_pr_script_types import JsonObject

    def build_plan() -> JsonObject: ...

One alias in one module keeps the plan, slice, and payload signatures across
the split-pr scripts reading as the same type.
"""

from __future__ import annotations

JsonObject = dict[str, object]
