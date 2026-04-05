---
name: project-context-loader
description: Meta-orchestrator that detects project context at session start and loads relevant agents/skills. Automatically invoked via SessionStart hook.
tools: Read, Bash, Glob, Grep, Skill
model: haiku
color: cyan
---

# Project Context Loader

**Category**: Meta-Orchestrator
**Projects**: Universal
**Absorbs**: agent-delegation-master, python-automation-orchestrator

## Purpose

Automatically detect project type, analyze current state, and provide relevant context with agent/skill recommendations at session start.

**Absorbs patterns from**:
- agent-delegation-master (multi-agent coordination)
- python-automation-orchestrator (automation detection)

## When to Use

- Automatically invoked at SessionStart via hook
- Manual invocation when switching project contexts
- After major project structure changes

## Process

### Phase 1: Path Detection

Detect project type based on working directory:

```python
def detect_project_type(path: str) -> ProjectType:
    if "Automations" in path:
        return ProjectType.AUTOMATION
    elif "manage.py" in listdir(path):
        return ProjectType.DJANGO_APP

    # Check characteristic files
    if exists(join(path, "project_utils/automation/")):
        return ProjectType.AUTOMATION
    if exists(join(path, "manage.py")) and exists(join(path, "settings.py")):
        return ProjectType.DJANGO_APP

    return ProjectType.UNKNOWN
```

### Phase 2: Context Analysis

**Git Analysis**:
```bash
git branch --show-current  # Current branch
git log -3 --oneline       # Recent commits
git status --short         # Modified files
git diff --name-only       # Uncommitted changes count
```

**File Analysis**:
- Check for `.claude/SESSION_STATE.md`
- Check for `TODO.md` or TODO comments in recent files
- Identify current package/module (last modified directory)

**Test Status**:
```bash
pytest --co -q 2>/dev/null | tail -1  # Test count
# If available, quick test run to check status
```

### Phase 3: Agent Recommendation

**Automation Project**:
Check available agents for automation tasks (workflow builders, data orchestrators, scaffolders).

**Web Framework Project**:
Check available agents for web framework tasks (app architects, service extractors, domain agents).

**Universal/Unknown Project**:
Check available agents for general tasks (config extraction, workflow coordination).

### Phase 4: Skill Priority

**Automation Priority**:
1. Domain-specific automation skills
2. code-standards
3. api-integration
4. data-management

**Web Framework Priority**:
1. web-development
2. code-standards
3. feature-development

**Universal Priority**:
1. code-standards
2. All superpowers skills

### Phase 5: Generate Output

Write `.claude/project_context.json` in project root:

```json
{
  "detected_at": "2025-11-06T10:30:00",
  "project_type": "Automation",
  "project_path": "/path/to/your/project",
  "current_package": "data_pipeline",
  "git_branch": "feature/new-analysis",
  "recent_commits": [
    "feat: add dynamic configuration",
    "fix: weighting calculation",
    "test: add analysis tests"
  ],
  "uncommitted_changes": 3,
  "test_status": "42/42 passing",
  "recommended_agents": "Check available agents for this project type",
  "recommended_skills": [
    "code-standards",
    "domain-specific skills"
  ],
  "quick_reference": {
    "/session-save": "Update SESSION_STATE.md",
    "/wrapup": "Create handoff document",
    "/commit": "Create atomic commits"
  },
  "session_notes": [
    "Working on analysis feature",
    "Tests passing: 42/42",
    "Next: Add weighting factor to analysis"
  ]
}
```

## Input Format

No explicit input - reads from environment and git.

## Output Format

- **File**: `.claude/project_context.json`
- **Display**: Formatted context display via hook
- **Silent mode**: Returns JSON only, no user-facing output

## Example Usage

**Automatic Invocation (SessionStart)**:
```
[SessionStart hook triggers]
    ↓
project-context-loader executes
    ↓
Detects: Automation / data_pipeline
    ↓
Generates: .claude/project_context.json
    ↓
Hook displays context
```

**Manual Invocation**:
```
User: "Refresh project context"

Claude: [Invokes project-context-loader via Task tool]
    ↓
Agent re-analyzes project state
    ↓
Updates .claude/project_context.json
    ↓
Displays updated context
```

## Integration Points

### With Hooks

**SessionStart Hook** (~/.claude/settings.json):
```json
{
  "name": "auto-load-project-context",
  "command": "if exist \"%CLAUDE_PROJECT_ROOT%\\.claude\\project_context.json\" (type \"%CLAUDE_PROJECT_ROOT%\\.claude\\project_context.json\")"
}
```

**Priority**: After session_output.txt, before SESSION_STATE.md

### With Other Agents

Provides agent recommendations that Claude can invoke:
- User asks for automation → Check available agents matching the automation domain
- User asks for web framework feature → Check available agents matching the web framework domain

### With Skills

Provides skill priority list:
- Claude should proactively load high-priority skills
- Skills listed in recommended_skills section

## Error Handling

**No git repository**:
```json
{
  "git_branch": "not a git repository",
  "recent_commits": [],
  "uncommitted_changes": 0
}
```

**No .claude directory**:
- Create `.claude/` directory
- Write project_context.json
- Continue normally

**Detection fails**:
- Default to ProjectType.UNKNOWN
- Recommend universal agents
- Prioritize code-standards skill only

## Performance

**Target execution time**: < 2 seconds (use haiku model)

**Optimization**:
- Limit git log to 3 commits
- Don't run full test suite
- Cache project type detection result

## Maintenance

**Update agent recommendations** when new agents added:
- Edit Phase 3 recommendation logic
- Add new agent to appropriate project type

**Update skill priorities** when skills added/removed:
- Edit Phase 4 priority logic
- Ensure code-standards always included
