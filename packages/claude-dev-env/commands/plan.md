Plan a feature with full validation workflow.

> **MANDATORY:** Load `~/.claude/docs/CODE_RULES.md` for all code standards.

## Workflow (MANDATORY - NO SKIPPING STEPS)

### Phase 1: Design
1. **Invoke `plan` skill** - Discover configs, design through dialogue

### Phase 2: Plan
2. **Invoke `write-plan` skill** - Create detailed TDD implementation plan (CODE_RULES.md compliant)
3. **Invoke `review-plan` skill** - Validate plan against CODE_RULES.md standards
4. **Fix violations** - If review-plan finds issues, fix before proceeding

### Phase 3: Approval (NEW PRs only)
5. **Invoke `plan-checkpoint` skill** - Generate summary gist for reviewer approval
6. **Wait for approval** - Do not proceed until approved

### Phase 4: Execute
7. **Invoke `plan-executor` agent** - Execute with full standards enforcement
8. **Invoke `readability-review` skill** - Validate written code against CODE_RULES.md

### Phase 5: Commit & Review
9. **Invoke `/commit`** - Create atomic commits
10. **Push branch** - Push to GitHub (NO PR yet); the git pre-push hook installed via `npx claude-dev-env` fires automatically and blocks on any violation
11. **Wait for commit review** - User reviews on GitHub
12. **Create PR** - Only after user approves commit

## Key Rules

- NEVER offer execution until review-plan passes with ZERO violations
- For NEW PRs: wait for reviewer approval on checkpoint before implementing
- For PR REVIEW FIXES: skip checkpoint, proceed directly to execution
- NEVER push if the git pre-push hook fails (it fires automatically via `npx claude-dev-env`)
- NEVER create PR until user explicitly approves pushed commit

## Skills & Agents Reference

| Step | Tool | Purpose |
|------|------|---------|
| Design | `plan` skill | Collaborative design with config discovery |
| Write | `write-plan` skill | TDD plan with CODE_RULES.md compliance |
| Review Plan | `review-plan` skill | Validate plan against standards |
| Execute | `plan-executor` agent | Implement with standards enforcement |
| Review Code | `readability-review` skill | Validate code before commit |

## Standards Reference

All code quality standards are in `~/.claude/docs/CODE_RULES.md`:
- Self-documenting code (no comments)
- Centralized configs (reuse existing)
- No magic values
- No abbreviations
- Complete type hints
- All imports shown

## Usage

```
/plan add user authentication
/plan refactor the payment system
```
