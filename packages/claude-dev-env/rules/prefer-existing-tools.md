# Prefer Existing Tools

**When this applies:** Before you build a tool, check, scanner, script, or library of your own.

## Rule

Search in this order, and stop at the first fit:

1. **Internal code.** Search the repository and its shared packages for a tool that already does the job. Reuse or extend it.
2. **An established open-source option.** Search for a plugin, package, or tool that already does the job.
3. **Your own code.** Build it only when steps 1 and 2 find nothing that fits.

Use an open-source option only when it meets all four conditions:

- It is secure: it has an active security process and no open critical advisory.
- It is well known in its field.
- It is widely used: many stars, downloads, or dependents.
- It is maintained: it had a release or commit in the last year.

Add only what the option lacks. Put custom rules in its own configuration format. Do not wrap it in a new layer of your own code.

## Report the choice

Tell the user which tool you chose before the work is marked ready. Give its name, link, license, and one number that shows how widely it is used. When you build your own code, name what you searched and why each candidate did not fit.

## Why

Code of your own is code you maintain alone. A trusted tool carries fixes and new patterns from its community, and its users find its defects first.

## Sibling rules

| Rule | Role |
|---|---|
| [`explore-thoroughly.md`](explore-thoroughly.md) | Read what exists before you propose a change |
| [`verify-before-asking.md`](verify-before-asking.md) | Answer a question with a tool before you ask it |
