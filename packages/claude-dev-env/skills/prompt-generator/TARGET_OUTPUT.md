# prompt-generator — user-visible output contract

This file is the **target output spec** for eval-driven iteration of the `prompt-generator` skill. Evals assert behavior against it; update this document and `SKILL.md` together when the contract changes.

**Methodology:** [Anthropic — Agent Skills: evaluation and iteration](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#evaluation-and-iteration)

## User-visible output contract

- **Clarity bar:** Every deliverable (AskUserQuestion fields, audit line, XML body) states concrete outcomes, explicit formats, and checkable done-when signals—aligned with Anthropic [Be clear and direct](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#be-clear-and-direct) and [Control the format of responses](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#control-the-format-of-responses). Prefer what to do and how to verify it over empty prohibitions or vague quality adjectives.
- **Questions:** Deliver every clarifying question through **AskUserQuestion** (one form per round), with **2–4** options per question and the **recommended** option listed **first**. Tag discovery-sourced options **`[discovered]`** when they came from repo search.
- **Final assistant message (complete handoff in one send):**
  1. **Audit line:** `Audit: pass 14/14` or `Audit: fail N/14 — [reason]`
  2. **Artifact:** the full XML prompt inside **one** Markdown code fence whose language tag is `xml`
  3. **Send boundary:** stop typing as soon as the closing fence ends—the message body is exactly those two blocks back-to-back, ready to copy; your next tokens belong to the user’s following turn
- **Full audit table / JSON debug bundle:** Stay internal until the user names debug with a phrase such as `show debug`, `full audit table`, or `raw internal object`; then append the table/JSON after the usual audit line + XML fence.
- **Hook retries:** Keep retry loops inside the subagent or internal pipeline; the user sees at most one short status line such as `Retrying: scope anchor missing` before the successful audit line + fence.
- **Decision stability:** Pick one drafting approach, carry it to a complete XML artifact, then stop. Change approach only when the user or tool results add **new** facts that contradict the earlier plan; if the draft fails checks, fix forward inside the same structure instead of restarting from scratch.

## Scenario 1: Fresh chat with brief goal

**Trigger:** `/prompt-generator [brief goal]` in a new or near-empty session.

**Discovery:** Run **3–5** parallel **Glob/Grep** (or equivalent repo search) calls before AskUserQuestion. Record: repo root, relevant package roots (e.g. `packages/<name>/`), config entry points (`pyproject.toml`, `package.json`, hook paths), and one example file path per area you will mention in the XML.

**Q&A:** One AskUserQuestion with **2–4** questions covering: scope (which subtree), audience (human vs agent consumer), desired downstream output shape, and hard constraints (tests, CODE_RULES, deadlines). Populate options from discovery paths and package names.

**Output:** Send audit line, then one `xml` fence with the full prompt, then stop—the handoff message is complete.

## Scenario 2: Session handoff

**Trigger:** `/prompt-generator` when the session already has substantial prior context; user wants a prompt for a **new** session to continue work.

**Discovery:** Reread the thread and list: current hypothesis or goal, decisions already made (bulleted), absolute paths of files already edited, the next **three** concrete actions, and blocking constraints. Use repo tools only when the thread references paths you must verify (e.g. confirm a file still exists).

**Q&A:** One AskUserQuestion with **1–2** questions, e.g. “Rank these next actions for the new session” or “Exclude these areas from scope,” each with **2–4** concrete options drawn from the thread.

**Output:** Send audit line, then one `xml` fence with the full prompt, then stop—the handoff message is complete.

**Handoff prompt quality:** `<context>` must include the bullet lists above so a new session can continue with **zero** access to this chat. Quote decision text verbatim where precision matters.

## Scenario 3: Long unstructured input

**Trigger:** User pastes a long, multi-requirement message (paths, tools, process constraints).

**Discovery:** Before AskUserQuestion, run targeted Glob/Grep to confirm each user-mentioned path or package (e.g. `packages/samsung-automation`, `shared_utils`, config modules). Note which claims are verified vs unknown.

**Q&A:** First question restates your parsed intent in one sentence and asks the user to pick among **2–4** interpretations (e.g. “extract constants only” vs “extract + add tests”). Later questions stay on **AskUserQuestion** with named option sets.

**Requirements checklist:** The generated XML must mention every user-stated requirement by name (timeouts, selectors, config extraction, TDD, CODE_RULES, test safety, etc.); if one is out of scope, put the reason in `<open_question>`.

**Output:** Send audit line, then one `xml` fence with the full prompt, then stop—the handoff message is complete.

## Scenario 4: Noisy context, stable output

**Trigger:** `/prompt-generator ...` after a long thread with unrelated topics, tool errors, or tangents.

**Output shape:** Same as Scenario 1: audit line, one `xml` fence, immediate send boundary after the closing fence.

**Content focus:** Keep the generated XML aligned with the latest `/prompt-generator` request (e.g. “security-focused code review agent”). Populate the subagent brief from: the user’s literal request string, a **one-paragraph** summary of on-topic facts, and path-grounded discovery notes—leave stack traces, failed commands, and off-topic thread history out of that brief so they never reach the XML body.

**Structure:** Complete XML: every tag opened is closed; lists end with finished items; last section is `<output_format>` with measurable checks.

**Delegation:** Give the drafting subagent a **curated** brief under ~2k tokens when possible: request string + summary + discovery snippets—enough context to draft, without attaching the full raw transcript.

## Structural invariant A — Tool-free artifact tail

- **Order:** discovery tool calls (when used) → AskUserQuestion → subagent (draft + internal audit) → **one** final assistant message.
- **Final message composition:** That message is plain text only, in order: audit line → opening fence → XML body → closing fence → end-of-message. Run every `tool_use` in earlier turns; between the opening and closing fence, emit only the characters of the XML payload.

## Structural invariant B — Fenced block closes cleanly

- Use one opening ``` and one closing ``` for the artifact.
- Balance every XML tag; close `<instructions>`, `<context>`, etc. explicitly.
- End each numbered step inside `<instructions>` with a complete sentence and a fully written list item.
- The user can copy from the opening ``` through the closing ``` into a new file without manual repair.

## Structural invariant C — Discovery before lock-in

- When the user is unsure where logic lives, run discovery **before** you freeze the XML; record findings in `<context>` with paths from Glob/Grep.
- If discovery finds the owner file(s), reference them with repo-relative paths in `<instructions>`.
- If discovery is inconclusive, add `<open_question>` in `<context>` naming what you searched and what remains unknown.
- After the opening fence of the artifact, treat the XML as frozen: finish editing inside that fence; route any new repo searches to a later user turn if needed.

## Structural invariant D — Certainty in instructions, questions in tags

- Inside the fenced XML, write `<instructions>` and `<constraints>` as **direct imperative** steps the downstream agent will follow.
- Place residual uncertainty only in `<open_question>` elements (one topic per tag) with a clear decision you need from the executor or user.
- Use definitive phrasing inside instructions (e.g. “Run tests in `packages/foo` with `pytest tests/`”) so each step reads like an executable checklist.

## XML artifact (minimum sections)

Include at least:

- `<role>...</role>`
- `<context>...</context>`
- `<instructions>...</instructions>`
- `<constraints>...</constraints>`
- `<output_format>...</output_format>`

Add `<examples>` when format or tone is easy to misunderstand; nest sections when the task has natural hierarchy.

## Internal 14-row compliance checklist (audit numerator)

The `14` in `Audit: pass 14/14` maps to the named rows in `SKILL.md` (§11 **Compliance audit — 14-row checklist**), including `reversible_action_and_safety_check_guidance` and `scope_terms_explicit_and_anchored`. **Default user path:** keep the table internal; print the expanded table + JSON only after an explicit debug request. On failure, set the audit line to `Audit: fail N/14 — [primary theme]` where the theme names one concrete gap (e.g. `scope_block missing completion_boundary`, `output_format lacks acceptance checks`).
