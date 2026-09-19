import sys
from pathlib import Path

_HOOKS_AUDIT_DIRECTORY = str(Path(__file__).resolve().parent)

if _HOOKS_AUDIT_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_AUDIT_DIRECTORY)

collect_ignore = ["fixtures"]
