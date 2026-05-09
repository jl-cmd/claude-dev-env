# Skill Types

Source: [Lessons from Building Claude Code: How We Use Skills](thariq-x-post-skills.json)

> "After cataloging all of our skills, we noticed they cluster into a few recurring categories. The best skills fit cleanly into one; the more confusing ones straddle several."

## Type taxonomy

For each type: what it is, recommended folder structure, primary needs.

### 1. Library & API Reference

Skills that explain how to correctly use a library, CLI, or SDK.

> "These could be both for internal libraries or common libraries that Claude Code sometimes has trouble with."

**Examples:** `billing-lib` (internal billing library: edge cases, footguns), `internal-platform-cli` (every subcommand with usage examples), `frontend-design` (design system guidance)

**Folder structure:**
```
skill-name/
├── SKILL.md          # Quick start + gotchas
├── reference/        # API surface, method signatures
│   └── api.md
└── examples/         # Copy-pasteable code snippets
    └── snippets.md
```

**Primary needs:** Reference docs, gotchas, code examples.

---

### 2. Product Verification

Skills that describe how to test or verify that code is working.

> "Verification skills are extremely useful for ensuring Claude's output is correct. It can be worth having an engineer spend a week just making your verification skills excellent."

**Examples:** `signup-flow-driver`, `checkout-verifier`, `tmux-cli-driver`

**Folder structure:**
```
skill-name/
├── SKILL.md          # Verification workflow + checklists
├── scripts/          # Verification scripts, assertions
│   ├── verify.py
│   └── assert_state.py
└── reference/        # Expected states, test data
    └── expected-behavior.md
```

**Primary needs:** Scripts for verification, assertion libraries, state-checking patterns.

---

### 3. Data Fetching & Analysis

Skills that connect to data and monitoring stacks.

> "These skills might include libraries to fetch your data with credentials, specific dashboard ids, etc. as well as instructions on common workflows or ways to get data."

**Examples:** `funnel-query`, `cohort-compare`, `grafana`

**Folder structure:**
```
skill-name/
├── SKILL.md          # Common queries + gotchas
├── reference/        # Table schemas, dashboard IDs, query patterns
│   ├── schemas.md
│   └── dashboards.md
└── scripts/          # Data fetching helpers
    └── query_helpers.py
```

**Primary needs:** Schema references, query patterns, credential setup instructions.

---

### 4. Business Process & Team Automation

Skills that automate repetitive workflows into one command.

> "For these skills, saving previous results in log files can help the model stay consistent and reflect on previous executions of the workflow."

**Examples:** `standup-post`, `create-<ticket>-ticket`, `weekly-recap`

**Folder structure:**
```
skill-name/
├── SKILL.md          # Workflow steps + templates
├── templates/        # Output templates
│   └── post-template.md
└── scripts/          # Automation helpers
    └── fetch_activity.py
```

**Primary needs:** Workflow steps, output templates, state persistence.

---

### 5. Code Scaffolding & Templates

Skills that generate framework boilerplate.

> "They are especially useful when your scaffolding has natural language requirements that can't be purely covered by code."

**Examples:** `new-workflow`, `new-migration`, `create-app`

**Folder structure:**
```
skill-name/
├── SKILL.md          # Scaffolding workflow
├── templates/        # File templates (copy + fill)
│   ├── handler.py.tmpl
│   └── test.py.tmpl
└── scripts/          # Scaffolding scripts
    └── scaffold.py
```

**Primary needs:** Templates, naming conventions, file placement rules.

---

### 6. Code Quality & Review

Skills that enforce code quality and help review code.

> "These can include deterministic scripts or tools for maximum robustness. You may want to run these skills automatically as part of hooks or inside of a GitHub Action."

**Examples:** `adversarial-review`, `code-style`, `testing-practices`

**Folder structure:**
```
skill-name/
├── SKILL.md          # Review protocol + severity rubric
├── reference/        # Category definitions, examples
│   └── categories.md
└── scripts/          # Deterministic validators
    └── lint_check.py
```

**Primary needs:** Rubrics, scripts for deterministic checks, severity classification.

---

### 7. CI/CD & Deployment

Skills that help fetch, push, and deploy code.

> "These skills may reference other skills to collect data."

**Examples:** `babysit-pr`, `deploy-<service>`, `cherry-pick-prod`

**Folder structure:**
```
skill-name/
├── SKILL.md          # Deployment workflow + safety gates
├── workflows/        # Sub-workflows for different scenarios
│   └── rollback.md
└── scripts/          # Deployment scripts
    ├── smoke_test.py
    └── rollout.py
```

**Primary needs:** Safety gates, rollback procedures, step-by-step checklists.

---

### 8. Runbooks

Skills that take a symptom and walk through investigation.

> "Skills that take a symptom (such as a Slack thread, alert, or error signature), walk through a multi-tool investigation, and produce a structured report."

**Examples:** `<service>-debugging`, `oncall-runner`, `log-correlator`

**Folder structure:**
```
skill-name/
├── SKILL.md          # Symptom → investigation mapping
├── reference/        # Query patterns, known issues
│   ├── query-patterns.md
│   └── known-issues.md
└── templates/        # Report template
    └── finding-template.md
```

**Primary needs:** Symptom-to-query mapping, known issues catalog, report format.

---

### 9. Infrastructure Operations

Skills that perform routine maintenance and operational procedures.

> "Some of which involve destructive actions that benefit from guardrails. These make it easier for engineers to follow best practices in critical operations."

**Examples:** `<resource>-orphans`, `dependency-management`, `cost-investigation`

**Folder structure:**
```
skill-name/
├── SKILL.md          # Operation steps + safety confirmations
├── reference/        # Resource naming patterns, policies
│   └── resources.md
└── scripts/          # Cleanup/investigation scripts
    └── find_orphans.py
```

**Primary needs:** Safety guardrails, confirmation gates, resource identification patterns.

---

## Routing table

| User says... | Likely type |
|---|---|
| "Claude keeps using the wrong API" | 1. Library & API Reference |
| "I need to verify Claude's output" | 2. Product Verification |
| "Claude needs to query our data" | 3. Data Fetching & Analysis |
| "Automate this repetitive workflow" | 4. Business Process & Team Automation |
| "Generate boilerplate for new X" | 5. Code Scaffolding & Templates |
| "Enforce code quality / review PRs" | 6. Code Quality & Review |
| "Deploy / push / merge automation" | 7. CI/CD & Deployment |
| "Investigate / debug when X happens" | 8. Runbooks |
| "Manage infrastructure / cleanup" | 9. Infrastructure Operations |

When the skill straddles multiple types, pick the dominant one for folder structure and note the secondary influence.
