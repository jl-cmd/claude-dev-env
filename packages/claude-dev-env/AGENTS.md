# Scope

## User-facing language hierarchy

ELI5 owns beginner framing and beginner-friendly presentation, large visuals, minimal text, one stable self-contained HTML artifact, update-in-place continuity, and sharing when a response needs that presentation.

`rules/asd-ste100-language.md` owns sentence-level word choice, grammar, tone, punctuation, exact labels, and prose form in every user-facing response and every ELI5 page.

Named capability rules own evidence, questions, current-state documentation, completion, code documentation, durable artifacts, and runtime enforcement. They apply ASD sentence rules and use ELI5 presentation when their user-facing output needs that envelope.

Raw tool output, machine payloads, code, and native repository artifacts keep their required formats. Their user-visible explanations follow the ASD rule.

A responsible human verifies technical accuracy, terminology, safety, confidentiality, and intended meaning.

Ask when ambiguity materially changes scope or implementation. Collect credentials through secure UI only; never request secrets in chat.

## Documentation

Describe the current system state. Keep documentation self-contained. Apply `rules/asd-ste100-language.md` for sentence-level prose.

Code and tests

Tests must exercise real behavior, real data, and production paths. Test theater is forbidden.

For multi-step code tasks:

Coders consult a warm session-advisor when blocked (Sol xHigh).
Repair reported findings when that review mode is selected.

Use `~/.claude/agents/session-advisor.md` for advisor selection and consultation protocol.

Research and delegation
Delegate fact extraction when multiple files or search patterns are required. Request precise file-and-line answers.

Use warm & reusable parallel luna (you decide effort level per task) fast subagents for unrelated questions; threaded & named appropriately.

Read or search directly only in files you will modify via es.exe.

For code navigation, prefer es.exe, then content search or globbing.

Scope every es.exe search.

Never scan an entire drive or network share.

Use `~/.claude/skills/everything-search/SKILL.md` for scoped filesystem searches that require Everything.

Task tracking
Track every task using `update_plan`.

## Definitions
Warm agent: Any agent who has acted within the past 30 minutes.

# Response and working style

ELI5 presentation sets beginner framing, useful visuals, concise detail, stable HTML continuity, and sharing when that capability applies.

Sentence-level language follows `rules/asd-ste100-language.md`.

Progress and final structure follow the named completion contract.

# Word budget

Keep ELI5 pages concise and useful. Use the ASD rule's 20-word procedure target and 25-word descriptive target when the technical content allows.

# No contrast framing

Use direct claims and direct actions. The canonical rule owns sentence form; capability contracts own exceptions needed to explain a concrete failure.

# Naming

Use full capability names for files, modules, functions, variables, branches, and tests. Name reusable components for the capability they provide. Keep workflow words on driver surfaces.

  # Change size



  When planning work or opening a pull request, size the change first: one self-contained change, around 100 lines, with its tests. Read the small-changelists guide for the numbers, the allowed exceptions, and how to split.

Use `~/.claude/skills/small-cl/SKILL.md` for change-size guidance and review-sized boundaries.

## Execution and delegation

Delegate all task work to Tier 3 agents.

Draft a separate assignment for each agent. Each assignment must be clear, concise, tightly scoped, independently executable, and explicit about ownership, constraints, deliverables, and verification.

Run independent assignments in parallel. Keep overlapping work sequential. The primary agent coordinates agents, resolves dependencies, verifies results, and reports outcomes.

## Definitions

Tier 3 agent: A strong execution specialist that independently completes a bounded assignment, follows repository contracts, repairs routine failures, tests production behavior, and escalates decisions that materially affect architecture or scope.

Warm agent: An agent that has acted within the past 30 minutes. Reuse warm agents for related follow-up work.

  # Corrections

  Only correct an earlier statement when the ecode, conclusions, or decisions. Statecorrections plainly and briefly, then continue the task. For slips that change nothing for the user, make the fix and move on without noting it.

  # Tool calls and output hygiene

  When you use a tool, you may say a brief sentence first. If no tool can express what the user asked for, say so. Do not include internal or system XML tags in your response.

Use the named review workflow for code-review response reporting.

  # Code review

  When reviewing code, report everything you find. Filtering belongs in a separate pass.

<tone_preference>
ELI5 sets beginner-friendly presentation when it applies. ASD sets sentence-level wording and tone.
</tone_preference>
