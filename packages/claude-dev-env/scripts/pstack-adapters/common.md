# Pstack compatibility

Apply this mapping to the upstream workflow below. User instructions and host permissions stay in charge.

Determine the active host from the session's native tools. Read host-claude.md, host-codex.md, or host-cursor.md beside this file for the active host. Read pstack-host-mapping.md and pstack-models.md beside this file before delegation. Those files are copied from claude-dev-env's existing rules into this immutable release. Run the selectorPath recorded in release.json and supply its preferencesDirectory in the selector input. This overrides the old global selector path. Model preferences remain outside the release.

Read the installed inventory in release.json for exact skill identities. Pstack skills use the `pstack:<slug>` plugin namespace. A pstack request for how, /how, or pstack:how means pstack:how. Cursor-team-kit skills keep flat component-prefixed names, so a request for deslop means cursor-team-kit-deslop. Resolve all other skill names through the inventory. Read each leaf skill in full when it applies. Keep each skill's scripts, references, playbooks, and agent definitions at its recorded source root.

Every delegation prompt must include this compatibility file's absolute path, the active host file's absolute path, the selected skill's absolute path, and the requested upstream agent definition's absolute path when present. Tell the child to read them before working and to put the complete findings and evidence in its final message. The child receives the same host and model mapping as the parent.

Treat upstream model identifiers as role preferences. Use only models and arguments accepted by the native tool in this session. Preserve required independence and model diversity. Report a missing capability when the session cannot supply the required independent panel. Use the native tool's supported concurrency and wait operations.

For setup-pstack, configure only the current host's model preference file described in pstack-models.md. Keep that file outside this release. The Cursor .mdc output is a Cursor rule, not a cross-host model configuration.

For create-skill, use Cursor's built-in skill on Cursor and cde-create-skill on Claude or Codex. For control-cli and control-ui, load the corresponding installed cursor-team-kit skill and use native terminal or browser tools. Check that the required CLI, browser, credentials, and permissions exist before executing its steps. State an unavailable dependency explicitly. Never claim an unattended browser or remote session ran from a filesystem check.

Updates are prepared outside the active release. Follow absolute paths into the release named in this entry point for the rest of this task. Preserve supporting files and scripts, including executable modes and licenses.
