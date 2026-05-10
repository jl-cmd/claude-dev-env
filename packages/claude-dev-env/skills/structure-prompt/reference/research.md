# When the skill needs information that isn't in the input

Some spokes need information the input prompt doesn't include — like the line number where an identifier lives, the canonical example for a category, or the real value to put where a placeholder sits. This file describes how to find that information from real sources.

## Where to look, in order

1. **The sibling rubric file.** When the calling framework provides a companion rubric (typically at `../category_rubrics/<same-name>.md` in audit-rubric layouts, but the path is framework-specific), read it first. The rubric often spells out the canonical example, the instantiation recipe, and the category-specific failure-mode noun. When no sibling rubric exists for the input prompt, skip this source and proceed to the companion artifact.

2. **The companion artifact.** When the rubric points at a sibling prompt as a worked example (e.g., "see `category-a-api-contracts.md` for the canonical diff"), read that sibling and use its diff or framework as the reference.

3. **The user-supplied context.** When the user pasted an artifact alongside the prompt — a diff, a PR URL, a file dump — use it directly.

4. **AskUserQuestion.** When the three sources above turn up nothing, ask the user via the AskUserQuestion tool. Phrase the question around the specific blocker (e.g., "Which artifact should I instantiate against?") and offer two to four concrete options.

## What counts as evidence

A change earns its place in the rewritten prompt when one of these is true:
- The rubric file states it
- The sibling artifact contains it (the line number is real, the identifier sits in the diff)
- The user-pasted context contains it (the value sits in the prompt body the user supplied, in a fenced block within it, or in an artifact the user pasted alongside the prompt)
- The user supplied it via an AskUserQuestion answer

When none of the four holds, the spoke leaves the prompt as-is and notes the gap in the location [`output-contract.md`](output-contract.md) defines for the active emission mode. The deferral itself is mandatory — see the [no silent no-op](output-contract.md#disposition-invariants) invariant.

## Tone of the AskUserQuestion

Use everyday phrasing. Tell the user what's blocked and what answers would unblock it.

| What the spoke needs | Question shape |
|---|---|
| Which PR or artifact to instantiate against | "I have placeholders in the prompt. Which artifact should I fill them with?" |
| Which scope of source material to inline | "Should I inline the full diff, the changed files only, or specific paths?" |
| Which sub-bucket is the canonical case | "The framework has six similarly-weighted sub-buckets. Which one is the canonical case for this category?" |
