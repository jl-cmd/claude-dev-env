---
name: tdd-team
description: "Spawn an orchestrated TDD agent team (planner, tester, implementer, validator) to build features or fix bugs via Red-Green-Refactor. Use when the user says /tdd-team, 'TDD team', 'agent team for this', 'have a team build this', or describes a non-trivial implementation task they want done with test-driven development and parallel agents. Also triggers on 'agentically', 'orchestrated team', or 'planner implementer tester validator'."
---

# TDD Team

Spawn an orchestrated team of 4 agents that implements a feature or fix using strict Test-Driven Development: Plan -> RED (failing tests) -> GREEN (minimum code to pass) -> Validate.

## When to use

- Non-trivial features requiring 3+ files changed
- Bug fixes where the fix needs tests proving the bug exists first
- Any task where the user says "TDD" and "team" or "agentically"

## Arguments

The full task description follows the command. Example:
```
/tdd-team fix proportional split distribution when item prices exceed order total
```

## Workflow

### Phase 1: Setup

1. **Create team** via TeamCreate with a name derived from the task (kebab-case, max 30 chars)
2. **Create tasks** with dependencies:
   - #1 PLAN — blocked by nothing
   - #2-N RED — blocked by #1
   - #N+1 GREEN — blocked by all RED tasks
   - #LAST VALIDATE — blocked by GREEN task
3. **Spawn 4 agents** (all at once for parallel startup):
   - `planner` (team-lead) — reads code, designs the approach, defines file ownership so agents work independently, and messages teammates with clear assignments
   - `tester` (team-implementer) — writes failing tests that define the expected behavior before implementation exists, establishing the contract the code must satisfy
   - `implementer` (team-implementer) — writes the minimum production code to satisfy the test contracts, keeping scope tight to keep all behavior tested
   - `validator` (team-reviewer) — runs the full test suite to catch regressions across files, and verifies the feature works end-to-end

### Phase 2: Orchestrate

As the team lead, your job is to:
- **Nudge blocked agents** when upstream tasks complete (send messages)
- **Shutdown idle agents** when all their tasks are done (send shutdown_request)
- **Report progress** to the user at milestones (plan done, tests written, implementation done, validation complete)
- **Fix coordination issues** (e.g., tester waiting for planner who already finished)

### Phase 3: Cleanup

After validator reports success:
1. Shutdown all remaining agents
2. Clean up any temporary files, scripts, or helper files created during iteration
3. Delete the team via TeamDelete
4. Run `python -m pytest tests/ -q` to confirm final count
5. Commit with descriptive message
6. Report summary to user

## Agent Prompts

Each agent receives a structured prompt containing:

### Common context (all agents get this)
- The task description from the user
- Working directory path
- Code rules reminder: no magic values, no abbreviations, complete type hints, no new inline comments, imports at top, constants in config/
- Collaboration guidance: flag ambiguity or uncertainty to teammates and use [PLACEHOLDER] for values you have not verified. Your role contributes to a specific phase of the TDD cycle — the separation between phases is what makes TDD effective.
- Anti-test-fixation: write general solutions that work for all valid inputs, not just the specific test cases. Tests verify correctness -- they do not define the solution. If a test seems incorrect, flag it rather than working around it.
- Commit-and-execute: choose an approach and commit to it. Avoid revisiting decisions unless new information directly contradicts your reasoning. Course-correct later if needed.

### Planner-specific
- Read the relevant source files before designing
- Design the implementation with function signatures and return types
- Define file ownership boundaries (tester owns test files, implementer owns production files)
- Create the task breakdown with specific test cases to write
- Mark task complete and message teammates with assignments
- If the scope is unclear or requirements are ambiguous, flag this to the orchestrator and propose assumptions for confirmation
- Commit to an approach and communicate it clearly to teammates -- avoid revisiting architectural decisions unless implementation reveals a fundamental problem

### Tester-specific
- Wait for planner to complete (check TaskList)
- Write FAILING tests that reproduce the desired behavior
- Use existing test patterns from the project (read test files first)
- Mock external calls, use patch.dict for env vars
- Tests must FAIL before implementation — that's the point
- Mark each task complete, check TaskList for next work
- If a test case from the plan is ambiguous about expected behavior, ask the planner for clarification — a clear test is the most valuable deliverable

### Implementer-specific
- Wait for tester to complete (check TaskList)
- Read the failing tests to understand expected behavior
- Write MINIMUM code to make tests pass — no extras
- Run the specific test file to verify green
- Mark task complete, check TaskList for next work
- Write general solutions that work for all valid inputs -- never hard-code values or create implementations that only satisfy specific test assertions
- If a failing test seems to test the wrong behavior or has a bug in the test itself, flag it to the validator for review

### Validator-specific
- Wait for implementer to complete (check TaskList)
- Run full test suite (`python -m pytest tests/ -q`)
- Fix test regressions from the new code (e.g., unmocked new functions in existing tests)
- Verify new functions exist and are wired correctly
- Verify the implementation fully captures the planner's design (all planned functions exist, signatures match, edge cases covered)
- Verify the implementation follows project code rules (centralized config, complete type hints, full-word naming, self-documenting code)
- Report: test count, pass/fail, regressions found and fixed, plan coverage assessment, code rules compliance
- If regressions trace to a design issue, report the root cause to the orchestrator for a targeted follow-up task

## Task Sizing

The planner decides how many RED tasks to create based on the scope:
- **Small fix** (1 function): 1 RED task, 1 GREEN task
- **Medium feature** (2-3 functions): 2-3 RED tasks (can be parallel), 1-2 GREEN tasks
- **Large feature** (4+ functions across files): 3-5 RED tasks, 2-3 GREEN tasks with dependencies

## Error Recovery

- If tester writes tests that import non-existent constants, that's expected (RED phase)
- If implementer's code breaks existing tests, validator fixes the regressions
- If validator finds issues, create a new fix task and assign to implementer
- If an agent goes idle repeatedly without progress, send a message with specific instructions
- When encountering obstacles, use standard tools and approaches -- do not create helper scripts or workarounds to bypass problems; flag the issue for resolution

## Ownership Boundaries

Each agent owns its phase — this separation ensures the TDD cycle produces reliable results:

- The tester writes tests; the implementer writes production code. This separation ensures tests define behavior independently of implementation.
- Failing tests exist before any production code. This is the core of TDD — the test proves the requirement, then the code satisfies it.
- The validator runs after implementation. It catches regressions across files that are invisible to agents working on individual files.
- Shut down agents after their tasks complete. Idle agents consume context; active agents produce value.
