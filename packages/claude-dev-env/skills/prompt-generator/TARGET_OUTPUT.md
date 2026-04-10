# prompt-generator — user-visible output contract

This file is the **target output spec** for eval-driven iteration of the `prompt-generator` skill. Evals assert behavior against it; update this document and `SKILL.md` together when the contract changes.

**File map:** `ARCHITECTURE.md` lists all files in this skill package and their roles.

**Methodology:** [Anthropic — Agent Skills: evaluation and iteration](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#evaluation-and-iteration)

## Terminology

- **Outcome preview gate** — Mandatory `AskUserQuestion` turn **after** the drafting subagent returns candidate XML internally and **before** the orchestrator emits the fenced artifact. Confirms the user recognizes what executing the generated prompt will produce.
- **Outcome digest** — Skimmable markdown block **after** the closing ` ``` ` of the single `xml` fence on the final handoff: bullets for downstream deliverables, primary inputs or tools, done criteria, and a short sample excerpt (see `SKILL.md` §9).

## User-visible output contract

- **Clarity bar:** Every deliverable (`AskUserQuestion` fields, XML body, outcome digest) states concrete outcomes, explicit formats, and checkable done-when signals—aligned with Anthropic [Be clear and direct](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#be-clear-and-direct) and [Control the format of responses](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#control-the-format-of-responses). Prefer what to do and how to verify it over empty prohibitions or vague quality adjectives.
- **Questions:** Deliver every clarifying question through **AskUserQuestion** (one form per round), with **2–4** options per question and the **recommended** option listed **first**. Tag discovery-sourced options **`[discovered]`** when they came from repo search.
- **Outcome preview turn (mandatory):** Immediately before the final handoff, emit exactly one assistant turn that contains:
  1. A markdown block titled `### Outcome preview` with bullets only: **What it does**, **Key inputs**, **Done when**, **Quick sample** (about twenty lines max; follow the sample formatting rules in SKILL.md section 7).
  2. **AskUserQuestion** with **2–4** options: **Ship this outcome profile** (recommended first), two **contextual alternates** grounded in discovery, and **Refine with free text** (starts another drafting loop). Observe the preview round cap per SKILL.md Phase 4.
- **Final assistant message (complete handoff in one send):**
  1. **Artifact:** the full XML prompt inside **one** Markdown code fence whose language tag is `xml`
  2. **Outcome digest:** after the closing fence, a `## Outcome digest` section with tightened bullets so the user can verify intent at a glance
  3. **Paste-ready section:** The paste-ready prompt artifact remains the single ` ```xml ` block; the digest is for reading, not for pasting into the downstream session
- **Full audit table / JSON debug bundle:** Stay internal until the user names debug with a phrase such as `show debug`, `full audit table`, or `raw internal object`; then append the table/JSON **after** the Outcome digest.
- **File-based validation loop:** The subagent writes output to `data/prompts/.draft-prompt.xml`, runs the validator CLI, and fixes violations until exit 0. The orchestrator then outputs the validated result to the user.
- **Decision stability:** Pick one drafting approach, carry it through preview confirmation, then ship; change approach only when **new** facts from the user or tools contradict the earlier plan; if the draft fails checks, fix forward inside the same structure instead of restarting from scratch.

## Scenario 1: Fresh chat with brief goal

**Trigger:** `/prompt-generator [brief goal]` in a new or near-empty session.

**Discovery:** Run **3–5** parallel **Glob/Grep** (or equivalent repo search) calls before AskUserQuestion. Record: repo root, relevant package roots (e.g. `packages/<name>/`), config entry points (`pyproject.toml`, `package.json`, hook paths), and one example file path per area you will mention in the XML.

**Q&A:** One AskUserQuestion with **2–4** questions covering: scope (which subtree), audience (human vs agent consumer), desired downstream output shape, and hard constraints (tests, CODE_RULES, deadlines). Populate options from discovery paths and package names.

**Output:** After drafting, run the **Outcome preview** turn; then send `xml` fence and **Outcome digest**—the handoff message is complete.

## Scenario 2: Session handoff

**Trigger:** `/prompt-generator` when the session already has substantial prior context; user wants a prompt for a **new** session to continue work.

**Discovery:** Reread the thread and list: current hypothesis or goal, decisions already made (bulleted), absolute paths of files already edited, the next **three** concrete actions, and blocking constraints. Use repo tools only when the thread references paths you must verify (e.g. confirm a file still exists).

**Q&A:** One AskUserQuestion with **1–2** questions, e.g. “Rank these next actions for the new session” or “Exclude these areas from scope,” each with **2–4** concrete options drawn from the thread.

**Output:** After drafting, run the **Outcome preview** turn; then send `xml` fence and **Outcome digest**.

**Handoff prompt quality:** `<background>` must include the bullet lists above so a new session can continue with **zero** access to this chat. Quote decision text verbatim where precision matters.

## Scenario 3: Long unstructured input

**Trigger:** User pastes a long, multi-requirement message (paths, tools, process constraints).

**Discovery:** Before AskUserQuestion, run targeted Glob/Grep to confirm each user-mentioned path or package (e.g. `packages/samsung-automation`, `shared_utils`, config modules). Note which claims are verified vs unknown.

**Q&A:** First question restates your parsed intent in one sentence and asks the user to pick among **2–4** interpretations (e.g. “extract constants only” vs “extract + add tests”). Later questions stay on **AskUserQuestion** with named option sets.

**Requirements checklist:** The generated XML must mention every user-stated requirement by name (timeouts, selectors, config extraction, TDD, CODE_RULES, test safety, etc.); if one is out of scope, put the reason in `<open_question>`.

**Output:** After drafting, run the **Outcome preview** turn; then send `xml` fence and **Outcome digest**.

## Scenario 4: Noisy context, stable output

**Trigger:** `/prompt-generator ...` after a long thread with unrelated topics, tool errors, or tangents.

**Output shape:** Same as Scenario 1 for the final message: one `xml` fence, then **Outcome digest**.

**Content focus:** Keep the generated XML aligned with the latest `/prompt-generator` request (e.g. “security-focused code review agent”). Populate the subagent brief from: the user’s literal request string, a **one-paragraph** summary of on-topic facts, and path-grounded discovery notes—leave stack traces, failed commands, and off-topic thread history out of that brief so they never reach the XML body.

**Structure:** Complete XML: every tag opened is closed; lists end with finished items; last section is `<output_format>` with measurable checks.

**Delegation:** Give the drafting subagent a **curated** brief under ~2k tokens when possible: request string + summary + discovery snippets—enough context to draft, without attaching the full raw transcript.

## Structural invariant A — Tool-free artifact output

- **Order:** discovery tool calls (when used) → **AskUserQuestion** → subagent (draft + internal audit) → **Outcome preview** turn (`### Outcome preview` + **AskUserQuestion**) → optional refinement loops → **one** final assistant message.
- **Final message composition:** That message is plain text only, in order: opening ` ```xml ` fence → XML body → closing fence → `## Outcome digest` → end-of-message. Run every `tool_use` in earlier turns; between the opening and closing `xml` fence, emit only the characters of the XML payload.

## Structural invariant B — Fenced block closes cleanly

- Use one opening ``` and one closing ``` for the **xml** artifact.
- Balance every XML tag; close `<instructions>`, `<background>`, etc. explicitly.
- End each numbered step inside `<instructions>` with a complete sentence and a fully written list item.
- The user can copy from the opening ``` through the closing ``` of the **xml** fence into a new file without manual repair.

## Structural invariant C — Discovery before lock-in

- When the user is unsure where logic lives, run discovery **before** you freeze the XML; record findings in `<background>` with paths from Glob/Grep.
- If discovery finds the owner file(s), reference them with repo-relative paths in `<instructions>`.
- If discovery is inconclusive, add `<open_question>` in `<background>` naming what you searched and what remains unknown.
- After the opening fence of the artifact, treat the XML as frozen: finish editing inside that fence; route any new repo searches to a later user turn if needed.

## Structural invariant D — Certainty in instructions, questions in tags

- Inside the fenced XML, write `<instructions>` and `<constraints>` as **direct imperative** steps the downstream agent will follow.
- Place residual uncertainty only in `<open_question>` elements (one topic per tag) with a clear decision you need from the executor or user.
- Use definitive phrasing inside instructions (e.g. “Run tests in `packages/foo` with `pytest tests/`”) so each step reads like an executable checklist.

## Structural invariant E — Render-survival for XML sections

- **Problem (HTML):** Tag names used for prompt XML sections can overlap **HTML5 element names**. Chat renderers may treat those tokens as HTML and hide or alter the content between tags. High-risk examples include: `section`, `summary`, `details`, `header`, `footer`, `main`, `aside`, `article`, `nav`, `figure`. The former required name `context` matched an HTML element; **required** sections now use `<background>` for situational grounding so the name stays off that list. The raw assistant text may be complete while the **rendered** message looks like sections are missing.
- **Problem (nested Markdown fences):** A ` ```bash ` (or other inner) line inside the outer ` ```xml ` block is still a line of text in the transcript, but many Markdown renderers treat it as **opening a nested code fence**, which **closes the outer fence early**. Everything after that point (including `</illustrations>` and other closing tags) can appear outside the code block or look “swallowed.” `extract_fenced_xml_content` now walks inner fences (` ```lang ` … closing `` ``` ``) before accepting the outer `` ``` `` that ends the `xml` block.
- **Outcome digest:** Follow the sample formatting rules in SKILL.md section 7 inside `## Outcome digest` so a second outer ` ```xml ` block never appears—multiple `xml` fences concatenate in `extract_fenced_xml_content` and would corrupt clipboard copy.
- **Primary mitigation:** When the fenced XML artifact **contains any tag whose local name is on the HTML-collision list**, or when the artifact is **large enough that render truncation is likely**, the orchestrator **must write the full artifact to a file** (default: under `data/prompts/` or a path the user supplied earlier) and **paste the absolute file path** in the chat message. Pair the path with a **short section inventory** confirming all five required sections (`role`, `background`, `instructions`, `constraints`, `output_format`) are present in the file.
- **Authoring rules for code inside `<illustrations>`:** Follow the sample formatting rules in SKILL.md section 7. Hooks and clipboard treat complete triple-backtick pairs as one unit inside the outer `` ```xml `` fence.
- **Fallback when file write is unavailable:** Escape the **opening angle bracket** of colliding tags (for example `&lt;section>` — user restores `<` when pasting) or use another distinctive wrapper **documented in the same message**, so the user can recover literal XML. State explicitly that the user should restore brackets when copying into another system.
- **Structural safety net:** The **file-based validation loop** corrects missing section tag pairs before user output. The validator CLI enforces section presence, scope anchors, checklist rows, context-control signals, and positive phrasing.

## XML artifact (minimum sections)

Include at least:

- `<role>...</role>`
- `<background>...</background>`
- `<instructions>...</instructions>`
- `<constraints>...</constraints>`
- `<output_format>...</output_format>`

Add `<illustrations>` when format or tone is easy to misunderstand; nest sections when the task has natural hierarchy. **Long code samples belong in `<illustrations>`** — follow the sample formatting rules in SKILL.md section 7.


## File-based validation loop (primary enforcement)

The subagent writes the complete artifact (fenced XML + Outcome digest + hook validation block) to `data/prompts/.draft-prompt.xml`, runs the validator, and fixes violations (exit 2) until exit 0. The orchestrator then strips the hook validation block and outputs fence + digest.

    python packages/claude-dev-env/hooks/blocking/prompt_workflow_validate.py data/prompts/.draft-prompt.xml

The same checks are available as a Python function via `from prompt_workflow_validate import validate_prompt_workflow` for integration in tests and tooling.

## Internal 15-row compliance checklist (audit numerator)

The 15-row compliance audit maps to the named rows in `SKILL.md` §11. **Default user path:** keep the table internal; print the expanded table + JSON only after an explicit debug request.
