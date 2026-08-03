/**
 * Pure CLI vs Desktop embedded-version compatibility classifier.
 *
 * The classifier takes probe results only. Callers own process spawn, timeouts,
 * and binary discovery. Fail closed on unreadable or missing inputs.
 */

export const COMPATIBILITY_POLICY_VERSION = 1;

/** @typedef {'pass' | 'warn' | 'block'} CompatibilityAction */
/** @typedef {
 *   | 'equal'
 *   | 'patch-drift'
 *   | 'minor-drift'
 *   | 'major-drift'
 *   | 'missing-binary'
 *   | 'unreadable'
 *   | 'process-error'
 *   | 'non-semver'
 * } CompatibilityClass */

/**
 * Action table for every compatibility class. Missing / unreadable / process
 * errors and major/minor drift block; patch drift warns; equality passes.
 */
export const COMPATIBILITY_ACTION_BY_CLASS = Object.freeze({
    equal: 'pass',
    'patch-drift': 'warn',
    'minor-drift': 'block',
    'major-drift': 'block',
    'missing-binary': 'block',
    unreadable: 'block',
    'process-error': 'block',
    'non-semver': 'block',
});

/**
 * @typedef {{
 *   path: string | null,
 *   versionText: string | null,
 *   errorCode?: 'missing' | 'unreadable' | 'process-error' | null,
 *   errorMessage?: string | null,
 * }} VersionProbeResult
 */

/**
 * @typedef {{
 *   cliPath: string | null,
 *   desktopPath: string | null,
 *   cliVersion: string | null,
 *   desktopVersion: string | null,
 *   policyVersion: number,
 *   class: CompatibilityClass,
 *   action: CompatibilityAction,
 *   message: string,
 * }} CompatibilityResult
 */

/**
 * Classify CLI and Desktop embedded version compatibility from probe results.
 *
 * ::
 *
 *     classifyVersionCompatibility({
 *       cli: { path: 'cli', versionText: '2.1.220' },
 *       desktop: { path: 'desktop', versionText: '2.1.220' },
 *     })
 *     // class: equal, action: pass
 *
 *     classifyVersionCompatibility({
 *       cli: { path: 'cli', versionText: '2.1.220' },
 *       desktop: { path: 'desktop', versionText: '2.1.219' },
 *     })
 *     // class: patch-drift, action: warn
 *
 * @param {{
 *   cli: VersionProbeResult,
 *   desktop: VersionProbeResult,
 * }} parameters
 * @returns {CompatibilityResult}
 */
export function classifyVersionCompatibility(parameters) {
    const cliProbe = normalizeProbe(parameters.cli);
    const desktopProbe = normalizeProbe(parameters.desktop);

    const base = {
        cliPath: cliProbe.path,
        desktopPath: desktopProbe.path,
        cliVersion: extractVersionLabel(cliProbe.versionText),
        desktopVersion: extractVersionLabel(desktopProbe.versionText),
        policyVersion: COMPATIBILITY_POLICY_VERSION,
    };

    const probeFailure = firstProbeFailure(cliProbe, desktopProbe);
    if (probeFailure) {
        return finalizeResult({
            ...base,
            class: probeFailure.className,
            message: probeFailure.message,
        });
    }

    const cliVersion = parseSemver(cliProbe.versionText);
    const desktopVersion = parseSemver(desktopProbe.versionText);
    if (!cliVersion || !desktopVersion) {
        return finalizeResult({
            ...base,
            class: 'non-semver',
            message: formatNonSemverMessage(cliProbe.versionText, desktopProbe.versionText),
        });
    }

    if (
        cliVersion.major === desktopVersion.major
        && cliVersion.minor === desktopVersion.minor
        && cliVersion.patch === desktopVersion.patch
    ) {
        return finalizeResult({
            ...base,
            class: 'equal',
            message: `CLI and Desktop versions match (${formatSemver(cliVersion)})`,
        });
    }

    if (cliVersion.major !== desktopVersion.major) {
        return finalizeResult({
            ...base,
            class: 'major-drift',
            message: formatDriftMessage('major', cliVersion, desktopVersion),
        });
    }

    if (cliVersion.minor !== desktopVersion.minor) {
        return finalizeResult({
            ...base,
            class: 'minor-drift',
            message: formatDriftMessage('minor', cliVersion, desktopVersion),
        });
    }

    return finalizeResult({
        ...base,
        class: 'patch-drift',
        message: formatDriftMessage('patch', cliVersion, desktopVersion),
    });
}

/**
 * True when the classified action blocks launch before profile-state mutation.
 *
 * @param {CompatibilityResult} result
 * @returns {boolean}
 */
export function shouldBlockLaunch(result) {
    return result.action === 'block';
}

/**
 * Parse a version string into major.minor.patch when the leading triple is semver-shaped.
 *
 * @param {string | null | undefined} versionText
 * @returns {{major: number, minor: number, patch: number} | null}
 */
export function parseSemver(versionText) {
    if (typeof versionText !== 'string') {
        return null;
    }
    const trimmed = versionText.trim();
    if (!trimmed) {
        return null;
    }
    const match = trimmed.match(/(\d+)\.(\d+)\.(\d+)/);
    if (!match) {
        return null;
    }
    return {
        major: Number(match[1]),
        minor: Number(match[2]),
        patch: Number(match[3]),
    };
}

/**
 * @param {VersionProbeResult | null | undefined} probe
 * @returns {VersionProbeResult}
 */
function normalizeProbe(probe) {
    if (!probe || typeof probe !== 'object') {
        return {
            path: null,
            versionText: null,
            errorCode: 'missing',
            errorMessage: 'probe missing',
        };
    }
    return {
        path: typeof probe.path === 'string' ? probe.path : null,
        versionText: typeof probe.versionText === 'string' ? probe.versionText : null,
        errorCode: probe.errorCode ?? null,
        errorMessage: probe.errorMessage ?? null,
    };
}

/**
 * @param {VersionProbeResult} cliProbe
 * @param {VersionProbeResult} desktopProbe
 * @returns {{className: CompatibilityClass, message: string} | null}
 */
function firstProbeFailure(cliProbe, desktopProbe) {
    for (const [eachLabel, eachProbe] of [
        ['CLI', cliProbe],
        ['Desktop', desktopProbe],
    ]) {
        if (eachProbe.errorCode === 'missing' || !eachProbe.path) {
            return {
                className: 'missing-binary',
                message: `${eachLabel} binary path is missing`,
            };
        }
        if (eachProbe.errorCode === 'process-error') {
            return {
                className: 'process-error',
                message: `${eachLabel} version probe failed: ${eachProbe.errorMessage || 'process error'}`,
            };
        }
        if (eachProbe.errorCode === 'unreadable' || eachProbe.versionText === null) {
            return {
                className: 'unreadable',
                message: `${eachLabel} version output is unreadable`,
            };
        }
    }
    return null;
}

/**
 * @param {string | null} versionText
 * @returns {string | null}
 */
function extractVersionLabel(versionText) {
    if (typeof versionText !== 'string') {
        return null;
    }
    const trimmed = versionText.trim();
    return trimmed || null;
}

/**
 * @param {{
 *   cliPath: string | null,
 *   desktopPath: string | null,
 *   cliVersion: string | null,
 *   desktopVersion: string | null,
 *   policyVersion: number,
 *   class: CompatibilityClass,
 *   message: string,
 * }} partial
 * @returns {CompatibilityResult}
 */
function finalizeResult(partial) {
    const action = COMPATIBILITY_ACTION_BY_CLASS[partial.class];
    return {
        cliPath: partial.cliPath,
        desktopPath: partial.desktopPath,
        cliVersion: partial.cliVersion,
        desktopVersion: partial.desktopVersion,
        policyVersion: partial.policyVersion,
        class: partial.class,
        action,
        message: partial.message,
    };
}

/**
 * @param {'major' | 'minor' | 'patch'} axis
 * @param {{major: number, minor: number, patch: number}} cliVersion
 * @param {{major: number, minor: number, patch: number}} desktopVersion
 * @returns {string}
 */
function formatDriftMessage(axis, cliVersion, desktopVersion) {
    return `${axis} drift: CLI ${formatSemver(cliVersion)} vs Desktop ${formatSemver(desktopVersion)}`;
}

/**
 * @param {{major: number, minor: number, patch: number}} version
 * @returns {string}
 */
function formatSemver(version) {
    return `${version.major}.${version.minor}.${version.patch}`;
}

/**
 * @param {string | null} cliText
 * @param {string | null} desktopText
 * @returns {string}
 */
function formatNonSemverMessage(cliText, desktopText) {
    return `non-semver version text: CLI=${JSON.stringify(cliText)} Desktop=${JSON.stringify(desktopText)}`;
}
