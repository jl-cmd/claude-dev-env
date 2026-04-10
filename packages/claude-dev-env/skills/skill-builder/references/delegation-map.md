# Delegation Map

How the skill-builder orchestrator integrates with external skills at each phase.

## Phase 1: Identify Gaps -- This Orchestrator

No external delegation. The orchestrator guides a conversation with the user to document what fails without a skill.

**Output:** `[skill-name]-workspace/gap-analysis.md` using the template at `templates/gap-analysis.md`.

## Phase 2: Build Evals -- This Orchestrator

No external delegation. The orchestrator helps the user transform gaps into eval scenarios.

**Output:** `[skill-name]-workspace/evals/evals.json` using the template at `templates/eval-scenario.json`.

**Baseline runs:** Spawn subagents WITHOUT any skill for each eval scenario. These run as background Agent tasks.

## Phase 3: Write Skill -- Delegate to `/skill-writer`

**Full package path:** If the user approved a package plan from `prompt-generator/templates/skill-from-ground-up.md` (net-new) or `prompt-generator/templates/skill-refinement-package.md` (existing baseline), paste the approved architecture summary, baseline inventory, planned deltas, and checkpoint list into the skill-writer handoff so file order and scope stay aligned.

Invoke `/skill-writer` with the following context in your prompt:

```
Create a skill based on this gap analysis and eval scenarios.

Gap analysis: [paste or reference gap-analysis.md]
Eval scenarios: [paste or reference evals.json expected_output fields]
Baseline failures: [summarize what Claude got wrong without the skill]

Constraint: Write the minimum instructions needed to address these specific gaps.
Do not over-document. Every line must serve a documented gap.
```

skill-writer handles: type classification, degree of freedom, frontmatter, body structure, progressive disclosure, self-check.

**Output:** The skill's SKILL.md (and optional REFERENCE.md, scripts, etc.)

## Phase 4: Test -- Delegate to skill-creator Infrastructure

The skill-creator plugin provides the eval infrastructure. Reference its components directly:

### Spawning test runs

For each eval, spawn TWO subagents in the SAME turn (parallel):

**With-skill subagent:**
```
Execute this task:
- Read the skill at [path-to-skill]/SKILL.md and follow its instructions
- Task: [eval prompt from evals.json]
- Input files: [eval files if any]
- Save all output files to: [workspace]/iteration-N/eval-[name]/with_skill/outputs/
- Save a transcript of your complete work to: [workspace]/iteration-N/eval-[name]/with_skill/transcript.md
- At the end, write a metrics.json with tool call counts and file list
```

**Without-skill subagent** (baseline):
For iteration-1, reuse baseline results from Phase 2 (iteration-0). For later iterations, the original baseline persists.

### Grading

Read the grading agent instructions from the skill-creator plugin:
`[skill-creator-plugin-path]/agents/grader.md`

Spawn a grader subagent for each run with:
- The expectations from evals.json
- The transcript path
- The outputs directory

**Output:** `grading.json` in each run directory.

### Benchmarking

Run the aggregation script from the skill-creator plugin directory:
```bash
cd [skill-creator-plugin-path] && python -m scripts.aggregate_benchmark [workspace]/iteration-N --skill-name [name]
```

**Output:** `benchmark.json` and `benchmark.md` in the iteration directory.

### Eval Viewer

Launch the viewer from the skill-creator plugin:
```bash
python [skill-creator-plugin-path]/eval-viewer/generate_review.py \
  [workspace]/iteration-N \
  --skill-name "[name]" \
  --benchmark [workspace]/iteration-N/benchmark.json
```

For iteration 2+, add: `--previous-workspace [workspace]/iteration-[N-1]`

If no browser/display available, add: `--static [workspace]/iteration-N/review.html`

**Output:** Browser-based reviewer where the user inspects outputs and leaves feedback.

### Finding the skill-creator plugin path

The skill-creator plugin is installed at a path like:
`~/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/`

To find it dynamically, search for the skill-creator SKILL.md:
```bash
find ~/.claude/plugins -name "SKILL.md" -path "*/skill-creator/*" 2>/dev/null | head -1
```

Then derive the plugin root from that path.

## Phase 5: Iterate -- This Orchestrator + `/skill-writer`

The orchestrator reads feedback.json and transcripts, synthesizes observations, then delegates refinement to `/skill-writer`:

```
Refine this existing skill based on these observations from testing.

Current SKILL.md: [paste or reference]
User feedback: [from feedback.json]
Behavioral observations: [from transcript analysis]

Specific issues to address:
1. [Issue from feedback]
2. [Issue from observation]

Constraint: Only change what the feedback demands. Do not reorganize working content.
```

Then return to Phase 4 with the refined skill.

## Phase 6: Polish -- Delegate to skill-creator Description Optimizer

The skill-creator plugin includes a description optimization loop:

### Trigger eval generation

Generate 20 realistic eval queries (10 should-trigger, 10 should-not-trigger). Use the HTML review template from:
`[skill-creator-plugin-path]/assets/eval_review.html`

### Optimization loop

```bash
cd [skill-creator-plugin-path] && python -m scripts.run_loop \
  --eval-set [path-to-trigger-eval.json] \
  --skill-path [path-to-skill] \
  --model [current-model-id] \
  --max-iterations 5 \
  --verbose
```

### Final validation

Run the skill-writer self-check rubric (from skill-writer's Step 9) against the finished skill. All items must pass.
