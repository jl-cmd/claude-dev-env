/**
 * Install-time expansion of $HOME / ${HOME} / ~/ in settings.json commands.
 *
 * Hosts that require referenced env vars at hook load time (for example Grok)
 * skip the hook when HOME is unset — common on Windows — so the installer
 * rewrites residual tokens to absolute home paths.
 */

/**
 * Expands $HOME, ${HOME}, and ~/ in a command string to an absolute home directory
 * using forward slashes.
 *
 * @param {string} commandString Hook or statusLine command text.
 * @param {string} homeDirectory Absolute home directory (any path separators).
 * @returns {string} Command with home tokens expanded.
 */
export function expandHomeDirectoryTokens(commandString, homeDirectory) {
    const normalizedHome = homeDirectory.replace(/\\/g, '/').replace(/\/+$/, '');
    let expandedCommand = commandString;
    expandedCommand = expandedCommand.replaceAll('${HOME}', normalizedHome);
    expandedCommand = expandedCommand.replace(/(?<![A-Za-z0-9_])\$HOME\b/g, normalizedHome);
    expandedCommand = expandedCommand.replace(/(^|[\s"'=])~\//g, `$1${normalizedHome}/`);
    return expandedCommand;
}

/**
 * Expands home-directory tokens in every settings.json hook command and in the
 * optional statusLine command so residual $HOME entries from older installs
 * become absolute paths and no longer require HOME at hook load time.
 *
 * @param {object} settings The parsed settings.json object (mutated in place).
 * @param {string} homeDirectory Absolute home directory (any path separators).
 * @returns {void}
 */
export function expandHomeDirectoryTokensInSettings(settings, homeDirectory) {
    if (settings.hooks) {
        for (const matcherGroups of Object.values(settings.hooks)) {
            for (const eachGroup of matcherGroups) {
                if (!eachGroup.hooks) continue;
                for (const eachHook of eachGroup.hooks) {
                    if (typeof eachHook.command === 'string') {
                        eachHook.command = expandHomeDirectoryTokens(
                            eachHook.command,
                            homeDirectory,
                        );
                    }
                }
            }
        }
    }
    if (settings.statusLine && typeof settings.statusLine.command === 'string') {
        settings.statusLine.command = expandHomeDirectoryTokens(
            settings.statusLine.command,
            homeDirectory,
        );
    }
}
