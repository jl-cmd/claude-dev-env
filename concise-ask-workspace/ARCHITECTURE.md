# Concise Ask / Relevance-First Reply — End-State Architecture

**Scope:** `concise-ask-workspace/` only until the user names install under `packages/claude-dev-env/skills/<skill-folder>/`.

**Stable vocabulary (from gap analysis):** relevance-first opening, leading answer, depth proportional to the ask, staged breadth, structured clarification (`AskUserQuestion`, Cursor `AskQuestion`), thin grounding, missing grounding, partial confidence, late signal under early noise, disambiguate with minimal friction, bundled or multi-part prompt, highest-impact part first, deferred parts, clearly broad prompt, explicit depth request.

---

## 1. Progressive disclosure map and load order

| Order | Path | Purpose |
|-------|------|---------|
| 1 | `concise-ask-workspace/SKILL.md` | Entry: frontmatter, third-person `description`, triggers, TOC, one-level-deep links only |
| 2 | `concise-ask-workspace/WORKFLOWS.md` | Copy-paste checklists: disambiguation-first replies; depth-on-request expansion |
| 3 | `concise-ask-workspace/EXAMPLES.md` | Template openings; example pairs aligned to user-pasted or user-approved excerpts |
| 4 | `concise-ask-workspace/REFERENCE.md` | Terminology, Anthropic doc links, eval evidence rules, pending approved excerpts |
| 5 | `concise-ask-workspace/evals/relevance-skill.json` | Evaluation rows; populated cells require user paste or explicit approval reference |

**Optional later (not in initial package):**

| Milestone | Path / action | Activation |
|-----------|----------------|------------|
| Distribution | `packages/claude-dev-env/skills/<name>/` mirror of approved files | User requests packaging in chat |
| Hooks / Stop / clipboard | Installer or hook registration | Explicit user-started milestone only |

**Scripts folder:** `concise-ask-workspace/scripts/**` — reserved for future helper scripts (empty or absent until needed). No hook installation in Phase B.

---

## 2. `SKILL.md` — required YAML frontmatter

Aligned with Anthropic Agent Skills: concise metadata, third-person `description`, valid `name`.

| Field | Requirement |
|-------|-------------|
| `name` | Lowercase, hyphens, gerund or action-oriented; initial target: `relevance-first-asks` (adjust only if user renames in review) |
| `description` | Third person only; states what the skill does; lists **exact triggers** (see §3) in one or two dense sentences; length within Anthropic skill limits |
| Optional frontmatter | Follow repo / Anthropic examples for any additional allowed keys; do not duplicate long policy inside `description` |

**Body constraints:**

- Table of contents at top if body grows; **keep total body under 500 lines**; push depth into linked files.
- Links to `WORKFLOWS.md`, `EXAMPLES.md`, `REFERENCE.md` only (one level deep from `SKILL.md`).

---

## 3. Third-person `description` — trigger coverage (must appear in prose)

- Simple or single-focus questions → relevance-first opening, depth proportional to the ask.
- Explicit depth or breadth signals (“more,” “details,” “explain the rest,” clearly tutorial-scale or wide-scope prompts) → expand after signal or after clarification.
- Bundled or multi-part prompts → staged reply (highest-impact part first, name deferred parts) **or** structured clarification to pick which part leads.
- Thin or missing grounding (logs, paths, configs, artifacts outside thread) → structured clarification first; narrative depth after material is in thread.
- Partial confidence → state the uncertain slice and what would confirm; defer adjacent breadth unless user asks.
- Domain-agnostic examples in triggers may cite **theme automation** or similar only as illustration if kept short.

---

## 4. Linked files — purpose and length rules

| File | Purpose |
|------|---------|
| `WORKFLOWS.md` | Checklists: (A) disambiguation-first reply when intent splits or grounding is thin; (B) depth-on-request expansion after explicit signal or post-clarification |
| `EXAMPLES.md` | Template opening patterns; each paired with user-supplied or user-approved excerpt when available; labeled slots `<!-- PENDING: excerpt for ... -->` when not |
| `REFERENCE.md` | Glossary (stable vocabulary), links to Anthropic Agent Skills + prompting best practices, eval evidence policy, **Pending approved excerpts** section with positive wording for each empty eval slot |

**TOC rule:** Any reference file expected to exceed **100 lines** gets a table of contents at the top.

---

## 5. `evals/relevance-skill.json` — filename and schema

**Filename:** `concise-ask-workspace/evals/relevance-skill.json` (renamable in one checkpoint if user prefers).

**Top-level shape:** Array of evaluation objects (or wrapper with `evaluations` key — implement Phase B consistently; default: array of objects for simple tooling).

**Per-row fields:**

| Field | Type | Notes |
|-------|------|--------|
| `skills` | string[] | e.g. `["relevance-first-asks"]` |
| `query` | string | User question text; from paste or approved summary |
| `files` | string[] | Optional paths relevant to scenario; often `[]` until scenario needs them |
| `expected_behavior` | string[] | **Empty or placeholder** until matching pasted excerpt exists; then concrete bullets |
| `evidence_ref` | string | Chat message id, paste label, or exact user approval line from thread; required for any non-empty `expected_behavior` |

**Hygiene:** No fabricated threads. Rows with real expected behavior must cite `evidence_ref`. Gaps documented in `REFERENCE.md` under **Pending approved excerpts**.

**Stub row (shape reference):**

```json
{
  "skills": ["relevance-first-asks"],
  "query": "[paste user question text here]",
  "files": [],
  "expected_behavior": [],
  "evidence_ref": "[chat message id or user approval line]"
}
```

**Candidate scenario labels (from gap analysis — for row titles or comments only until evidence exists):**

- Single clear question → relevance-first opening; proportional depth.
- User wants more depth → expansion after explicit signal.
- Bundled or multi-part prompt → staged or clarified lead.
- Missing grounding → clarification before long narrative.
- Partial confidence → uncertainty stated; confirmation path named.

---

## 6. Eval evidence policy

- **Authorized:** Chat excerpts the user pastes, or text the user labels approved in thread.
- **Not authorized:** Invented dialog, synthetic “user said” without approval.
- **Illustration in EXAMPLES.md:** Quote user-pasted excerpts when showing a scenario; paraphrase only when user marks material as approved summary.

---

## 7. Phase B implementation order (one primary file per checkpoint)

After user approves this architecture in chat:

1. `SKILL.md` — skeleton then full draft (single checkpoint).
2. `REFERENCE.md` — terminology, links, evidence rules, pending slots.
3. `EXAMPLES.md` — templates + pairs / pending slots.
4. `WORKFLOWS.md` — checklists.
5. `evals/relevance-skill.json` — schema + stubs; populate `expected_behavior` only as approved evidence arrives (may stay sparse in first pass).

**Tiny cross-link tweaks** in the same file’s checkpoint only when necessary; user may OK in the same approval message.

---

## 8. Phase C (optional)

Copy or adapt approved package to `packages/claude-dev-env/skills/<name>/` when the user requests dev-env bundling; mirror file set; fix cross-links to new root.

---

## 9. End-state inventory (paths to exist after Phase B)

| Path | One-line purpose |
|------|------------------|
| `concise-ask-workspace/ARCHITECTURE.md` | End-state map, load order, schema, milestones |
| `concise-ask-workspace/gap-analysis.md` | Design input; hypothesis until excerpt-backed evals exist |
| `concise-ask-workspace/SKILL.md` | Skill entry with frontmatter and TOC links |
| `concise-ask-workspace/REFERENCE.md` | Terms, Anthropic links, evidence policy, pending excerpts |
| `concise-ask-workspace/EXAMPLES.md` | Template + example pairs (or pending slots) |
| `concise-ask-workspace/WORKFLOWS.md` | Disambiguation-first and depth-on-request checklists |
| `concise-ask-workspace/evals/relevance-skill.json` | Eval rows with evidence-backed behavior only |

---

## 10. Quality pass before each handoff

- Third-person `description` in `SKILL.md`.
- Consistent use of stable vocabulary (§opening paragraph).
- `SKILL.md` links one level deep; forward-slash paths in new content.
- Multi-step flows represented as checklists in `WORKFLOWS.md`.

---

*Phase A deliverable: this file. Phase B starts only after explicit user approval or edited approval in chat.*
