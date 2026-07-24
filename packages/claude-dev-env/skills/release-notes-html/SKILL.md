---
name: release-notes-html
description: Build a polished self-contained HTML product launch and release-notes page from work completed in the current session, using available repository state, source-of-truth files, tests, approvals, artifacts, commits, pull requests, previews, and release evidence. Use when the user asks to build release notes, create a launch page, document completed work, produce feature-release HTML, or turn the session into product-facing release notes.
when_to_use: Invoke for requests such as "build release notes for the work you've done," "create release notes HTML," "make a product launch page," "document this completed feature," or "turn our work into a polished release page."
disable-model-invocation: false
user-invocable: true
model: inherit
effort: high
---

Build a polished, self-contained HTML product launch and release-notes page for the work completed in this session.

Use the current conversation, task history, repository state, completed changes, test results, approvals, generated artifacts, plans, handoffs, file paths, commits, pull requests, and other evidence already available in the session as the source of truth.

Recover the feature name, purpose, capabilities, specifications, usage instructions, validation results, release status, and first production use directly from the available context. Inspect relevant files and repository artifacts when access is available.

Ask one concise clarification question only when the session does not contain enough information to identify the completed feature or its supporting evidence.

## Execution

Act as the orchestrator.

Create a task ledger covering:

- Evidence collection
- Feature and release-state synthesis
- Page structure
- HTML creation
- Evidence audit
- Visual and browser review
- Final delivery

Assign file inspection and HTML creation to executor workers when worker tools are available. The orchestrator owns the structure, factual acceptance, and final audit.

## Evidence rules

Use only facts supported by:

- The current conversation
- Current session tasks and results
- Repository files and git state
- Named source-of-truth files
- Generated reports, ledgers, plans, and acceptance packets
- Explicit user approvals
- Test and CI output already available
- Pull request and commit data available to the session

Locate the strongest source for each claim.

Preserve exact:

- Feature and package names
- File paths
- Commands
- Dimensions
- Flags
- Identifiers
- JSON keys
- Test totals
- Pull request numbers
- Branch and release status

Place exact technical values inside `<code>` elements.

Include previews, approval claims, test counts, merged status, and production-use claims when the available evidence supports them.

## Page content

Produce one cohesive launch page with a clear hierarchy that a non-engineer can skim.

Include the sections that the completed work supports:

1. Hero with the feature name and primary benefit
2. A brief explanation of what the feature enables
3. Major capability highlights
4. How to run or use it
5. Exact specifications
6. Quality, validation, and safety coverage
7. First production use, debut project, or approved example
8. Current availability or completion status

Adapt the section names and structure to the actual project. Give every heading a useful takeaway.

## Tone

Write the page as the launch of a completed new capability.

Use present-state product copy focused on:

- What it is
- What the user can accomplish
- How it works
- How to use it
- What guarantees or validations it provides
- Where it has already been applied

Keep implementation history, discarded approaches, debugging chronology, and internal justification outside the page unless they are essential to using the feature.

## Voice rules

The reader primarily absorbs headings, bolded leads, and the first sentence of each block.

1. Every title states a plain-language claim.
2. Each sentence carries one idea.
3. Lead with reader meaning, then explain the mechanism.
4. Explain specialized terms at first use.
5. Keep exact technical values verbatim inside `<code>` elements.
6. Limit cards to two sentences.
7. Limit list items to three sentences.
8. Give each section a one-sentence subtitle that adds information.
9. Make the complete story understandable from headings and bolded leads alone.
10. Use concise, active sentences.
11. Use present-state language throughout.
12. Give every important fact one clear location.

## Design

Create one valid HTML file with self-contained CSS. CDN-hosted fonts are acceptable.

Use:

- Strong visual hierarchy
- Spacious typography
- Scannable cards and sections
- Responsive desktop and narrow-screen layouts
- Accessible contrast
- Clear treatment of code, specifications, and commands
- An inviting product-launch presentation rather than dense documentation

Use an approved preview or product image when one is already available and supported by the session.

## Output location

Choose the output location from an explicit path already stated in the session.

When no output path has been established, write the file beside the project’s existing results, release, report, or acceptance artifacts using a clear name such as:

`RELEASE_NOTES.html`

Use the operating-system temporary directory only when no project location can be determined safely.

Write the file atomically and create its parent directory when required.

## Acceptance audit

Before delivery:

- Verify every factual claim against the available evidence.
- Review every heading for a clear takeaway.
- Review every sentence for one idea.
- Confirm specialized terms receive plain explanations.
- Confirm exact technical values remain verbatim.
- Confirm headings and bolded leads communicate the whole story.
- Confirm the page is readable at desktop and narrow browser widths.
- Confirm the output is one complete, valid HTML file.
- Open the completed page in Chrome or the available default browser when the environment supports it.
- Correct every issue found during the audit.

## Delivery

Reply with:

1. The full absolute path to the HTML file.
2. One sentence describing what the release-notes page covers.

Stop after delivering the completed page.
