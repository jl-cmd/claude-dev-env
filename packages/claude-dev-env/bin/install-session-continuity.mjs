import { existsSync, readFileSync, realpathSync, renameSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const supportedHosts = ['claude', 'codex', 'cursor'];

export function continuityHookConfiguration(host, script) {
    if (!supportedHosts.includes(host)) throw new Error(`Unsupported host ${host}`);
    if (/[\r\n"`$%]/.test(script)) throw new Error('Hook script path contains shell expansion characters');
    const command = `node "${script.replace(/\\/g, '/')}" hook ${host}`;
    if (host === 'cursor') {
        return Object.fromEntries(['sessionStart', 'beforeSubmitPrompt', 'preCompact', 'postToolUse'].map(event => [event, [{ command }]]));
    }
    const events = host === 'claude' ? ['UserPromptSubmit', 'UserPromptExpansion', 'SessionStart'] : ['UserPromptSubmit', 'SessionStart'];
    return Object.fromEntries(events.map(event => [event, [{
        ...(event === 'SessionStart' ? { matcher: host === 'claude' ? 'startup|resume|compact|clear|fork' : 'startup|resume|compact|clear' } : {}),
        ...(event === 'UserPromptExpansion' ? { matcher: '^(pstack:)?poteto-mode$|^(claude-dev-env:)?session-continuity$' } : {}),
        hooks: [{ type: 'command', command, timeout: 10 }],
    }]]));
}

export function mergeContinuityHooks(existing, host, script) {
    const additions = continuityHookConfiguration(host, script);
    const mergedConfiguration = structuredClone(existing);
    if (host === 'cursor') mergedConfiguration.version = 1;
    mergedConfiguration.hooks ||= {};
    for (const [event, groups] of Object.entries(additions)) {
        const current = mergedConfiguration.hooks[event] || [];
        const command = host === 'cursor' ? groups[0].command : groups[0].hooks[0].command;
        for (const entry of current) {
            for (const hook of entry.hooks || [entry]) {
                if (hook.command?.includes('/session-continuity/continuity.mjs') && hook.command !== command) {
                    throw new Error('Another continuity installation owns this host config. Select its profile or remove that installation explicitly.');
                }
            }
        }
        const kept = current.flatMap(entry => {
            if (host === 'cursor') return entry.command === command ? [] : [entry];
            const hooks = (entry.hooks || []).filter(hook => hook.command !== command);
            return hooks.length ? [{ ...entry, hooks }] : [];
        });
        mergedConfiguration.hooks[event] = kept.concat(groups);
    }
    return mergedConfiguration;
}

async function main() {
    const requested = process.argv.slice(2);
    const selected = requested.length ? requested : supportedHosts;
    const unsupported = selected.find(host => !supportedHosts.includes(host));
    if (unsupported) throw new Error(`Unsupported host ${unsupported}`);
    const { resolveInstallRoot } = await import('./resolve-install-root.mjs');
    const roots = resolveInstallRoot();
    const script = join(roots.skillsInstallDirectory, 'session-continuity', 'continuity.mjs');
    if (!existsSync(script) || !existsSync(join(dirname(script), 'SKILL.md'))) {
        throw new Error('Run the full claude-dev-env installer from this checkout first so the companion is in the canonical agents home.');
    }
    const paths = {
        claude: join(roots.managedRoot, 'settings.json'),
        codex: join(dirname(roots.codexRulesInstallDirectory), 'hooks.json'),
        cursor: join(roots.cursorInstallDirectory, 'hooks.json'),
    };
    const plans = selected.map(host => {
        const path = paths[host];
        if (!existsSync(dirname(path))) throw new Error(`Host config directory is absent: ${dirname(path)}`);
        const existing = existsSync(path) ? readFileSync(path, 'utf8') : null;
        return { path, existing, content: JSON.stringify(mergeContinuityHooks(existing ? JSON.parse(existing) : {}, host, script), null, 2) + '\n' };
    });
    for (const plan of plans) {
        if (plan.existing === plan.content) { console.log(`Already configured: ${plan.path}`); continue; }
        if (plan.existing !== null) {
            const backup = `${plan.path}.before-session-continuity`;
            if (!existsSync(backup)) writeFileSync(backup, plan.existing, { flag: 'wx', mode: 0o600 });
        }
        const current = existsSync(plan.path) ? readFileSync(plan.path, 'utf8') : null;
        if (current !== plan.existing) throw new Error(`Config changed during setup: ${plan.path}. Rerun setup.`);
        const temporary = `${plan.path}.continuity-${process.pid}.tmp`;
        writeFileSync(temporary, plan.content, { flag: 'wx', mode: 0o600 });
        renameSync(temporary, plan.path);
        if (readFileSync(plan.path, 'utf8') !== plan.content) throw new Error(`Config read-back mismatch: ${plan.path}`);
        console.log(`Configured and read back: ${plan.path}`);
    }
    console.log('Review and trust the new hooks in each host.');
}

if (process.argv[1] && resolve(realpathSync(process.argv[1])) === fileURLToPath(import.meta.url)) {
    main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
