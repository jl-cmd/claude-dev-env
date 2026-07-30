#!/usr/bin/env node
/**
 * Session probe for C2 global-rule activation.
 *
 * Loads rules without paths: frontmatter from CLAUDE_CONFIG_DIR/rules and
 * records marker activation. simulation=true for harness probes.
 */

import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

const MARKER_PATTERN = /FRESH_SESSION_GLOBAL_RULE_MARKER_C2_\w+/g;

/**
 * @param {string} content
 * @returns {boolean}
 */
function hasPathsFrontmatter(content) {
    const frontmatterMatch = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
    if (!frontmatterMatch) {
        return false;
    }
    return /^paths\s*:/m.test(frontmatterMatch[1]);
}

function main() {
    const profileId = process.env.FRESH_SESSION_PROFILE_ID ?? 'unknown';
    const evidencePath = process.env.FRESH_SESSION_EVIDENCE_PATH;
    const expectedMarker = process.env.FRESH_SESSION_GLOBAL_RULE_MARKER ?? '';
    const configDir = process.env.CLAUDE_CONFIG_DIR;

    if (!configDir) {
        process.stderr.write('global-rule probe: CLAUDE_CONFIG_DIR is required\n');
        process.exit(2);
    }

    const rulesDirectory = join(configDir, 'rules');
    /** @type {string[]} */
    const loadedMarkers = [];
    /** @type {string[]} */
    const allLoadedRuleNames = [];

    if (existsSync(rulesDirectory)) {
        for (const eachName of readdirSync(rulesDirectory)) {
            if (!eachName.endsWith('.md')) {
                continue;
            }
            const content = readFileSync(join(rulesDirectory, eachName), 'utf8');
            if (hasPathsFrontmatter(content)) {
                continue;
            }
            allLoadedRuleNames.push(eachName);
            for (const eachMatch of content.matchAll(MARKER_PATTERN)) {
                loadedMarkers.push(eachMatch[0]);
            }
        }
    }

    const isActivated = expectedMarker.length > 0 && loadedMarkers.includes(expectedMarker);
    const record = {
        transport: 'fake-probe',
        profileId,
        probe: 'global-rule',
        environment: { CLAUDE_CONFIG_DIR: configDir },
        activation: {
            channel: 'session-probe',
            simulation: true,
            loadedMarkers: [...new Set(loadedMarkers)],
            allLoadedRuleNames,
            isActivated,
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
        `global-rule-probe profile=${profileId} activated=${isActivated} rules=${allLoadedRuleNames.length}\n`,
    );
    process.exit(0);
}

main();
