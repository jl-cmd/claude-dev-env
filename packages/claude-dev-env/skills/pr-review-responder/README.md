# PR Review Responder Skill

Automatically find and respond to GitHub PR review comments before pushing code.

## What It Does

This skill helps you:
- Detect if your current branch has an open PR
- Find unresponded review comments from reviewers
- Match review comments to your recent code changes
- Draft concise, specific responses (format: `✅ **Fixed**: [what changed]`)
- Post responses directly to GitHub review comment threads

## When To Use

Use this skill:
- **Before every git push** when addressing PR feedback
- After committing fixes to reviewer comments
- When you want to notify reviewers what was addressed
- To speed up PR review cycles

## Files in This Package

- **SKILL.md**: Core instructions and step-by-step workflow for Claude
- **EXAMPLES.md**: 8 real-world examples with different scenarios
- **PRINCIPLES.md**: Theory and best practices for PR communication
- **README.md**: This file

## Quick Start

### Using with Claude

```bash
# 1. Make changes addressing PR feedback
git add .
git commit -m "fix: address PR feedback"

# 2. Activate the skill
"Respond to PR review comments"

# 3. Skill finds comments, drafts responses, shows them for approval
# 4. Confirm and push
git push
```

## Testing

Test the skill with these queries:

**Should activate**:
- "Respond to PR review comments"
- "Reply to code review feedback before pushing"
- "Find and respond to reviewer comments on my PR"
- "Post responses to review comments"

**Should NOT activate**:
- "Create a new PR" (different skill)
- "Review this code" (code review, not response)
- "What are the PR comments?" (just viewing, not responding)

## Requirements

- GitHub MCP server (`plugin:github:github`) authenticated
- Git repository with GitHub remote
- Current branch with an open PR
- Changes committed (not just staged)

## Integration Options

### As Slash Command

Add to `.claude/settings.json`:
```json
{
  "commands": {
    "/respond": "Use pr-review-responder skill to respond to PR comments"
  }
}
```

Usage: `/respond`

## Example Response Format

```
✅ **Fixed**: Removed wrapper class, using Path().read_bytes() directly
✅ **Fixed**: Extracted upload logic to storage.upload_file()
✅ **Fixed**: Moved animation timing from Python context to CSS
✅ **Fixed**: Added type hints (int, str, Optional[Dict])
📝 **Noted**: Will refactor to service layer in separate PR
```

## Troubleshooting

**"No PR found for this branch"**:
- Create PR first using MCP: `create_pull_request(owner=owner, repo=repo, title=title, body=body, head=head, base=base)`
- Ensure the branch has an associated open PR

**"No review comments found"**:
- PR might not have reviews yet
- Or all comments already responded to

**"Permission denied"**:
- Ensure the GitHub MCP server has write-scoped authentication
- Check repository write access

**"Cannot find matching changes"**:
- Review comments don't match files you modified
- Check that you committed the changes
- Comments might be on different files

## Best Practices

1. **Run before every push** - Make it part of your workflow
2. **Be specific** - Say what changed, not just "fixed"
3. **One response per comment** - Don't combine
4. **Acknowledge good catches** - "Good catch! Fixed by..."
5. **Keep it concise** - One sentence maximum

## Advanced Usage

See [EXAMPLES.md](EXAMPLES.md) for:
- Multiple commits addressing different comments
- Partial addressing (some comments fixed, some deferred)
- Handling conversation threads
- Custom response editing

See [PRINCIPLES.md](PRINCIPLES.md) for:
- Theory on PR communication
- Anti-patterns to avoid
- Cultural context for different teams
- Psychology of review responses

## Maintenance

**Updating the skill**:
1. Modify SKILL.md for instruction changes
2. Add examples to EXAMPLES.md
3. Update principles in PRINCIPLES.md
4. Restart Claude Code to reload

**Testing changes**:
```bash
# Test skill activation
"Respond to PR review comments"
```

## Version History

**v1.0.0** (2025-01-14):
- Initial release
- Support for inline code review comments
- Auto-detection of current PR
- Matching changes to comments
- Drafting responses with standard format
- Posting via GitHub API
- MCP-based GitHub tool integration

## Contributing

To improve this skill:
1. Add new examples to EXAMPLES.md
2. Document anti-patterns in PRINCIPLES.md
3. Test with various PR scenarios

## License

Part of the Claude Code skills library.
