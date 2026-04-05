# GitHub PR Summary Writing Guide for AI

Use this guide when writing pull request descriptions. Follow these best practices to create clear, professional, and reviewable PR summaries.

## Required Sections

### What (Changes)

- Concise statement of what was changed
- What files or systems were modified
- What functionality was added, removed, or improved
- Keep to 2-3 sentences maximum

### Why (Problem/Context)

- Explain the problem this PR solves
- Provide business or technical context
- Reference related issue numbers using `#123` or `Fixes #123`, `Closes #456`
- If no issue exists, briefly explain the motivation

### How (Approach/Solution)

- Describe your implementation approach
- Explain any design decisions or trade-offs
- Include architectural changes if applicable
- Note any breaking changes prominently

## Supporting Details

### Testing and Quality

- What tests were added/modified
- How to manually verify the changes (if applicable)
- Any areas of concern or limitations
- Performance impact (if relevant)

### Dependencies and Risk

- New dependencies introduced (if any)
- Backward compatibility status
- Potential side effects
- Migration steps (if needed)

## Optional but Valuable

### Related Issues/PRs

- Link to dependent PRs or issues
- Note any follow-up work needed

### Screenshots/Examples (for UI changes)

- Before/after comparisons when visual changes are involved

### Reviewer Guidance

- Specific areas to focus on
- Questions for reviewers
- Deployment considerations

## Tone and Style Guidelines

- Be clear and concise -- reviewers scan quickly
- Use second person sparingly -- focus on what the code does, not what the reviewer should do
- Avoid jargon -- explain technical terms if non-obvious
- Use markdown formatting -- bullets, code blocks, headers for readability
- Be honest about limitations -- acknowledge trade-offs and known issues
- Assume reviewers are unfamiliar -- provide sufficient context

## What to Avoid

- Vague statements like "fix bug" or "update code"
- AI-generated summaries without human verification
- Large walls of text -- break into sections
- Repeating information from commit messages
- References to temporary branch names or internal jargon without context

## Example Structure

```markdown
## Description
Brief 1-2 sentence overview of the change.

## Why
Problem/context and reference to related issue (#123).

## How
Implementation approach and design decisions.

## Testing
How this was tested and verified.

## Risk Assessment
Any breaking changes, dependencies, or concerns.
```
