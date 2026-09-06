import { existsSync, readFileSync, realpathSync, renameSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export function continuityHookConfiguration(host, script) {
    if (host === 'cursor') {
        throw new Error('Cursor automatic activation is unsupported: beforeSubmitPrompt has no agent-context output, sessionStart is fire-and-forget, and preCompact is observational. No Cursor settings changed.');
    }
    if (!['claude', 'codex'].includes(host)) throw new Error(`Unsupported host ${host}`);
    if (/[\r\n"`$%]/.test(script)) throw new Error('Hook script path contains shell expansion characters');
    const command = `node "${script.replace(/\\/g, '/')}" hook ${host}`;
    const events = host === 'claude' ? ['UserPromptSubmit', 'UserPromptExpansion', 'SessionStart'] : ['UserPromptSubmit', 'SessionStart'];
    return Object.fromEntries(events.map(event => [event, [{
        ...(event === 'SessionStart' ? { matcher: host === 'claude' ? 'startup|resume|compact|clear|fork' : 'startup|resume|compact|clear' } : {}),
        ...(event === 'UserPromptExpansion' ? { matcher: '^(pstack:)?poteto-mode$|^(claude-dev-env:)?session-continuity$' } : {}),
        hooks: [{ type: 'command', command, timeout: 10 }],
    }]]));
}

export function mergeContinuityHooks(existing, host, script) {
    const additions = continuityHookConfiguration(host, script);
    const result = structuredClone(existing);
    result.hooks ||= {};
    for (const [event, groups] of Object.entries(additions)) {
        const current = result.hooks[event] || [];
        for (const group of current) {
            for (const hook of group.hooks || []) {
                if (hook.command?.includes('/session-continuity/continuity.mjs') && hook.command !== groups[0].hooks[0].command) {
                    throw new Error('Another continuity installation owns this host config. Select its profile or remove that installation explicitly.');
                }
            }
        }
        const kept = current.flatMap(group => {
            const hooks = (group.hooks || []).filter(hook => hook.command !== groups[0].hooks[0].command);
            return hooks.length ? [{ ...group, hooks }] : [];
        });
        result.hooks[event] = kept.concat(groups);
    }
    return result;
}

async function main() {
    const requested = process.argv.slice(2);
    const selected = requested.length ? requested : ['claude', 'codex'];
    if (selected.some(host => !['claude', 'codex'].includes(host))) continuityHookConfiguration(selected.find(host => !['claude', 'codex'].includes(host)), '');
    const { resolveInstallRoot } = await import('./resolve-install-root.mjs');
    const roots = resolveInstallRoot();
    const script = join(roots.skillsInstallDirectory, 'session-continuity', 'continuity.mjs');
    if (!existsSync(script) || !existsSync(join(dirname(script), 'SKILL.md'))) {
        throw new Error('Run the full claude-dev-env installer from this checkout first so the companion is in the canonical agents home.');
    }
    const paths = { claude: join(roots.managedRoot, 'settings.json'), codex: join(dirname(roots.codexRulesInstallDirectory), 'hooks.json') };
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
    console.log('Review and trust the new hooks in each host. Cursor remains unsupported; no Cursor settings changed.');
}

if (process.argv[1] && resolve(realpathSync(process.argv[1])) === fileURLToPath(import.meta.url)) {
    main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
