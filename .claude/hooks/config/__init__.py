"""Regular-package marker, matching the repo's other ``config/`` packages.

The hook imports ``config.session_start_refresh_constants`` because it runs as
a script path: the interpreter puts the hook's own directory at ``sys.path[0]``,
so this ``config`` shadows the repo-root one. A different launch shape —
``python -m``, a wrapper, a ``PYTHONPATH`` entry that puts the repo root first —
resolves ``config`` to the repo root instead and breaks the import.
"""
