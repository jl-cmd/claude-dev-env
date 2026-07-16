# Session-log template blocks

The two verbatim HTML blocks the `session-log` skill drops into every session
page. The hub ([`../SKILL.md`](../SKILL.md)) points here from Step 1 / Step 2
(frontmatter) and Step 3 (notes).

## Frontmatter contract

The first child of `<body>`, inside an HTML comment. Substitute a concrete value
for every placeholder; `vault_context_retrieved` starts `false` and Step 3 sets
it.

```html
<!--
type: session-report
project: [name]
session: [N]
session_id: [uuid]
date: [YYYY-MM-DD]
status: completed|in-progress|blocked
blocked: true|false
vault_context_retrieved: true|false
tags: [session, [project-tag], [topic-tags]]
-->
```

## Notes block (Step 3)

Append one vault-context line. When the page already carries a notes /
references section, add a matching child element to that section; use the block
below only when the page has no such section.

```html
<h2>Notes</h2>
<ul>
  <!-- Pick exactly one of the two forms based on whether vault MCP tools fired this session: -->
  <li><strong>Vault context:</strong> Retrieved ([list of note paths])</li>
  <li><strong>Vault context:</strong> Not retrieved</li>
</ul>
```
