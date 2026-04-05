# Initialize Session

You are starting a new task. Before proceeding, you MUST read and internalize the critical protocols from CLAUDE.md.

## MANDATORY PROTOCOL REVIEW

Read CLAUDE.md now and focus on:

### 1. AGENT-FIRST WORKFLOW (CRITICAL)

**BEFORE RESPONDING TO ANY USER MESSAGE:**
- ☐ What is the user asking for?
- ☐ Does ANY agent match this request?
- ☐ If yes → INVOKE THE AGENT via Task tool
- ☐ If no agent matches → Proceed with skills/direct implementation

**Agent Decision Tree:**
- Automation work → check available agents for automation patterns
- Web App Development → check available agents for framework-specific patterns
- Configuration/Architecture → config-extraction-agent, parallel-workflow-coordinator

**Never skip agent check to "save time" or because request "seems simple"**

### 2. SKILLS WORKFLOW (CRITICAL)

**Before ANY task:**
- ☐ List available skills in your mind
- ☐ Does ANY skill match this request?
- ☐ If yes → Use Skill tool to read and run it
- ☐ Announce which skill you're using
- ☐ Follow the skill exactly

**Mandatory skills to remember:**
- `code-standards` - For ALL code generation, planning, implementation
- `superpowers:test-driven-development` - For ANY feature/bugfix
- `superpowers:brainstorming` - BEFORE coding on design tasks
- `superpowers:systematic-debugging` - For bugs/failures
- `superpowers:verification-before-completion` - Before claiming work is done

### 3. TDD IS NON-NEGOTIABLE

**Red-Green-Refactor:**
1. **Red**: Write failing test FIRST. NO production code.
2. **Green**: MINIMUM code to pass test only.
3. **Refactor**: Assess improvements after green.

**If writing production code without failing test, STOP immediately.**

### 4. CODE STANDARDS (ENFORCED)

- No `Any` types - Use Union/Optional/generics
- No `# type: ignore` without justification
- All imports at top
- No files in project root
- Immutable data (frozen dataclasses)
- Small functions (5-15 lines, max 30)
- Max 2 nesting levels
- No comments (self-documenting code)
- No Unicode in print/debug (Windows compatibility)

### 5. RIGHT-SIZED ENGINEERING

**Always Do:**
- Extract constants and configuration
- Create reusable functions
- DRY from the start
- Single responsibility

**Never Do (Solo Scale):**
- Abstract base classes for single implementations
- Dependency injection frameworks
- Complex patterns
- Over-abstracted interfaces

## Common Rationalizations That Mean Failure

If you think:
- "This is too simple" → WRONG. Check agents/skills.
- "Let me just implement quickly" → WRONG. Check agents/skills first.
- "I'll gather context first" → WRONG. Agents/skills tell you HOW.
- "This doesn't need formal process" → WRONG. Process prevents mistakes.

## NOW PROCEED

You have reviewed the critical protocols. Apply them to the current task.

**Remember:**
1. Check agents FIRST
2. Check skills SECOND
3. Follow TDD ALWAYS
4. Build it right, but build it simple
