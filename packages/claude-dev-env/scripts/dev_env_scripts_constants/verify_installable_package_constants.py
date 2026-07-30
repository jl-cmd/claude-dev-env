"""Constants for verify_installable_package — npm pack surface checks.

Holds manifest keys, pack/tarball path tokens, hook-command path markers,
git and smoke-tool argv pieces, and CLI status messages.
"""

MANIFEST_FILENAME: str = "installable-surfaces.manifest.json"
"""Basename of the committed installable-surfaces manifest under the package root."""

PACKAGE_JSON_FILENAME: str = "package.json"
"""Basename of the npm package manifest that lists the files field."""

PACKAGE_JSON_FILES_KEY: str = "files"
"""JSON key on package.json that lists packaged path entries."""

PACKAGE_JSON_EXCLUDE_PREFIX: str = "!"
"""Prefix on package.json files entries that exclude a path pattern."""

MANIFEST_DIRECTORIES_KEY: str = "directories"
"""JSON key listing required top-level package directories."""

MANIFEST_ROOT_FILES_KEY: str = "root_files"
"""JSON key listing required package-root files."""

TARBALL_PACKAGE_PREFIX: str = "package/"
"""Path prefix npm pack applies to every member inside the generated tarball."""

PLUGIN_ROOT_TOKEN: str = "${CLAUDE_PLUGIN_ROOT}/"
"""Placeholder prefix hooks.json uses for package-relative hook script paths."""

PYTHON_FILE_SUFFIX: str = ".py"
"""Suffix that marks a hook command token as a Python script path."""

HOOKS_JSON_RELATIVE_PATH: str = "hooks/hooks.json"
"""Package-relative path of the hook registration map."""

INSTALL_ENTRYPOINT_RELATIVE_PATH: str = "bin/install.mjs"
"""Package-relative path of the primary install CLI entrypoint."""

PACKAGE_PATH_FROM_REPOSITORY: str = "packages/claude-dev-env"
"""Repository-relative path of the published package directory."""

NPM_BINARY_NAME: str = "npm"
"""npm CLI binary name used to build the pack tarball on POSIX hosts."""

NPM_CMD_BINARY_NAME: str = "npm.cmd"
"""Windows npm launcher resolved before the extensionless npm name."""

NEWLINE_JOIN_SEPARATOR: str = "\n"
"""Separator used when joining multi-line verification failure reports."""

NPM_PACK_SUBCOMMAND: str = "pack"
"""npm subcommand that writes the installable tarball."""

NPM_PACK_JSON_FLAG: str = "--json"
"""Flag that makes npm pack emit machine-readable filename metadata."""

NPM_PACK_DESTINATION_FLAG: str = "--pack-destination"
"""Flag that directs npm pack to write the tarball into a chosen directory."""

NPM_PACK_FILENAME_KEY: str = "filename"
"""JSON field on an npm pack --json record that holds the tarball basename."""

GIT_BINARY_NAME: str = "git"
"""git CLI binary name used to confirm hook scripts are committed."""

GIT_LS_FILES_SUBCOMMAND: str = "ls-files"
"""git subcommand that lists tracked paths in the index."""

NODE_BINARY_NAME: str = "node"
"""Node.js binary name used for install-entrypoint syntax smoke checks."""

NODE_CHECK_FLAG: str = "--check"
"""Flag that makes node parse a script without executing it."""

UTF8_ENCODING: str = "utf-8"
"""Text encoding for manifest, hooks.json, and subprocess text mode."""

CLASS_PACKAGED: str = "packaged"
"""Surface classification when a directory is on disk and listed for packaging."""

CLASS_SOURCE_ONLY: str = "source_only"
"""Surface classification when a directory is on disk but not listed for packaging."""

CLASS_CONTRADICTORY: str = "contradictory"
"""Surface classification when package.json lists a directory that is missing on disk."""

EXIT_CODE_SUCCESS: int = 0
"""Process exit code when every installable-surface check passes."""

EXIT_CODE_FAILURE: int = 1
"""Process exit code when one or more installable-surface checks fail."""

MISSING_MANIFEST_SURFACES_HEADER: str = "Missing surfaces in npm pack tarball:"
"""Header printed when required manifest paths are absent from the packed tarball."""

UNTRACKED_HOOK_SCRIPTS_HEADER: str = "Hook scripts missing from git index:"
"""Header printed when a hooks.json command resolves to an untracked or missing file."""

SMOKE_COMPILE_FAILURES_HEADER: str = "Hook scripts failed py_compile:"
"""Header printed when a resolved hook script fails Python syntax compilation."""

INSTALL_ENTRYPOINT_SMOKE_FAILURE_HEADER: str = "Install entrypoint failed node --check:"
"""Header printed when bin/install.mjs fails the Node syntax smoke check."""

VERIFICATION_PASSED_MESSAGE: str = "installable package verification passed"
"""Status line printed when every check succeeds."""
