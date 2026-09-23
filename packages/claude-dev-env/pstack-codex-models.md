# pstack model configuration

feature, refactoring: gpt-6-sol
bug-fix: gpt-6-astra
perf-issue: gpt-6-sol
hillclimb: gpt-6-sol
judgment and prose: gpt-6-astra
strongest judgment: gpt-6-astra
how explorer: gpt-6-luna
how explainer: gpt-6-luna
why investigators: gpt-6-luna
why synthesizer: gpt-6-luna
reflect tooling: gpt-6-sol
reflect judgment, divergent, synthesizer: gpt-6-astra
arena runners: gpt-6-astra, gpt-6-sol, gpt-6-luna
arena cross-judge pool: gpt-6-astra, gpt-6-sol, gpt-6-luna
swarm workers: gpt-6-luna
architect runners: gpt-6-astra, gpt-6-sol, gpt-6-luna
interrogate reviewers: gpt-6-astra, gpt-6-sol, gpt-6-luna

## Reasoning effort

Single-model Luna roles use max. Astra roles use low. Sol roles use medium.
Panel entries use low, max, xhigh in the listed order.
Keep duplicate panel entries. Each entry specifies one candidate.
The cross-judge pool retains the effort paired with each entry.

Apply these substitutions once to incoming model requests:
- Sol medium through Luna max requests use gpt-6-luna with max effort.
- Sol high or higher requests use gpt-6-astra with low effort.
- Terra requests use gpt-6-luna with xhigh effort.
- Existing Luna requests use gpt-6-luna with high effort.

Explicit role and panel settings above take precedence over substitutions.
Do not apply substitutions again to their output.

session hook: on
