# Self-Audit Checklist

Mandatory post-build verification. Every item must pass before a skill is delivered. Run after writing a new skill, improving an existing one, or polishing.

Source synthesis: [Anthropic best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices), [Lessons from Building Claude Code](thariq-x-post-skills.json), model skills (bugteam, pr-converge).

## Core quality

- [ ] **Conciseness** — Only context Claude doesn't already have. Every line justifies its token cost.
  > "Default assumption: Claude is already very smart."
- [ ] **Degree of freedom** — Matches task fragility. Low for narrow bridges, high for open fields.
  > "Match the level of specificity to the task's fragility and variability."
- [ ] **Naming convention** — Name uses gerund form (verb-ing) unless it's a well-known acronym or proper name. Lowercase, numbers, hyphens only. Max 64 chars. No reserved words.
  > "Use consistent naming patterns to make Skills easier to reference."
- [ ] **Description field** — Third person. Includes what AND when. Specific trigger phrases. Max 1024 chars. No XML tags.
  > "The description is critical for skill selection: Claude uses it to choose the right Skill from potentially 100+ available Skills."
- [ ] **SKILL.md body under 500 lines**
  > "Keep SKILL.md body under 500 lines for optimal performance."
- [ ] **One level deep** — All reference files link directly from SKILL.md. No nested references.
  > "Claude may partially read files when they're referenced from other referenced files."
- [ ] **TOC on files over 100 lines** — Every reference file >100 lines has a table of contents.
  > "This ensures Claude can see the full scope of available information even when previewing with partial reads."
- [ ] **No time-sensitive claims** — Or isolated in "old patterns" section.
  > "Don't include information that will become outdated."
- [ ] **Consistent terminology** — One term per concept throughout.
  > "Consistency helps Claude understand and follow instructions."
- [ ] **Forward slashes only** — File paths use `/`, not `\`.
  > "Unix-style paths work across all platforms."
- [ ] **Default provided, not options menu** — One recommended approach, escape hatch for special cases.
  > "Don't present multiple approaches unless necessary. Provide a default with escape hatch."
- [ ] **Gotchas section present** — Highest-signal content. Built from real failure observations.
  > "The highest-signal content in any skill is the Gotchas section."
- [ ] **Doesn't state the obvious** — Pushes Claude out of defaults, doesn't re-teach what Claude knows.
  > "Focus on information that pushes Claude out of its normal way of thinking."
- [ ] **Not railroading** — Gives information and flexibility, not rigid scripts.
  > "Give Claude the information it needs, but give it the flexibility to adapt to the situation."
- [ ] **When-this-applies section** — Trigger conditions clear. Refusal cases with exact response text.
  > bugteam pattern — "Refusals — first match wins; respond with the quoted line exactly and stop."
- [ ] **File index present** — Every file in the package listed with its purpose.
  > "Tell Claude what files are in your skill, and it will read them at appropriate times."
- [ ] **Concrete examples** — Input/output pairs or exit scenarios, not abstract descriptions.
  > "Examples help Claude understand the desired style and level of detail more clearly than descriptions alone."
- [ ] **Workflows have checklists** — Multi-step processes include copyable `[ ]` checklists.
  > "For particularly complex workflows, provide a checklist that Claude can copy into its response and check off as it progresses."
- [ ] **Feedback loops where quality-critical** — Run validator → fix → repeat pattern.
  > "This pattern greatly improves output quality."
- [ ] **Constraints separated** — Non-negotiables in CONSTRAINTS.md or equivalent section.
  > bugteam pattern — constraints file with design rationale.
- [ ] **Folder map at bottom** — Lists directories and their purposes.
  > pr-converge pattern — "Folder map" section.

## Skill-type-specific

- [ ] **Skill type classified** — Fits one of 9 types. Folder structure matches type recommendation.
  > "The best skills fit cleanly into one; the more confusing ones straddle several."
- [ ] **Domain layout appropriate** — If multiple domains, organized by domain (reference/finance.md, reference/sales.md).
  > Pattern 2 — domain-specific organization.

## Code and scripts (if applicable)

- [ ] **Scripts solve, don't punt** — Error handling explicit, no raw exceptions for Claude to figure out.
  > "Handle error conditions rather than punting to Claude."
- [ ] **No voodoo constants** — Every magic number has a documented justification.
  > "Configuration parameters should be justified and documented."
- [ ] **Execute vs read intent clear** — "Run script.py" (execute) vs "See script.py for algorithm" (read).
  > "Make clear in your instructions whether Claude should execute the script or read it as reference."
- [ ] **Dependencies listed** — Required packages stated, verified as available.
  > "List required packages in your SKILL.md and verify they're available."
- [ ] **MCP tools fully qualified** — `ServerName:tool_name` format.
  > "Always use fully qualified tool names to avoid 'tool not found' errors."
- [ ] **Plan-validate-execute for high-stakes ops** — Verifiable intermediate outputs before destructive actions.
  > "Catches errors early: validation finds problems before changes are applied."

## Setup and memory (if applicable)

- [ ] **Setup instructions clear** — config.json pattern or AskUserQuestion for initial context.
  > "If the config is not set up, the agent can then ask the user for information."
- [ ] **Persistent data uses `${CLAUDE_PLUGIN_DATA}`** — Not stored in skill directory itself.
  > "Data stored in the skill directory may be deleted when you upgrade the skill."

## Composition and measurement (if applicable)

- [ ] **Skill dependencies documented** — Skills this one composes with are named.
  > "You can just reference other skills by name, and the model will invoke them if they are installed."
- [ ] **Hooks declared** — If skill registers hooks, their purpose and scope is stated.
  > "Skills can include hooks that are only activated when the skill is called."

---

## Usage

Copy this checklist into your response after building. Check off each item. Any item that fails → fix before delivering. Any item marked "if applicable" that doesn't apply → mark N/A with a one-line reason.
