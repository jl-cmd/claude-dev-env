/**
 * Named values the installer reads, kept out of the code that uses them.
 *
 * `install.mjs` holds the install pipeline; the tables below hold the data that
 * pipeline compares against, so a value has one home and one spelling.
 */

/**
 * Entry names the source walk keeps out of installed trees.
 *
 * Each name represents local metadata or build output.
 * A contributor who runs the test suites and then runs `node bin/install.mjs`
 * copies from a source tree carrying these entries, so skipping the names at
 * the walk keeps installed trees and the install manifest focused on runtime
 * files.
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
 * The directory name skill directories carry in a package source and under
 * `~/.claude`.
 *
 * The copy loop reads `<package-root>/skills` and writes `~/.claude/skills`, the
 * dependency walk reads `<dependency-root>/skills`, the retired-skill prune reads
 * the installed directory, and the per-root stale-file prune names it as one of
 * its roots. One spelling serves every one of them, so the copy destination and
 * the prune target stay the same directory.
 */
export const MANAGED_SKILLS_DIRECTORY_NAME = 'skills';

/**
 * The directory name hook scripts carry in a package source and under
 * `~/.claude`.
 *
 * The copy loop reads `<package-root>/hooks` and writes `~/.claude/hooks`, the
 * hooks.json reads sit under the same name in each package source, the git-hook
 * shims and the mypy configuration point at the installed directory, the
 * retired-hook diff takes its relative paths against it, and the per-root
 * stale-file prune names it as one of its roots.
 */
export const MANAGED_HOOKS_DIRECTORY_NAME = 'hooks';

/**
 * The `~/.claude` file name that holds the user's harness settings.
 *
 * The hook merge writes it, the retired-hook prune rewrites it, and the uninstall
 * purge rewrites it, so all three reach the file through one name.
 */
export const SETTINGS_FILE_NAME = 'settings.json';

/**
 * The home-directory file name `install_mypy_ini.mjs` writes.
 *
 * mypy reads its configuration from the home directory, so this is the one file
 * the installer writes outside `~/.claude`. The install records the path and the
 * uninstall containment guard names it as a permitted location, so `--uninstall`
 * removes the file the install created.
 */
export const MYPY_INI_FILE_NAME = '.mypy.ini';

/**
 * Environment variable Codex uses for its config home. When unset, Codex reads
 * `~/.codex`. The installer copies shipped exec-policy files into
 * `<that home>/rules`.
 */
export const CODEX_HOME_ENVIRONMENT_VARIABLE = 'CODEX_HOME';

/**
 * Directory name Codex uses under the user home when `CODEX_HOME` is unset.
 */
export const DEFAULT_CODEX_DIRECTORY_NAME = '.codex';

/**
 * Directory name under the Codex home that holds `*.rules` exec-policy files.
 * Codex loads every file in that directory; see `load_exec_policy` in Codex.
 */
export const CODEX_RULES_DIRECTORY_NAME = 'rules';

/**
 * Package subdirectory that holds the shipped Codex exec-policy files. The
 * installer copies this tree into the Codex rules directory, not into
 * `~/.claude/`.
 */
export const CODEX_RULES_PACKAGE_DIRECTORY_NAME = 'codex-rules';

/**
 * Shipped exec-policy file name. A distinct name keeps a local `default.rules`
 * file in place.
 */
export const CODEX_RULES_SHIPPED_FILE_NAME = 'claude-dev-env.rules';

/**
 * Directory name Cursor uses under the user home for editor config.
 */
export const DEFAULT_CURSOR_DIRECTORY_NAME = '.cursor';

/**
 * Directory name under the Cursor home that holds generated `.mdc` rule files.
 */
export const CURSOR_RULES_DIRECTORY_NAME = 'rules';

/**
 * Installed script that writes Cursor `.mdc` files from Claude rules.
 */
export const CURSOR_SYNC_SCRIPT_FILE_NAME = 'sync_to_cursor.py';

/**
 * Windows Python launcher command the installer may bake into hook settings.
 */
export const WINDOWS_PYTHON_LAUNCHER_COMMAND = 'py -3';
