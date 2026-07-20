---
name: condensing-instructions
description: >-
  Rewrite existing instruction documents or turn first drafts and requirements
  into compact, high-information operational instructions without changing or
  inventing their contract. Use for prompts, skills, policies, runbooks,
  agent-facing documents, reference instructions, token reduction,
  deduplication, restructuring, or concise instruction authoring.
---

# Condensing Instructions

Rewrite an existing instruction document or turn a first draft, notes, or requirements into compact operational instructions. Preserve behavior; reduce length only after the contract is complete and unambiguous.

## Preserve the full contract

Treat every execution-relevant detail as binding: required, prohibited, and permitted behavior; safety and authority boundaries; actors, objects, data or resource kinds, and scope; force, negation, and quantifiers; triggers, defaults, conditions, exceptions, thresholds, and precedence; dependencies, prerequisites, order, timing, duration, persistence, and state; failure and recovery behavior; exact strings, names, paths, URLs, identifiers, commands, flags, numbers, placeholders, schemas, and error text; and input, output, formatting, validation, acceptance, and completion requirements.

Keep rationale or examples only when they define a decision, boundary, exception, exact value, or required behavior. Preserve required frontmatter, tags, wrappers, templates, schemas, and other machine-read structure.

When rewriting, change wording and structure, not behavior. When authoring, supply organization, wording, and conventional editorial choices, but do not invent material obligations, permissions, exceptions, or defaults. Ask one concise blocking question when missing, contradictory, or ambiguous information would materially change behavior, safety, authority, scope, precedence, failure handling, or output. Otherwise proceed.

If no instruction material or requirements are provided, respond exactly: `Provide the instructions or draft requirements.`

## Build a requirement ledger first

Before deleting, merging, or drafting text, record each atomic commitment internally. Capture its force, actor, trigger, action, object or type, required outcome, scope, timing or persistence, dependencies, defaults, exceptions, precedence, failure behavior, and exact literals when applicable.

For an existing document, inventory every behaviorally meaningful statement. Distinguish true duplicates from similar rules that apply to different actors, stages, conditions, or scopes. For a first draft, translate each stated goal into observable behavior or an acceptance condition; mark material gaps instead of silently choosing an answer. Do not promote a preference to a hard rule or average conflicting rules.

Do not expose the ledger unless requested.

## Group rules by the decisions they control

- Group requirements by function or decision point, not by draft order.
- Default to this sequence when it fits: purpose and scope; inputs and prerequisites; operating defaults; procedures and branches; constraints and safety; outputs and failures; verification. Override it when dependencies require another sequence.
- Place a safety rule or other constraint before the first action it governs.
- Within a group, put prerequisites before actions, general rules before narrow exceptions, and production requirements before their checks.
- Put each exception beside the rule it modifies. State precedence when rules overlap.
- Give each rule one authoritative location. State a shared actor, condition, default, or scope once at the narrowest level that covers every affected rule.
- Let a heading carry scope only when every instruction beneath it clearly inherits that scope. Use the fewest headings that preserve navigation.

## Write direct, dense rules

- Use active, imperative language and concrete verbs. Put a condition before its action and an exception immediately after its default.
- Preserve force and quantifiers. Keep `must`, `never`, `only`, `should`, `may`, `all`, `any`, and exact counts distinct.
- Combine statements only when their actor, force, scope, trigger, timing, persistence, and exceptions align.
- Replace true repetition with one rule and a compact list of affected cases. Keep separate statements when repetition protects distinct stages, scopes, or failure modes.
- Use one sentence per decision. Join clauses only when they form one testable rule.
- Use paragraphs for cohesive rules and lists for parallel obligations, mappings, or branches. Avoid decorative headings and structural ceremony.
- Remove non-operative background, history, rationale, transition text, conversational framing, restatement, setup narration, and examples. Remove inventories or folder maps that merely describe the document.
- Use one term for each concept. Define unfamiliar terms at first use. Do not compress complete sentences into fragments, stacked jargon, or vague shorthand.
- Preserve operational literals character for character, including spelling, case, punctuation, quoting, and placeholders. Preserve whether a list is exhaustive or illustrative; never replace an exact enumeration with `etc.` or a broader category.

## Imply only what cannot change behavior

Rely on ordinary language competence and document conventions only when every reasonable reader would take the same action. State a detail when omitting it could change permission, safety, actor, object or type, scope, force, trigger, sequence, timing, persistence, precedence, failure behavior, exact output, or acceptance.

Match detail to fragility. Specify exact steps for brittle, high-risk, or order-dependent work. For flexible work, state the required outcome and constraints, then leave the method open.

Never use implication to carry a prohibition, exception, dependency, safety boundary, or exact literal. Do not retain obvious advice that constrains nothing, and do not omit a non-obvious rule because it seems intuitive.

## Pass the quality gate

Run these checks silently:

1. **Coverage:** Map every ledger item to a clause in the finished document.
2. **Support:** Map every material clause back to a stated or confirmed requirement; remove invented behavior.
3. **Fidelity:** Compare force, negation, quantifiers, actor, object or type, scope, conditions, exceptions, dependencies, order, timing, persistence, failure behavior, outputs, and protected literals. Nothing may be weakened, broadened, narrowed, contradicted, or altered character for character where exactness matters.
4. **Boundary behavior:** Test the normal case, each branch and exception, prohibited cases, missing dependencies, failures, and acceptance checks when present. Each case must yield the intended action.
5. **Clarity:** Resolve ambiguous references, hidden precedence, scattered exceptions, inconsistent terms, and unclear qualifier scope.
6. **Density:** Delete any sentence that changes no behavior, safety boundary, interpretation, or validation result. Merge remaining text only when the boundary stays equally clear.
7. **Independent use:** Reconstruct the ledger from only the finished document. It must stand alone without background or unstated context.

Do not finish until every check passes. If multiple versions pass, prefer fewer words, fewer sections, and lower lookup cost. Shorter text never compensates for lost behavior or precision.

## Deliver the requested artifact

Preserve the requested format and required syntactic envelope. If no format is specified, use the leanest clear Markdown structure.

For text supplied in the conversation, output only the finished instruction document. For file tasks, write only the requested paths: edit an existing file in place, and create a new file only when requested. Report changed paths with a concise behavior summary. Do not include the ledger or process narration unless requested.
