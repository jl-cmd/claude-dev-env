# BDD Scenario Quality Guide

This guide defines the seven patterns that make scenarios clear, focused, and testable, enabling teams to align on business behavior, merge ideas from shared examples, and verify outcomes with automation and review.

Source: Smart & Molak, *BDD in Action* 2e, Chapter 7.6 — scenario quality patterns.

## Declarative Focus

Scenarios work best when they name what users want to achieve in the language of the business. Lead with goals and recognizable domain tasks so readers grasp intent at a glance. Reserve step-level or UI detail for places where it truly clarifies behavior.

> "Good scenarios model business behavior, not system interactions." — Smart & Molak §7.6.3

Good scenarios name user goals and tasks in domain language before any implementation detail.

## Single-Rule Focus

Each scenario tests one business rule. When a rule is complex or a scenario grows hard to read, split it into smaller scenarios that each test one aspect of the rule. That keeps failures pointing to a single behavior.

> "Good scenarios focus on testing a single business rule. If a business rule is complex, or if a scenario gets too big and hard to read, a good trick is to break the scenario into smaller, more focused ones that test a specific aspect of the rule." — Smart & Molak §7.6.4

Good scenarios isolate one rule so failures point to a single behavior.

### Example: hotel search (illustrates single-rule focus and declarative data)

This scenario shows one rule: search returns hotels within a distance threshold.

```
Scenario: Search for available hotels by distance
Given the following hotels:
| Hotel Name | Location | Distance from center |
| Ritz       | Paris    | 3.2                  |
| Savoy      | Paris    | 6.9                  |
| Hilton     | Paris    | 12.5                 |
When I search for a hotel within 10 km of Paris
Then I should be presented with the following hotels:
| Hotel Name | Location | Distance from center |
| Ritz       | Paris    | 3.2                  |
| Savoy      | Paris    | 6.9                  |
```

## Meaningful Actors

Personas ground scenarios in realistic goals and context. Use light soap-opera personas when you need depth before full UX research: introduce names and roles as needed and deepen them across scenarios.

> Smart & Molak §7.6.5 describe personas as rich, realistic descriptions: each persona captures goals, abilities, and background information that ground the test scenario in a real user context.

Good scenarios name who acts and what they need in plain language.

## Essential Detail

Include columns and fields that affect the outcome; verify each column contributes, and simplify tables where values repeat or stay neutral to the result. Every visible value should earn its place in the example.

> Smart & Molak §7.6.6 — essential detail is information directly relevant to the business rule.

Good scenarios tie every field to a value that changes the outcome.

## State Clarity

When examples use data to illustrate behavior, spell out the starting situation and the expected end state in the same breath. Set up or reference test data so the system begins in the expected initial state before the action. Readers should always see both the before and after picture when data carries the story.

> "Well-written scenarios describe both behavior and data. When a scenario uses data to illustrate behavior, it should describe the initial state and the final state and manage or set up the test data to ensure that the system is in the expected initial state." — Smart & Molak §7.6.6

Good scenarios state initial and final state when data illustrates behavior.

## Outcome Description

Well-written scenarios state target outcomes in clear, measurable terms any reader can verify—business results observers can confirm directly in the Then steps.

> Smart & Molak §7.6.7 — scenarios state outcomes observers can confirm.

Good scenarios describe observable outcomes in domain terms.

## Independence

Each scenario sets up its own data and system state so it can run alone; give every scenario a self-contained setup so the suite passes in any run order. Every scenario carries its own setup and makes preconditions explicit.

> Smart & Molak §7.6.8 — independent scenarios work in isolation.

Good scenarios carry their own setup and expose every precondition needed to run in any order.

## Quick Reference

- ✓ Scenarios describe user goals and business tasks in domain terms
- ✓ Each scenario tests one business rule
- ✓ Actors have recognizable goals and context
- ✓ Tables and fields carry the information that affects the outcome
- ✓ Initial and final state are clear when data matters
- ✓ Outcomes are unambiguous and measurable
- ✓ Scenarios run independently with their own data
