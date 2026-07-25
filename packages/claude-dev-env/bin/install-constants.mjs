/**
 * Named values the installer reads, kept out of the code that uses them.
 *
 * `install.mjs` holds the install pipeline; the tables below hold the data that
 * pipeline compares against, so a value has one home and one spelling.
 */

/**
 * Entry names the source walk leaves behind, whatever directory they sit in.
 *
 * Each name belongs to a tool that writes beside the source it reads: Python
 * bytecode caches, the ruff, pytest, and mypy caches, an installed
 * `node_modules` tree, and the macOS Finder's `.DS_Store` marker. A contributor
 * who runs the test suites and then runs `node bin/install.mjs` copies from a
 * source tree carrying all of them, so skipping the names at the walk keeps them
 * out of `~/.claude` and out of the install manifest.
 */
export const SKIPPED_SOURCE_ENTRY_NAMES = new Set([
    '__pycache__',
    '.ruff_cache',
    '.pytest_cache',
    '.mypy_cache',
    'node_modules',
    '.DS_Store',
]);

/**
 * File extensions the source walk leaves behind, compared in lower case.
 *
 * Python writes a `.pyc` beside a module inside `__pycache__` and a `.pyo` under
 * an optimized run, and either can land outside a cache directory, so the
 * extension check stands alongside the name check.
 */
export const SKIPPED_SOURCE_FILE_EXTENSIONS = new Set(['.pyc', '.pyo']);

/**
 * The name shape a run backup directory carries under
 * `~/.claude/.claude-dev-env-pruned/`.
 *
 * The installer names each run backup from an ISO timestamp with every `:` and
 * `.` rewritten as `-`, for example `2026-07-25T18-04-11-923Z`. The retention
 * sweep removes only a direct child matching this shape, so a directory any
 * other tool or person left in the backup directory stays where it is.
 */
export const RUN_BACKUP_DIRECTORY_NAME_PATTERN =
    /^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{3}Z$/;

/**
 * The `~/.claude` directory name skill directories install into.
 *
 * The skills copy loop, the retired-skill prune, and the per-root stale-file
 * prune each name this directory, so one spelling serves all three.
 */
export const MANAGED_SKILLS_DIRECTORY_NAME = 'skills';

/**
 * The `~/.claude` directory name hook scripts install into.
 *
 * The retired-hook diff reads its relative paths against this directory, and the
 * per-root stale-file prune moves its content under a backup child of the same
 * name.
 */
export const MANAGED_HOOKS_DIRECTORY_NAME = 'hooks';

/**
 * The `~/.claude` file name that holds the user's harness settings.
 *
 * The hook merge writes it and the retired-hook prune rewrites it, so both reach
 * the file through one name.
 */
export const SETTINGS_FILE_NAME = 'settings.json';
