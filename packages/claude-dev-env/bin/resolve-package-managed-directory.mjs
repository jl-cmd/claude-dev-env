/**
 * Resolve a managed content directory in a package source tree.
 *
 * This package keeps managed trees under `.agents/<name>/`. A dependency
 * package may still keep those trees at `<package-root>/<name>/`. Callers pass
 * the package root and the managed directory name; this helper returns the
 * directory that exists.
 */

import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { PACKAGE_AGENTS_HOME_DIRECTORY_NAME } from './install-constants.mjs';

/**
 * @param {string} sourceRoot Package root that may hold `.agents/<name>` or `<name>`.
 * @param {string} directoryName Managed directory name.
 * @returns {string} Absolute source directory to copy from.
 */
export function resolvePackageManagedDirectory(sourceRoot, directoryName) {
    const agentsHomeDirectory = join(
        sourceRoot,
        PACKAGE_AGENTS_HOME_DIRECTORY_NAME,
        directoryName,
    );
    if (existsSync(agentsHomeDirectory)) {
        return agentsHomeDirectory;
    }
    return join(sourceRoot, directoryName);
}
