# Scenario quality and anti-patterns (§7.6 and related)

Use this as a **checklist** when writing or reviewing scenarios and developer-facing specifications. Phrasing follows *BDD in Action* 2e and the catalog summarized in [claude-code-config#82](https://github.com/jl-cmd/claude-code-config/issues/82).

## Positive targets (what "good" looks like)

- **Declarative focus (§7.6.3):** Scenarios describe **business behavior** and user goals, not low-level UI click scripts.
- **Single-rule focus (§7.6.4):** One **business rule** per scenario; split when a scenario grows hard to read.
- **Meaningful actors (§7.6.5):** Personas can be **lightweight** (e.g. soap-opera introductions) when full UX research is unavailable — name + role, grow detail as scenarios demand.
- **Essential detail (§7.6.6):** Include data and columns that **change outcomes**; omit neutral or redundant columns.
- **State clarity (§7.6.6):** Make **initial** and **final** state explicit when data illustrates behavior.
- **Outcome description (§7.6.7):** Outcomes are **observable and measurable** — not hidden behind vague "verify" steps.
- **Independence (§7.6.8):** Each scenario sets up **its own** data and state so it can run alone.

## Anti-patterns to refuse or rewrite

- **Imperative scenarios** that read like automation scripts (especially pure UI step lists).
- **Multi-concern** scenarios that mix unrelated rules.
- **Incidental detail** that does not serve the rule under test.
- **Test scripts in disguise** — heavy use of **verify** / **check** without stating the business outcome.
- **Dependent scenarios** that only pass in order.
- **Gherkin without conversation** (BAs or testers writing scenarios in isolation) — structured specs are an **output** of discovery, not a substitute for it (Minimal BDD).

## Executable specs at the code level

Prefer **"should …"** phrasing in names (Dan North, 2006). Nest by **behavior context** (e.g. when / given groupings) rather than mirroring production file layout when that obscures intent (§16.5.5 attitude: tests as documentation).
