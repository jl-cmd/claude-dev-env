#!/usr/bin/env node
/**
 * Session probe for C3 path-scoped rule activation.
 *
 * Activates only when the workspace path matches the rule's paths: globs and
 * the marker is present in the rule body.
 */

import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

const MARKER_PATTERN = /FRESH_SESSION_PATH_RULE_MARKER_C3_\w+/g;

/**
 * @param {string} content
 * @returns {string[]}
 */
function extractPathGlobs(content) {
    const frontmatterMatch = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
    if (!frontmatterMatch) {
        return [];
    }
    const block = frontmatterMatch[1];
    if (!/^paths\s*:/m.test(block)) {
        return [];
    }
    /** @type {string[]} */
    const allGlobs = [];
    for (const eachLine of block.split(/\r?\n/)) {
        const match = eachLine.match(/^\s*-\s*["']?([^"'\n]+)["']?\s*$/);
        if (match) {
            allGlobs.push(match[1].trim());
        }
    }
    return allGlobs;
}

/**
 * Minimal glob match for ** / segment / ** shapes used by the fixture.
 *
 * @param {string} workspacePath
 * @param {string} globPattern
 * @param {string} matchingSegment
 * @returns {boolean}
 */
function workspaceMatchesGlob(workspacePath, globPattern, matchingSegment) {
    const normalizedWorkspace = workspacePath.replace(/\\/g, '/').toLowerCase();
    const normalizedGlob = globPattern.replace(/\\/g, '/').toLowerCase();
    const normalizedSegment = matchingSegment.toLowerCase();
    if (normalizedGlob.includes(`**/${normalizedSegment}/**`)) {
        return normalizedWorkspace.includes(`/${normalizedSegment}`);
    }
    if (normalizedGlob.includes(normalizedSegment)) {
        return normalizedWorkspace.includes(normalizedSegment);
    }
    return false;
}

function main() {
    const profileId = process.env.FRESH_SESSION_PROFILE_ID ?? 'unknown';
    const evidencePath = process.env.FRESH_SESSION_EVIDENCE_PATH;
    const expectedMarker = process.env.FRESH_SESSION_PATH_RULE_MARKER ?? '';
    const configDir = process.env.CLAUDE_CONFIG_DIR;
    const workspacePath = process.env.FRESH_SESSION_WORKSPACE_PATH ?? '';
    const matchingSegment = process.env.FRESH_SESSION_MATCHING_SEGMENT ?? 'matching-workspace';

    if (!configDir) {
        process.stderr.write('path-rule probe: CLAUDE_CONFIG_DIR is required\n');
        process.exit(2);
    }

    const rulesDirectory = join(configDir, 'rules');
    /** @type {string[]} */
    const loadedMarkers = [];
    let matchedPath = false;

    if (existsSync(rulesDirectory)) {
        for (const eachName of readdirSync(rulesDirectory)) {
            if (!eachName.endsWith('.md')) {
                continue;
            }
            const content = readFileSync(join(rulesDirectory, eachName), 'utf8');
            const allGlobs = extractPathGlobs(content);
            if (allGlobs.length === 0) {
                continue;
            }
            const doesMatch = allGlobs.some((eachGlob) => (
                workspaceMatchesGlob(workspacePath, eachGlob, matchingSegment)
            ));
            if (!doesMatch) {
                continue;
            }
            matchedPath = true;
            for (const eachMatch of content.matchAll(MARKER_PATTERN)) {
                loadedMarkers.push(eachMatch[0]);
            }
        }
    }

    const uniqueMarkers = [...new Set(loadedMarkers)];
    const isActivated = matchedPath
        && expectedMarker.length > 0
        && uniqueMarkers.includes(expectedMarker);

    const record = {
        transport: 'fake-probe',
        profileId,
        probe: 'path-rule',
        environment: {
            CLAUDE_CONFIG_DIR: configDir,
            FRESH_SESSION_WORKSPACE_PATH: workspacePath,
        },
        activation: {
            channel: 'session-probe',
            simulation: true,
            loadedMarkers: uniqueMarkers,
            isActivated,
            matchedPath,
            expectedMarker,
        },
        exitStatus: 0,
        recordedAt: new Date().toISOString(),
    };

    if (evidencePath) {
        mkdirSync(dirname(evidencePath), { recursive: true });
        writeFileSync(evidencePath, `${JSON.stringify(record, null, 2)}\n`, 'utf8');
    }

    process.stdout.write(
        `path-rule-probe profile=${profileId} matched=${matchedPath} activated=${isActivated}\n`,
    );
    process.exit(0);
}

main();
