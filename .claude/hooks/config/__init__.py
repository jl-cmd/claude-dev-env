"""Regular-package marker, matching the repo's other ``config/`` packages.

The hook imports ``config.session_start_refresh_constants``. On a script-path
launch the interpreter puts the hook's own directory at ``sys.path[0]``, so
this ``config`` shadows the repo-root one. For a launch shape that leaves the
hook directory off ``sys.path`` — ``PYTHONSAFEPATH``, ``python -m``, a wrapper
— the hook catches the ``ImportError``, drops any wrongly-resolved ``config``
package from ``sys.modules`` (the failed import leaves it cached there, and a
cached entry would win the retry), inserts its own directory at the front of
``sys.path``, and retries the same import.
"""
