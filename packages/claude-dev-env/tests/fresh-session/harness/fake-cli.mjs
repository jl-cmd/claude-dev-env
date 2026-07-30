#!/usr/bin/env node
/**
 * Fake Claude CLI transport for the fresh-session harness.
 *
 * Records argv, selected environment keys, and a version string to an evidence
 * file named by FRESH_SESSION_EVIDENCE_PATH. Exits non-zero when
 * FRESH_SESSION_FAIL_PROFILE matches FRESH_SESSION_PROFILE_ID so a failed
 * profile produces a profile-specific diagnostic.
 */

import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

const FAKE_CLI_VERSION = 'fake-claude/0.0.0-harness';

function main() {
    const profileId = process.env.FRESH_SESSION_PROFILE_ID ?? 'unknown';
    const evidencePath = process.env.FRESH_SESSION_EVIDENCE_PATH;
    const failProfile = process.env.FRESH_SESSION_FAIL_PROFILE ?? '';
    const shouldFail = failProfile.length > 0 && failProfile === profileId;

    const record = {
        transport: 'fake',
        profileId,
        cliVersion: FAKE_CLI_VERSION,
        argv: process.argv.slice(2),
        environment: {
            HOME: process.env.HOME ?? null,
            USERPROFILE: process.env.USERPROFILE ?? null,
            CLAUDE_CONFIG_DIR: process.env.CLAUDE_CONFIG_DIR ?? null,
            GIT_CONFIG_GLOBAL: process.env.GIT_CONFIG_GLOBAL ?? null,
            CLAUDE_PROFILES_ROOT: process.env.CLAUDE_PROFILES_ROOT ?? null,
        },
        exitStatus: shouldFail ? 2 : 0,
        diagnostic: shouldFail
            ? `fake-cli: forced failure for profile ${profileId}`
            : null,
        recordedAt: new Date().toISOString(),
    };

    if (evidencePath) {
        mkdirSync(dirname(evidencePath), { recursive: true });
        writeFileSync(evidencePath, `${JSON.stringify(record, null, 2)}\n`, 'utf8');
    }

    if (process.argv.includes('--version')) {
        process.stdout.write(`${FAKE_CLI_VERSION}\n`);
    } else {
        process.stdout.write(`fake-cli ok profile=${profileId}\n`);
    }

    if (shouldFail) {
        process.stderr.write(`${record.diagnostic}\n`);
        process.exit(2);
    }
    process.exit(0);
}

main();

export { FAKE_CLI_VERSION };
