#!/usr/bin/env python3
"""SessionStart hook: ask Claude to run /orchestrator for this session.

At a fresh or cleared session start this hook injects a directive telling Claude
to run the ``/orchestrator`` skill, so the session plans and delegates work from
the outset. The hook stays silent — writing nothing — when the session continues
an existing conversation or when the ``CLAUDE_AUTO_ORCHESTRATOR`` toggle is off.
"""

from __future__ import annotations

import json
import sys

import _path_setup  # noqa: F401

from hooks_constants.orchestrator_auto_starter_constants import (  # noqa: E402
    AUTO_ORCHESTRATOR_ENV_VAR_NAME,
    ORCHESTRATOR_START_DIRECTIVE,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)
from hooks_constants.session_start_injector import (  # noqa: E402
    build_session_start_payload,
    is_eligible_source,
    is_injection_enabled,
)
from hooks_constants.session_start_injector_constants import (  # noqa: E402
    SESSION_SOURCE_FIELD_KEY,
)


def build_orchestrator_directive() -> str:
    """Return the directive that asks Claude to run /orchestrator."""
    return ORCHESTRATOR_START_DIRECTIVE


def main() -> None:
    """Inject the /orchestrator directive on an eligible, enabled start, else stay silent."""
    payload = read_hook_input_dictionary_from_stdin()
    if payload is None:
        sys.exit(0)
    session_source = str(payload.get(SESSION_SOURCE_FIELD_KEY) or "")
    if not is_eligible_source(session_source):
        sys.exit(0)
    if not is_injection_enabled(AUTO_ORCHESTRATOR_ENV_VAR_NAME):
        sys.exit(0)
    directive_payload = build_session_start_payload(build_orchestrator_directive())
    sys.stdout.write(json.dumps(directive_payload) + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
