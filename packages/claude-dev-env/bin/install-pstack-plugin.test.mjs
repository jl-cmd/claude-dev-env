import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
    PSTACK_MARKETPLACE_REPOSITORY,
    PSTACK_PLUGIN_HOSTS,
    PSTACK_PLUGIN_IDENTIFIER,
    hostCommandInvocation,
    installPstackPlugin,
    pstackPluginPlan,
    shouldInstallPstackPlugin,
} from './install-pstack-plugin.mjs';

function recordingRunner(outcomeForCommand = () => ({ status: 0, stderr: '' })) {
    const calls = [];
    return {
        calls,
        runCommand(executable, commandArguments, options) {
            calls.push({ executable, commandArguments, environment: options.environment });
            return outcomeForCommand(executable, commandArguments);
        },
    };
}

const ROOTS = { claudeRoot: '/managed/.claude', codexHome: '/managed/.codex' };

test('the Claude plan carries the two documented plugin commands', () => {
    const plan = pstackPluginPlan('claude');
    assert.equal(plan.executable, 'claude');
    assert.deepEqual(plan.commands, [
        ['plugin', 'marketplace', 'add', PSTACK_MARKETPLACE_REPOSITORY],
        ['plugin', 'install', PSTACK_PLUGIN_IDENTIFIER],
    ]);
});

test('the Codex plan adds the plugin with the Codex verb', () => {
    const plan = pstackPluginPlan('codex');
    assert.equal(plan.executable, 'codex');
    assert.deepEqual(plan.commands, [
        ['plugin', 'marketplace', 'add', PSTACK_MARKETPLACE_REPOSITORY],
        ['plugin', 'add', PSTACK_PLUGIN_IDENTIFIER],
    ]);
});

test('an unsupported host names the hosts this installer knows', () => {
    assert.throws(() => pstackPluginPlan('cursor'), /cursor/);
    assert.deepEqual(PSTACK_PLUGIN_HOSTS, ['claude', 'codex']);
});

test('each host installs into the managed root this run wrote', () => {
    const runner = recordingRunner();
    const outcome = installPstackPlugin(ROOTS, runner);
    assert.equal(outcome.status, 'installed');
    assert.deepEqual(runner.calls.map(call => [call.executable, ...call.commandArguments]), [
        ['claude', 'plugin', 'marketplace', 'add', PSTACK_MARKETPLACE_REPOSITORY],
        ['claude', 'plugin', 'install', PSTACK_PLUGIN_IDENTIFIER],
        ['codex', 'plugin', 'marketplace', 'add', PSTACK_MARKETPLACE_REPOSITORY],
        ['codex', 'plugin', 'add', PSTACK_PLUGIN_IDENTIFIER],
    ]);
    assert.equal(runner.calls[0].environment.CLAUDE_CONFIG_DIR, ROOTS.claudeRoot);
    assert.equal(runner.calls[2].environment.CODEX_HOME, ROOTS.codexHome);
});

test('an absent host command skips that host and leaves the other installed', () => {
    const runner = recordingRunner((executable) => (executable === 'codex'
        ? { status: null, error: Object.assign(new Error('spawn codex ENOENT'), { code: 'ENOENT' }) }
        : { status: 0, stderr: '' }));
    const outcome = installPstackPlugin(ROOTS, runner);
    assert.equal(outcome.hosts.find(host => host.host === 'claude').status, 'installed');
    const codex = outcome.hosts.find(host => host.host === 'codex');
    assert.equal(codex.status, 'skipped');
    assert.match(codex.warning, /codex/);
    assert.equal(runner.calls.filter(call => call.executable === 'codex').length, 1);
});

test('a failing command reports that host and still installs the next one', () => {
    const runner = recordingRunner((executable, commandArguments) => (
        executable === 'claude' && commandArguments[1] === 'marketplace'
            ? { status: 1, stderr: 'marketplace unreachable' }
            : { status: 0, stderr: '' }));
    const outcome = installPstackPlugin(ROOTS, runner);
    assert.equal(outcome.status, 'failed');
    const claude = outcome.hosts.find(host => host.host === 'claude');
    assert.equal(claude.status, 'failed');
    assert.match(claude.warning, /marketplace unreachable/);
    assert.equal(outcome.hosts.find(host => host.host === 'codex').status, 'installed');
    assert.equal(runner.calls.filter(call => call.executable === 'claude').length, 1);
});

test('an executable override replaces the host command for that host only', () => {
    const runner = recordingRunner();
    installPstackPlugin(
        { ...ROOTS, environment: { CDE_CODEX_EXECUTABLE: '/opt/codex/bin/codex' } },
        runner,
    );
    assert.deepEqual([...new Set(runner.calls.map(call => call.executable))], [
        'claude',
        '/opt/codex/bin/codex',
    ]);
});

test('the opt-out flag and variable both turn the step off', () => {
    assert.equal(shouldInstallPstackPlugin([], {}), true);
    assert.equal(shouldInstallPstackPlugin(['--no-pstack'], {}), false);
    assert.equal(shouldInstallPstackPlugin([], { CDE_INSTALL_PSTACK: '0' }), false);
    assert.equal(shouldInstallPstackPlugin([], { CDE_INSTALL_PSTACK: '1' }), true);
});

test('a selected host list installs only that host', () => {
    const runner = recordingRunner();
    const outcome = installPstackPlugin({ ...ROOTS, hosts: ['codex'] }, runner);
    assert.deepEqual(outcome.hosts.map(host => host.host), ['codex']);
    assert.deepEqual([...new Set(runner.calls.map(call => call.executable))], ['codex']);
});

test('a non-Windows platform launches the host command directly', () => {
    const invocation = hostCommandInvocation('claude', ['plugin', 'install', PSTACK_PLUGIN_IDENTIFIER], 'linux');
    assert.deepEqual(invocation, {
        file: 'claude',
        args: ['plugin', 'install', PSTACK_PLUGIN_IDENTIFIER],
        windowsVerbatimArguments: false,
    });
});

test('Windows launches the host command through cmd.exe, which alone can run a .cmd shim', () => {
    const invocation = hostCommandInvocation(
        'claude', ['plugin', 'install', PSTACK_PLUGIN_IDENTIFIER], 'win32', { ComSpec: 'C:\\Windows\\system32\\cmd.exe' },
    );
    assert.equal(invocation.file, 'C:\\Windows\\system32\\cmd.exe');
    assert.deepEqual(invocation.args, [
        '/d',
        '/s',
        '/c',
        `""claude" plugin install ${PSTACK_PLUGIN_IDENTIFIER}"`,
    ]);
    assert.equal(invocation.windowsVerbatimArguments, true);
});

test('a Windows executable path holding a space stays one quoted token', () => {
    const invocation = hostCommandInvocation(
        'C:\\Program Files\\nodejs\\claude.cmd',
        ['plugin', 'marketplace', 'add', PSTACK_MARKETPLACE_REPOSITORY],
        'win32',
    );
    assert.equal(invocation.file, 'cmd.exe');
    assert.equal(
        invocation.args.at(-1),
        `""C:\\Program Files\\nodejs\\claude.cmd" plugin marketplace add ${PSTACK_MARKETPLACE_REPOSITORY}"`,
    );
});

test("cmd.exe's command-not-found exit code reads as an absent host, not a failure", () => {
    const runner = recordingRunner((executable) => (executable === 'codex'
        ? {
            status: 9009,
            stderr: "'codex' is not recognized as an internal or external command,\noperable program or batch file.",
        }
        : { status: 0, stderr: '' }));
    const outcome = installPstackPlugin(ROOTS, runner);
    const codex = outcome.hosts.find(host => host.host === 'codex');
    assert.equal(codex.status, 'skipped');
    assert.equal(outcome.status, 'installed');
    assert.equal(runner.calls.filter(call => call.executable === 'codex').length, 1);
});

test('a non-zero exit that is not command-not-found still reads as a failure', () => {
    const runner = recordingRunner(() => ({ status: 9009, stderr: 'the marketplace rejected the catalog' }));
    const outcome = installPstackPlugin({ ...ROOTS, hosts: ['claude'] }, runner);
    assert.equal(outcome.hosts[0].status, 'failed');
    assert.match(outcome.hosts[0].warning, /rejected the catalog/);
});
