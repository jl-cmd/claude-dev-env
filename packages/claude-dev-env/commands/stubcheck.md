---
description: Detect and fix stub implementations in code and plans with agent/skill recommendations
allowed-tools: Read, Grep, Glob, Skill
---

Execute comprehensive stub detection using the stub-detector skill to identify incomplete implementations and recommend appropriate solutions.

## Process

1. **Invoke stub-detector skill** to scan current project
2. Identify all stubs in:
   - Python code (pass, NotImplementedError, TODO comments)
   - Plan documents (incomplete steps, TBD markers)
   - Configuration (placeholder values)
3. Classify by severity (CRITICAL/HIGH/MEDIUM/LOW)
4. Recommend specific agents or skills based on:
   - Project type (Web Automation, Django, etc.)
   - Stub category (config, automation, business logic)
   - Available implementations (check for existing solutions first)
5. Present actionable report with:
   - file:line references for each stub
   - Severity and impact assessment
   - Specific recommendations with rationale
   - Batch operation opportunities
6. Offer immediate actions to fix CRITICAL stubs

## Stub Detection Patterns

**Code stubs to find:**
```
pass statements
NotImplementedError
TODO/FIXME/HACK comments
Empty functions with only docstrings
Placeholder returns (return None when type suggests otherwise)
```

**Documentation stubs to find:**
```
[TODO] or [TBD] markers
"To be implemented" sections
Incomplete step descriptions
Placeholder text in plans
Missing details in implementation guides
```

## Agent/Skill Recommendation Logic

**Web Automation stubs →**
- Automation: automation-agent or automation skill
- Google Sheets: sheets orchestrator agent
- Config issues: config-extraction skill

**Web framework stubs →**
- Models/views/forms: domain-specific agent
- Business logic: domain-specific agent
- Domain features: domain-specific agent

**General stubs →**
- Follow TDD workflow from CLAUDE.md
- Follow CODE_RULES.md standards (via clean-coder agent)
- Check for existing shared utilities first

## Output Format

Provide a clear summary report showing:
- Total stubs found with severity breakdown
- Grouped by category for batch processing
- Specific recommendations for each stub
- Immediate action options for user

Example:
```
Found 7 stubs (3 CRITICAL, 2 HIGH, 2 MEDIUM)

[CRITICAL] services/file_processor.py:45
Incomplete matching logic
→ Recommendation: Use FileProcessor (already available)
→ Action: Refactor to use shared utility

[HIGH] tests/test_integration.py:234
Missing integration test
→ Recommendation: Follow TDD workflow

Would you like me to fix CRITICAL stubs now?
```

**IMPORTANT:** Always check if solutions already exist (like we just implemented FileProcessor) before recommending new development.
