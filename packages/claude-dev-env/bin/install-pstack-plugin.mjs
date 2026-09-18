import { spawnSync } from 'node:child_process';

export const PSTACK_MARKETPLACE_REPOSITORY = 'michael-denyer/pstack-claude';
export const PSTACK_MARKETPLACE_NAME = 'pstack-claude';
export const PSTACK_PLUGIN_IDENTIFIER = `pstack@${PSTACK_MARKETPLACE_NAME}`;
export const PSTACK_PLUGIN_HOSTS = Object.freeze(['claude', 'codex']);

export const PSTACK_PLUGIN_OPT_OUT_FLAG = '--no-pstack';
export const PSTACK_PLUGIN_OPT_OUT_VARIABLE = 'CDE_INSTALL_PSTACK';

const HOST_PLANS = Object.freeze({
    claude: Object.freeze({
        executable: 'claude',
        executableVariable: 'CDE_CLAUDE_EXECUTABLE',
        homeVariable: 'CLAUDE_CONFIG_DIR',
        commands: Object.freeze([
            Object.freeze(['plugin', 'marketplace', 'add', PSTACK_MARKETPLACE_REPOSITORY]),
            Object.freeze(['plugin', 'install', PSTACK_PLUGIN_IDENTIFIER]),
        ]),
    }),
    codex: Object.freeze({
        executable: 'codex',
        executableVariable: 'CDE_CODEX_EXECUTABLE',
        homeVariable: 'CODEX_HOME',
        commands: Object.freeze([
            Object.freeze(['plugin', 'marketplace', 'add', PSTACK_MARKETPLACE_REPOSITORY]),
            Object.freeze(['plugin', 'add', PSTACK_PLUGIN_IDENTIFIER]),
        ]),
    }),
});

/**
 * Read the marketplace and plugin commands one host installs pstack with.
 *
 * Claude Code and Codex publish the same marketplace under different plugin
 * verbs, so the command list belongs to the host rather than to the caller.
 *
 * @param {string} host Either `claude` or `codex`.
 * @returns {{executable: string, executableVariable: string, homeVariable: string,
 *   commands: ReadonlyArray<ReadonlyArray<string>>}} The host's install plan.
 */
export function pstackPluginPlan(host) {
    const plan = HOST_PLANS[host];
    if (!plan) {
        throw new Error(
            `Unsupported pstack plugin host ${host}: this installer knows ${PSTACK_PLUGIN_HOSTS.join(', ')}.`,
        );
    }
    return plan;
}

/**
 * Decide whether a full install also installs the pstack plugin.
 *
 * The step reaches the network for the marketplace repository. `--no-pstack`
 * on the command line, or `CDE_INSTALL_PSTACK=0` in the environment, turns it
 * off for an air-gapped or offline run.
 *
 * @param {string[]} [argumentList] The command-line arguments after the script.
 * @param {Record<string, string|undefined>} [environment] The process environment.
 * @returns {boolean} True when this run installs the pstack plugin.
 */
export function shouldInstallPstackPlugin(
    argumentList = process.argv.slice(2),
    environment = process.env,
) {
    if (argumentList.includes(PSTACK_PLUGIN_OPT_OUT_FLAG)) return false;
    return environment[PSTACK_PLUGIN_OPT_OUT_VARIABLE] !== '0';
}

/**
 * Build the process launch one platform needs to run a host command.
 *
 * Both hosts ship on Windows as a `.cmd` shim, and Node's synchronous spawn
 * rejects a batch file with `EINVAL` unless a shell runs it, so Windows goes
 * through `cmd.exe /d /s /c` with the whole command line as one verbatim
 * argument. The executable carries its own quotes inside that line, which is
 * why the line is passed verbatim rather than quoted again by Node. Every
 * other platform launches the executable directly.
 *
 * @param {string} executable The host command, a bare name or a path.
 * @param {string[]} commandArguments The arguments after the executable.
 * @param {string} [platform] The platform to build for.
 * @param {Record<string, string|undefined>} [environment] Supplies `ComSpec`.
 * @returns {{file: string, args: string[], windowsVerbatimArguments: boolean}} The launch.
 */
export function hostCommandInvocation(
    executable,
    commandArguments,
    platform = process.platform,
    environment = process.env,
) {
    if (platform !== 'win32') {
        return { file: executable, args: [...commandArguments], windowsVerbatimArguments: false };
    }
    const commandLine = [`"${executable}"`, ...commandArguments].join(' ');
    return {
        file: environment.ComSpec || 'cmd.exe',
        args: ['/d', '/s', '/c', `"${commandLine}"`],
        windowsVerbatimArguments: true,
    };
}

function runHostCommand(executable, commandArguments, options) {
    const invocation = hostCommandInvocation(executable, commandArguments);
    const spawned = spawnSync(invocation.file, invocation.args, {
        encoding: 'utf8',
        env: { ...process.env, ...options.environment },
        windowsVerbatimArguments: invocation.windowsVerbatimArguments,
    });
    return { status: spawned.status, stderr: spawned.stderr ?? '', error: spawned.error };
}

const COMMAND_NOT_FOUND_EXIT_CODE = 9009;
const COMMAND_NOT_FOUND_PATTERN = /is not recognized as an internal or external command/;

function namesAnAbsentCommand(outcome) {
    if (outcome.error?.code === 'ENOENT') return true;
    return outcome.status === COMMAND_NOT_FOUND_EXIT_CODE
        && COMMAND_NOT_FOUND_PATTERN.test(outcome.stderr ?? '');
}

function firstLine(text) {
    const trimmed = (text ?? '').trim();
    if (!trimmed) return '';
    return trimmed.split(/\r?\n/).filter(Boolean).at(-1);
}

function installForHost(host, homeDirectory, environment, runCommand) {
    const plan = pstackPluginPlan(host);
    const executable = environment[plan.executableVariable] || plan.executable;
    const commandEnvironment = { [plan.homeVariable]: homeDirectory };
    for (const commandArguments of plan.commands) {
        const outcome = runCommand(executable, [...commandArguments], {
            environment: commandEnvironment,
        });
        if (namesAnAbsentCommand(outcome)) {
            return {
                host,
                executable,
                status: 'skipped',
                warning: `${executable} is not on PATH, so pstack was not installed for ${host}.`,
            };
        }
        if (outcome.status !== 0 || outcome.error) {
            const detail = firstLine(outcome.stderr) || outcome.error?.message || `exit ${outcome.status}`;
            return {
                host,
                executable,
                status: 'failed',
                warning: `${executable} ${commandArguments.join(' ')} failed: ${detail}`,
            };
        }
    }
    return { host, executable, status: 'installed', warning: null };
}

/**
 * Install the pstack plugin from its marketplace into each host's own home.
 *
 * Each host is one member of the batch. A host without its command-line tool
 * is skipped and a host whose command fails is reported, so the rules, hooks,
 * and skills this run already wrote still reach their durable places. An
 * absent tool arrives as a spawn `ENOENT` on other platforms and as
 * `cmd.exe`'s command-not-found exit code on Windows, and both read as
 * skipped.
 *
 * @param {object} [options] Install targets.
 * @param {string} [options.claudeRoot] The managed Claude root to install into.
 * @param {string} [options.codexHome] The Codex home to install into.
 * @param {string[]} [options.hosts] The hosts to install. Defaults to both.
 * @param {Record<string, string|undefined>} [options.environment] The process environment.
 * @param {object} [dependencies] Seams for the command runner.
 * @returns {{status: string, hosts: object[], warning: string|null}} The outcome per host.
 */
export function installPstackPlugin(options = {}, dependencies = {}) {
    const environment = options.environment ?? process.env;
    const runCommand = dependencies.runCommand ?? runHostCommand;
    const homeDirectories = { claude: options.claudeRoot, codex: options.codexHome };
    const hosts = options.hosts ?? PSTACK_PLUGIN_HOSTS;
    const hostOutcomes = hosts.map(host => installForHost(
        host,
        homeDirectories[host],
        environment,
        runCommand,
    ));
    const failedCount = hostOutcomes.filter(outcome => outcome.status === 'failed').length;
    const installedCount = hostOutcomes.filter(outcome => outcome.status === 'installed').length;
    const status = failedCount > 0 ? 'failed' : (installedCount > 0 ? 'installed' : 'skipped');
    const warnings = hostOutcomes.map(outcome => outcome.warning).filter(Boolean);
    return { status, hosts: hostOutcomes, warning: warnings.join(' ') || null };
}
