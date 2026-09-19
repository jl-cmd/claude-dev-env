# Correctness properties

This file lists the correctness properties for the audit. The machine-readable record is `data/properties.tsv`. `test_properties.py` checks that record.

## How to read a property

- The repository is the target of the audit. The repository supplies no correctness yardstick.
- Each sourced property cites one outside source by its source-lock id. The quote is the exact text from that source.
- A property with the source id `house` has no outside source. A house property records an observation only. A house property cannot establish correctness and cannot keep a component.
- Correctness is a floor. A component that passes every property still needs a measured contribution or a proven necessity.
- Strength `normative` means the source defines platform or tool behavior. Strength `recommended` or `advisory` means the source gives guidance. Do not grade guidance as a protocol requirement.
- The classes come from the `kind` column of `data/inventory.tsv`.
- Revision 1 applies to every row. A change to a source-lock entry needs a new revision of each property that cites the entry.

## Fields not yet filled

The plan asks for a calibration set for each property: a passing control, an invalid case, and a valid near-neighbor. Only the properties with an existing check have that set today. The hook harness holds the set for the hook properties.

## Properties

### P-HOOK-01

A hook that claims to block an input should exit with code 2 or return a deny decision for that input.

- Source: `W1`, section "Exit code 2", strength normative.
- Quote: "Exit 2 means a blocking error."
- Classes: `hook_module`.
- Observe: exit code. Run the hook with the claimed input on stdin and read the exit code.
- Check: tests/audit/hooks/test_hook_harness.py.

### P-HOOK-02

A hook that exits 0 with no output should leave the tool call to the normal permission flow.

- Source: `W1`, section "Exit code 0", strength normative.
- Quote: "Exit code 0 with no output means the hook has no decision to report, so the tool call continues through the normal [permission flow](/docs/en/permissions)."
- Classes: `hook_module`.
- Observe: exit code; stdout. Run the hook with the valid near-neighbor input and read exit code and stdout.
- Check: tests/audit/hooks/test_hook_harness.py.

### P-HOOK-03

A hook should signal through exit codes alone or through JSON on exit 0, not both.

- Source: `W1`, section "JSON output", strength normative.
- Quote: "Choose one approach per hook: either use exit codes alone for signaling, or exit 0 and print JSON for structured control."
- Classes: `hook_module`.
- Observe: exit code; stdout. Run the hook on a blocking input and fail when stdout holds JSON and the exit code is 2.
- Check: none today.

### P-HOOK-04

A PreToolUse hook that denies through JSON should put permissionDecision inside hookSpecificOutput.

- Source: `W1`, section "Decision control", strength normative.
- Quote: "`permissionDecision` (allow/deny/ask/defer), `permissionDecisionReason`"
- Classes: `hook_module`.
- Observe: stdout. Parse the hook stdout and read hookSpecificOutput.permissionDecision.
- Check: tests/audit/hooks/test_hook_harness.py.

### P-HOOK-05

A hook that must block should print JSON that passes schema validation, because invalid JSON lets the action proceed.

- Source: `W1`, section "Exit code 0", strength normative.
- Quote: "exit 0 with a parsed object that fails schema validation is a non-blocking error: the action proceeds"
- Classes: `hook_module`.
- Observe: stdout; trace. Validate the hook stdout against the documented decision fields for its event.
- Check: none today.

### P-HOOK-06

A hook should give the same result whatever order the other matching hooks run in.

- Source: `W1`, section "Hook handlers", strength normative.
- Quote: "All matching hooks run in parallel. If you define the same handler in more than one settings file, it runs once."
- Classes: `hook_module`, `settings_manifest`.
- Observe: exit code; file. Run each hook alone in a clean directory and compare with the grouped run.
- Check: none today.

### P-SKILL-01

A skill should carry a description that says what the skill does and when to use it.

- Source: `W2`, section "Frontmatter reference", strength recommended.
- Quote: "What the skill does and when to use it. Claude uses this to decide when to apply the skill."
- Classes: `skill`.
- Observe: file. Parse SKILL.md frontmatter and read the description field.
- Check: none today.

### P-SKILL-02

A skill description plus when_to_use text should fit in 1,536 characters.

- Source: `W2`, section "Frontmatter reference", strength normative.
- Quote: "combined `description` and `when_to_use` text is truncated at 1,536 characters in the skill listing to reduce context usage."
- Classes: `skill`.
- Observe: file. Count the characters of description plus when_to_use in the frontmatter.
- Check: none today.

### P-SKILL-03

A SKILL.md file should stay under 500 lines.

- Source: `W2`, section "Add supporting files", strength advisory.
- Quote: "Keep `SKILL.md` under 500 lines. Move detailed reference material to separate files."
- Classes: `skill`.
- Observe: file. Read the lines column of the inventory row for each SKILL.md.
- Check: none today.

### P-SKILL-04

A skill description should name the contexts that trigger the skill.

- Source: `S-MARKET-SKILLCREATOR`, section "Anatomy of a skill", strength advisory.
- Quote: "include both what the skill does AND specific contexts for when to use it"
- Classes: `skill`.
- Observe: trace. Send a trigger prompt and a must-not-trigger prompt and read which skill loaded.
- Check: none today.

### P-MEM-01

An instruction file loaded at launch should stay under 200 lines.

- Source: `S-MEMORY`, section "Write effective instructions", strength advisory.
- Quote: "target under 200 lines per CLAUDE.md file. Longer files consume more context and reduce adherence."
- Classes: `instruction_file`.
- Observe: file. Read the lines column of the inventory row.
- Check: none today.

### P-MEM-02

An import chain between instruction files should be four hops deep at most.

- Source: `S-MEMORY`, section "Import additional files", strength normative.
- Quote: "Imported files can recursively import other files, with a maximum depth of four hops."
- Classes: `instruction_file`, `rule`.
- Observe: file. Follow each @path import and count the hops.
- Check: none today.

### P-MEM-03

A rule file with no paths field should appear in the session context at launch.

- Source: `S-MEMORY`, section "Path-specific rules", strength normative.
- Quote: "Rules without a `paths` field are loaded unconditionally and apply to all files."
- Classes: `rule`.
- Observe: trace. Start a session in an arm that holds the rule and read the loaded-instruction list.
- Check: none today.

### P-AGENT-01

An agent name should use lowercase letters and hyphens only.

- Source: `S-AGENTS`, section "Supported frontmatter fields", strength normative.
- Quote: "Unique identifier using lowercase letters and hyphens."
- Classes: `agent`.
- Observe: file. Parse the agent frontmatter and match the name against lowercase letters and hyphens.
- Check: none today.

### P-AGENT-02

An agent should carry a description that says when to delegate to it.

- Source: `S-AGENTS`, section "Supported frontmatter fields", strength normative.
- Quote: "When Claude should delegate to this subagent"
- Classes: `agent`.
- Observe: file. Parse the agent frontmatter and read the description field.
- Check: none today.

### P-PLUGIN-01

A plugin manifest, when present, should hold a name field.

- Source: `W3`, section "Plugin manifest schema", strength normative.
- Quote: "If you include a manifest, `name` is the only required field."
- Classes: `settings_manifest`.
- Observe: file. Parse each plugin.json and read the name key.
- Check: none today.

### P-CODEX-01

A Codex instruction file should hold content.

- Source: `W7`, section "Troubleshooting", strength normative.
- Quote: "Ensure instruction files contain content; Codex ignores empty files."
- Classes: `codex_projection`, `instruction_file`.
- Observe: file. Read the bytes column of the inventory row for each AGENTS.md.
- Check: none today.

### P-CODEX-02

The combined Codex instruction files should fit under the 32 KiB default limit.

- Source: `W7`, section "How Codex discovers guidance", strength normative.
- Quote: "Codex skips empty files and stops adding files once the combined size reaches the limit defined by"
- Classes: `codex_projection`, `instruction_file`.
- Observe: file. Sum the bytes of the AGENTS.md chain from the root to the working directory.
- Check: none today.

### P-CURSOR-01

A Cursor project rule should use the .mdc extension.

- Source: `W9`, section "Rule file format", strength normative.
- Quote: "Project rules must use the `.mdc` extension."
- Classes: `cursor_projection`.
- Observe: file. List the files under .cursor/rules and read each extension.
- Check: none today.

### P-CI-01

A required check should report a successful, skipped, or neutral status before a merge.

- Source: `W10`, section "Require status checks before merging", strength normative.
- Quote: "Required status checks must have a `successful`, `skipped`, or `neutral` status before collaborators can make changes to a protected branch."
- Classes: `ci_workflow`.
- Observe: exit code; trace. Read the check runs on the head commit and compare with the ruleset contexts.
- Check: none today.

### P-CI-02

A workflow should pin each third-party action to a full-length commit SHA.

- Source: `S-GH-SECURITY`, section "Using third-party actions", strength advisory.
- Quote: "Pinning an action to a full-length commit SHA is currently the only way to use an action as an immutable release."
- Classes: `ci_workflow`.
- Observe: file. Read every uses line and match the ref against 40 hexadecimal characters.
- Check: none today.

### P-CI-03

A workflow should grant the GITHUB_TOKEN the minimum access its jobs need.

- Source: `S-GH-SYNTAX`, section "permissions", strength advisory.
- Quote: "adding or removing access as required, so that you only allow the minimum required access"
- Classes: `ci_workflow`.
- Observe: file. Parse each workflow and read the permissions key at workflow and job level.
- Check: none today.

### P-CI-04

A timeout-minutes value in a workflow should be a positive integer.

- Source: `S-GH-SYNTAX`, section "jobs.<job_id>.steps[*].timeout-minutes", strength normative.
- Quote: "Fractional values are not supported. `timeout-minutes` must be a positive integer."
- Classes: `ci_workflow`.
- Observe: file. Parse each workflow and read every timeout-minutes value.
- Check: none today.

### P-TEST-01

A test that carries an xfail marker should not count as passing evidence.

- Source: `W6`, section "strict parameter", strength normative.
- Quote: "Both `XFAIL` and `XPASS` don’t fail the test suite by default."
- Classes: `test`.
- Observe: file; exit code. Search the test files for xfail markers and read the pytest summary line.
- Check: none today.

### P-TEST-02

A unittest method that is meant to run should have a name that starts with test.

- Source: `S-UP-PYTHON`, section "Basic example", strength normative.
- Quote: "individual tests are defined with methods whose names start with the letters"
- Classes: `test`.
- Observe: file; trace. Collect the suite and compare the collected count with the method count.
- Check: none today.

### P-TEST-03

A node test run with a failing test should end with exit code 1.

- Source: `S-UP-NODETEST`, section "Test runner execution model", strength normative.
- Quote: "If any tests fail, the process exit code is set to"
- Classes: `test`, `ci_support`.
- Observe: exit code. Run node --test on a suite with one deliberate failure and read the exit code.
- Check: none today.

### P-TEST-04

A retained test should fail when the defect it names is introduced.

- Source: `PS-TEST-BEHAVIOR`, section "Test behavior, not implementation", strength advisory.
- Quote: "Before keeping a test, name a relevant defect and determine whether the complete test arrangement detects it."
- Classes: `test`.
- Observe: exit code. Apply the named defect in a disposable copy and read the test exit code.
- Check: none today.

### P-TEST-05

A check should take its expected result from outside the code it tests.

- Source: `PS-TEST-BEHAVIOR`, section "Test behavior, not implementation", strength advisory.
- Quote: "Use an independent expectation"
- Classes: `test`, `audit_rubric`, `audit_record`.
- Observe: file. Read the test and trace where the expected value comes from.
- Check: none today.

### P-PWSH-01

A script started with pwsh -File should receive its arguments as literal strings.

- Source: `S-UP-POWERSHELL`, section "-File", strength normative.
- Quote: "Parameters passed to the script are passed as literal strings, after interpretation by the current shell."
- Classes: `scripts_module`, `bin_script`.
- Observe: trace; exit code. Start the script with a probe argument and read what the script received.
- Check: none today.

### P-EVAL-01

An output-shaping component should score higher with the component than without it on the same cases.

- Source: `W4`, section "The no-plugin baseline", strength normative.
- Quote: "If a case scores 1.0 both with and without the plugin, the plugin isn't what made it pass."
- Classes: `skill`, `rule`, `agent`, `command`, `instruction_file`, `system_prompt`.
- Observe: trace. Run both arms on the same cases and compare the pass rates.
- Check: tests/audit/bench/run_baseline.py.

### P-PROMPT-01

An instruction should give the reason behind the behavior it asks for.

- Source: `S-PROMPT`, section "Add context to improve performance", strength advisory.
- Quote: "Providing context or motivation behind your instructions, such as explaining to Claude why such behavior is important, can help Claude better understand your goals and deliver more targeted responses."
- Classes: `rule`, `instruction_file`, `system_prompt`, `skill`.
- Observe: file. Review method: a judge reads each instruction and marks whether a reason follows it.
- Check: none today.

### P-PROMPT-02

An instruction should avoid ALWAYS and NEVER in capital letters.

- Source: `S-MARKET-SKILLCREATOR`, section "Improving the skill", strength advisory.
- Quote: "If you find yourself writing ALWAYS or NEVER in all caps, or using super rigid structures, that's a yellow flag"
- Classes: `skill`, `rule`, `instruction_file`.
- Observe: file. Search each file for the two words in capital letters and count the hits.
- Check: none today.

### P-STRUCT-01

A rule that repeats one instruction should be replaced by a lint, flag, runtime check, or script.

- Source: `PS-ENCODE`, section "description", strength advisory.
- Quote: "Encode the rule as a lint, metadata flag, runtime check, or script instead of more text."
- Classes: `rule`, `doc`, `instruction_file`.
- Observe: file. Review method: find instructions that occur in two or more files and look for a check that enforces each.
- Check: none today.

### P-LOAD-01

A module with one caller should be collapsed into that caller.

- Source: `PS-READER-LOAD`, section "description", strength advisory.
- Quote: "collapse one-caller wrappers and shrink mutable scope"
- Classes: `shared_module`, `hook_support`, `scripts_module`.
- Observe: file. Count the inbound edges of each module in tests/audit/data/dependencies.tsv.
- Check: none today.

### P-SUB-01

Dead code should leave the tree before new code is added.

- Source: `PS-SUBTRACT`, section "description", strength advisory.
- Quote: "Remove dead code, redundant validators, and stub references first, then build on the simpler base."
- Classes: `archive_item`, `shared_module`, `hook_support`, `scripts_module`.
- Observe: file. List the modules with no live inbound edge in tests/audit/data/dependencies.tsv.
- Check: none today.

### H-BAND-01

A KEEP verdict should rest on a full-arm pass rate of 0.60 or more and a pass-rate delta of 0.40 or more.

- Source: `house`. No outside source backs this property. preferences.md order 21.
- Classes: `skill`, `rule`, `agent`, `command`, `instruction_file`.
- Observe: trace. Read the two-arm summary and compare with the bands.
- Check: tests/audit/bench/summarize_baseline.py.

### H-STE-01

A descriptive sentence in user-facing text should hold 25 words or fewer.

- Source: `house`. No outside source backs this property. ASD-STE100 content is not retained, so no quote is possible.
- Classes: `rule`, `doc`, `instruction_file`.
- Observe: file. Split the text into sentences and count the words in each.
- Check: none today.
