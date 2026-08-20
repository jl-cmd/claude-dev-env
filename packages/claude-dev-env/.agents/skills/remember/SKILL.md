---
name: remember
description: "Save a decision, gotcha, or architectural choice to the Obsidian vault. User-initiated only."
disable-model-invocation: true
argument-hint: "[what to remember]"
---

# Remember

Save a structured decision, gotcha, or architectural choice to the Obsidian vault as an individual note in the `decisions/` directory.

## Instructions

1. **Parse the input.** Extract the core decision, fact, or gotcha from `$ARGUMENTS`.

2. **Classify the type** based on content:
   - `decision` -- a choice made between alternatives (e.g., "chose Groq over Gemini")
   - `procedural` -- a how-to or workflow step (e.g., "deploy requires manual cookie refresh first")
   - `fact` -- an objective piece of information (e.g., "YNAB API cannot overwrite split transactions")
   - `gotcha` -- a surprising behavior or trap (e.g., "Amazon blocks Cloud Run datacenter IPs")

3. **Infer the project name** from conversation context (git remote, working directory, or topic).

4. **Generate a short title** (3-7 words) that captures the essence.

5. **Write to vault** via `mcp__obsidian__write_note`:

   **Path:** `decisions/[Project] - [Short Title].md`

   **Frontmatter:**
   ```yaml
   name: [Short Title from step 4]
   description: [One-line summary of the decision/fact/gotcha -- concise enough for frontmatter search]
   type: [decision|procedural|fact|gotcha]
   project: [Project Name]
   date: [YYYY-MM-DD]
   status: Active
   tags: [relevant, tags]
   ```

   **Body format depends on type:**

   For `decision`:
   ```
   **Decision:** [One sentence stating what was decided]
   **Reasoning:** [Why this was chosen]
   **Alternatives considered:** [What was rejected and why]
   **Consequences:** [What this means going forward]
   ```

   For `gotcha`:
   ```
   **Gotcha:** [One sentence stating the surprising behavior]
   **Symptom:** [What you observe when you hit this]
   **Fix:** [How to work around or resolve it]
   ```

   For `fact` or `procedural`:
   ```
   [The fact or procedure, written clearly in 1-3 sentences with relevant context]
   ```

6. **Confirm** what was saved and where (vault path).
