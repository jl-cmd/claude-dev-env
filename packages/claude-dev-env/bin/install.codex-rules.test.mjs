import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { execFileSync } from 'node:child_process';
import {
    mkdtempSync,
    mkdirSync,
    writeFileSync,
    readFileSync,
    existsSync,
    rmSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
    resolveInstallRoot,
    isAllowedInstallDestination,
} from './resolve-install-root.mjs';
import {
    CODEX_HOME_ENVIRONMENT_VARIABLE,
    CODEX_RULES_DIRECTORY_NAME,
    CODEX_RULES_PACKAGE_DIRECTORY_NAME,
    CODEX_RULES_SHIPPED_FILE_NAME,
    DEFAULT_CODEX_DIRECTORY_NAME,
} from './install-constants.mjs';
import {
    CONTENT_DIRECTORIES,
    detectPython,
    INSTALL_GROUPS,
    pythonFileAndPrefixArguments,
} from './install.mjs';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const INSTALLER_PATH = join(THIS_DIRECTORY, 'install.mjs');
const PACKAGE_DIRECTORY = dirname(THIS_DIRECTORY);
const INSTALLER_PROCESS_TIMEOUT_MS = 60_000;
const SHIPPED_RULES_SOURCE_PATH = join(
    PACKAGE_DIRECTORY,
    CODEX_RULES_PACKAGE_DIRECTORY_NAME,
    CODEX_RULES_SHIPPED_FILE_NAME,
);
const BLOCKING_HOOKS_DIRECTORY = join(PACKAGE_DIRECTORY, 'hooks', 'blocking');
const PYTHON_PII_SCAN_SCRIPT = [
    'import json',
    'import sys',
    'from dataclasses import asdict',
    'from pii_scanner import scan_text_for_pii',
    'all_findings = scan_text_for_pii(sys.stdin.read())',
    "home_path_findings = [asdict(each_finding) for each_finding in all_findings if each_finding.category == 'home-path']",
    'print(json.dumps(home_path_findings))',
].join('\n');

function runInstaller(homeDirectory, extraArguments) {
    return execFileSync('node', [INSTALLER_PATH, ...extraArguments], {
        cwd: PACKAGE_DIRECTORY,
        encoding: 'utf8',
        env: {
            ...process.env,
            HOME: homeDirectory,
            USERPROFILE: homeDirectory,
            GIT_CONFIG_GLOBAL: join(homeDirectory, '.gitconfig'),
            [CODEX_HOME_ENVIRONMENT_VARIABLE]: join(homeDirectory, DEFAULT_CODEX_DIRECTORY_NAME),
        },
        timeout: INSTALLER_PROCESS_TIMEOUT_MS,
    });
}

function scanTextWithProductionPiiScanner(scannedText) {
    const temporaryDirectory = mkdtempSync(join(tmpdir(), 'cdev-pii-scan-'));
    try {
        const detectedPythonCommand = detectPython();
        if (!detectedPythonCommand) {
            throw new Error('No usable Python interpreter found for the PII scanner test');
        }
        const { file, prefixArguments } = pythonFileAndPrefixArguments(
            detectedPythonCommand,
        );
        const scannerJson = execFileSync(
            file,
            [...prefixArguments, '-c', PYTHON_PII_SCAN_SCRIPT],
            {
                cwd: PACKAGE_DIRECTORY,
                encoding: 'utf8',
                env: {
                    ...process.env,
                    PYTHONPATH: BLOCKING_HOOKS_DIRECTORY,
                    CLAUDE_LOCAL_IDENTITY_PATH: join(
                        temporaryDirectory,
                        'missing-local-identity.json',
                    ),
                },
                input: scannedText,
                timeout: INSTALLER_PROCESS_TIMEOUT_MS,
            },
        );
        return JSON.parse(scannerJson);
    } finally {
        rmSync(temporaryDirectory, { recursive: true, force: true });
    }
}

test('CONTENT_DIRECTORIES omits codex-rules because that tree installs to the Codex home', () => {
    assert.equal(CONTENT_DIRECTORIES.includes(CODEX_RULES_PACKAGE_DIRECTORY_NAME), false);
});

test('the core group installs Codex exec-policy files', () => {
    assert.equal(INSTALL_GROUPS.core.includeCodexRules, true);
});

test('resolveInstallRoot names ~/.codex/rules and allows files under it', () => {
    const homeDirectory = join(tmpdir(), 'cdev-codex-rules-home');
    const resolution = resolveInstallRoot({
        homeDirectory,
        environment: {},
        explicitTarget: null,
    });
    const expectedDirectory = join(homeDirectory, DEFAULT_CODEX_DIRECTORY_NAME, CODEX_RULES_DIRECTORY_NAME);
    assert.equal(resolution.codexRulesInstallDirectory, expectedDirectory);
    assert.equal(
        isAllowedInstallDestination(join(expectedDirectory, CODEX_RULES_SHIPPED_FILE_NAME), resolution),
        true,
    );
    assert.equal(
        isAllowedInstallDestination(join(homeDirectory, '.ssh', 'id_rsa'), resolution),
        false,
    );
});

test('CODEX_HOME relocates the Codex rules destination', () => {
    const homeDirectory = join(tmpdir(), 'cdev-codex-home-default');
    const relocatedHome = join(tmpdir(), 'cdev-codex-home-relocated');
    const resolution = resolveInstallRoot({
        homeDirectory,
        environment: { [CODEX_HOME_ENVIRONMENT_VARIABLE]: relocatedHome },
        explicitTarget: null,
    });
    assert.equal(
        resolution.codexRulesInstallDirectory,
        join(relocatedHome, CODEX_RULES_DIRECTORY_NAME),
    );
});

test('a full install copies shipped Codex rules and leaves a local default.rules in place', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-codex-install-'));
    try {
        const userRulesPath = join(
            homeDirectory,
            DEFAULT_CODEX_DIRECTORY_NAME,
            CODEX_RULES_DIRECTORY_NAME,
            'default.rules',
        );
        mkdirSync(dirname(userRulesPath), { recursive: true });
        writeFileSync(userRulesPath, 'prefix_rule(pattern=["echo", "hi"], decision="allow")\n');

        runInstaller(homeDirectory, []);

        const installedRulesPath = join(
            homeDirectory,
            DEFAULT_CODEX_DIRECTORY_NAME,
            CODEX_RULES_DIRECTORY_NAME,
            CODEX_RULES_SHIPPED_FILE_NAME,
        );
        assert.equal(existsSync(installedRulesPath), true);
        assert.equal(
            readFileSync(installedRulesPath, 'utf8'),
            readFileSync(SHIPPED_RULES_SOURCE_PATH, 'utf8'),
        );
        assert.equal(
            readFileSync(userRulesPath, 'utf8'),
            'prefix_rule(pattern=["echo", "hi"], decision="allow")\n',
        );
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('the shipped Codex rules file has no production-scanner home-path findings', () => {
    const allHomePathFindings = scanTextWithProductionPiiScanner(
        readFileSync(SHIPPED_RULES_SOURCE_PATH, 'utf8'),
    );
    assert.deepEqual(
        allHomePathFindings,
        [],
        `home-path findings: ${JSON.stringify(allHomePathFindings, null, 2)}`,
    );
});

test('--only journal skips Codex rules; --only core copies them', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-codex-groups-'));
    try {
        const installedRulesPath = join(
            homeDirectory,
            DEFAULT_CODEX_DIRECTORY_NAME,
            CODEX_RULES_DIRECTORY_NAME,
            CODEX_RULES_SHIPPED_FILE_NAME,
        );
        runInstaller(homeDirectory, ['--only', 'journal']);
        assert.equal(existsSync(installedRulesPath), false);

        runInstaller(homeDirectory, ['--only', 'core']);
        assert.equal(existsSync(installedRulesPath), true);
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});

test('uninstall removes the shipped Codex rules file and leaves default.rules', () => {
    const homeDirectory = mkdtempSync(join(tmpdir(), 'cdev-codex-uninstall-'));
    try {
        const rulesDirectory = join(
            homeDirectory,
            DEFAULT_CODEX_DIRECTORY_NAME,
            CODEX_RULES_DIRECTORY_NAME,
        );
        const userRulesPath = join(rulesDirectory, 'default.rules');
        mkdirSync(rulesDirectory, { recursive: true });
        writeFileSync(userRulesPath, 'keep-me\n');

        runInstaller(homeDirectory, []);
        runInstaller(homeDirectory, ['--uninstall']);

        const installedRulesPath = join(rulesDirectory, CODEX_RULES_SHIPPED_FILE_NAME);
        assert.equal(existsSync(installedRulesPath), false);
        assert.equal(readFileSync(userRulesPath, 'utf8'), 'keep-me\n');
    } finally {
        rmSync(homeDirectory, { recursive: true, force: true });
    }
});
