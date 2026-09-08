# Pstack host compatibility

Apply this file before the upstream workflow. Keep the user's instructions and the
host's permissions in charge. Identify the active host from the current session and
its tool definitions. A directory or environment variable does not identify a host.

## Tools and delegation

| Upstream request | Claude Code | Codex | Cursor |
| --- | --- | --- | --- |
| Read a skill | Skill tool or read its installed SKILL.md | Load the named skill or read its SKILL.md | Load the named skill or read its SKILL.md |
| Task | The exposed Agent or Task tool | The exposed spawn_agent tool, then wait and close tools | The exposed native subagent tool |
| AskQuestion | The exposed question tool | The exposed user-input tool or a direct question | The exposed question tool |
| Shell, terminal, PTY | Bash and available terminal tools | exec_command and write_stdin when exposed | The exposed shell and terminal tools |
| Browser or UI control | Available browser, Playwright or CDP tools | Available browser, Playwright or CDP tools | Available browser, Playwright or CDP tools |

Read the native tool schema before calling it. Pass only supported fields. Preserve
parallel work through native concurrent calls and wait for their results. Use
background execution only when the native tool supports it with the needed tools.

For a poteto-agent or comment-sicko request, use the installed native agent when it
is available. Otherwise use a supported general-purpose agent and include the
matching upstream agent file as instructions. Carry the complete role instructions
for any other upstream agent type into a supported native agent.

Every child prompt includes PSTACK_RELEASE, the absolute release directory provided
by the invoking skill, and asks the child to read this compatibility file, the model
policy, and its upstream agent or workflow file before working. Ask for all findings,
checks and evidence in the final message. The parent reviews that message and the
actual changes. Intermediate child messages may never reach the parent.

If delegation is unavailable, report the missing capability. A sequential parent
pass is a different procedure and needs the user's agreement when the workflow
requires independent agents. Likewise, a same-model panel is not a diverse-model
panel. Preserve the workflow's independent-review and diversity requirements.

## Models and setup

Read rules/pstack-host-mapping.md and rules/pstack-models.md in this release.
Use the release paths in this file in place of their global installation paths.
The portable role policy replaces
upstream Cursor model defaults. The selector is scripts/select_pstack_models.mjs
inside this release. Run it before each delegation with the active tool's confirmed
inventory. Pass preferencesDirectory as the preferences directory beside releases
in the installation root. Keep models in pstack-model-preferences.<host>.json there.

The selector returns a model preference, not permission to invent a tool parameter.
Use a returned model only through a mechanism the current native tool supports.
Omit the model for a supported parent-inheritance choice. Preserve the selector's
capability and distinct-model checks. Stop when the requested choice is unavailable.

For setup-pstack, read the upstream setup workflow for its role questions, then save
only the active host's preference JSON in that preferences directory. This replaces
the upstream step that writes ~/.cursor/rules/pstack-models.mdc. Keep the other hosts'
preferences unchanged. Choose actual session models rather than guessed model IDs.

## Files, transcripts and dependencies

The invoking wrapper names an immutable upstream SKILL.md. Resolve its relative
scripts, references and playbooks from that source directory, not the wrapper.
The complete upstream pstack and cursor-team-kit directories remain in this release.
Read sibling skills from those directories or the installed wrappers. A pstack:
namespace and a bare skill name refer to the same workflow. The host's skill menu
determines the invocation syntax.

Resolve transcript searches through the active host's documented session location.
Search only the relevant workspace or session. Ask for missing evidence rather than
inventing Cursor transcript paths on another host.

cursor-team-kit:deslop maps to the bundled deslop workflow. For control-cli, use the
bundled workflow with the active host's real shell and terminal tools. For control-ui,
use the bundled workflow with real browser or UI automation. Check tool access first.
A screenshot, test stub or source inspection does not prove an interactive flow. If
a needed PTY, browser, application or credential is absent, name that missing item
and mark the corresponding runtime check unverified.

create-skill maps to the installed pstack create-skill compatibility workflow. In
Codex, the built-in skill-creator may be used when available. Keep project skills in
.claude/skills, with discovery links under .agents/skills where needed. Keep supporting
files with each skill and test an actual invocation on its intended host.

## Session version

Use the invoking skill's PSTACK_RELEASE for the entire task, including child prompts.
Updates create another immutable release. Start new work through cde-pstack launch
so active processes protect their release from a simultaneous publication change.
Resume hooks keep the recorded session release. Report the upstream commit and the
adapter digest when diagnosing an installation. A filesystem verification proves
installation integrity; a live host invocation proves runtime behavior.
