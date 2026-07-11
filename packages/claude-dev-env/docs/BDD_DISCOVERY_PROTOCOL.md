# BDD Discovery Protocol

This protocol guides Claude through **Example Mapping** to discover test ideas from user requests before writing code. Work **breadth-first**: map rules, examples, and unknowns first; park unresolved questions instead of guessing. Based on Smart & Molak *BDD in Action* §6.4 and Dan North, "Introducing BDD" (2006).

> §6.4.2: "The team discuss the rules and asks for an example of each. Examples are often described using a short phrase that starts with the words 'The one where ...' This notation, originally described by Daniel Terhorst-North, is known as the 'Friends episode notation', from the 90s TV series of the same name."

> §6.4.4: "Questions that can't be answered immediately are noted as pink cards."

> §6.4.5: "Example Mapping sessions should be quite short; 25–30 minutes is usually enough to get through a story."

## Core algorithm

1. **State the rule or feature** — Restate until the rule is clearly defined. *Exit:* shared understanding of what we are exploring.

2. **Generate examples** — Produce 3–5 phrases using **"The one where …"** notation, simple to complex. *Exit:* examples cover the rule’s scope without duplicating the same case.

3. **Probe the first unchecked example** — Ask: *What if …?* *Is this always the case?* *Are there examples where this rule behaves differently?* *Exit:* all three probes asked for this example.

4. **Evaluate answers** — When a new rule emerges, return to Step 3 for that rule. New edge cases may become **new rules** (add 2–3 examples each). Questions you cannot answer become **parked items**. *Exit:* probes for this example are processed.

5. **Next example** — Repeat steps 3–4. *Exit:* all examples probed.

6. **Compile and confirm** — In steady state, present a full compile of rules, examples, and parking lot. Ask: "Does this Example Map cover the behavior you need? Any rules or examples to add, remove, or refine?" *Exit:* user confirms; exit when user confirms.

7. **Time-box and exit** — Keep discovery within ~25–30 minutes when possible; also **exit** when tests are under way or the session ends.

> "What to call your test is easy: it's a sentence describing the next behaviour in which you are interested." — Dan North (2006)

## Worked Example: Theme Asset Release Date Validation

- **Rule:** A theme asset must not go live before its configured release date.
- **Examples (the one where …):**
  - … the release date is tomorrow and today’s import runs — should block or warn
  - … the release date was last week — should allow publish
  - … the release date field is empty — should use policy default
  - … the release date is updated after a draft was already scheduled — should re-validate against policy
- **Probe:** *What if the server timezone is UTC but the editor is local?* → Surfaces a **new rule** about timezone for "release day."
- **New rule examples:** same calendar date in UTC vs local; DST boundary.
- **Parked:** certification API does not return a timezone — follow up with vendor.

## Using This Protocol

- State the business rule clearly
- Generate concrete examples (the one where ...)
- Probe each example with three question forms
- Capture open questions as a parked list for later resolution
- Compile and confirm the Example Map with the user
- Proceed to test writing only after user approval

## References

- Smart & Molak, *BDD in Action* 2e, Chapter 6, §6.4 (Example Mapping)
- Dan North, "Introducing BDD" (2006), https://dannorth.net/blog/introducing-bdd/
