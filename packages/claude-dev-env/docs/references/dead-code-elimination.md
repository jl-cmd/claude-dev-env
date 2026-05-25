# Dead Code Elimination — Reference

External sources and standard terminology behind [CODE_RULES §9.8](../CODE_RULES.md#98-remove-code-you-orphan-dead-code-elimination). Each entry names the concept, gives a one-line definition, and links a direct source.

## The mechanic — removing code that cannot affect results

- **Dead-code elimination (DCE)** — a compiler optimization that removes code which does not affect program results, reducing program size, resource use, and execution time. Foundational treatment: Aho, Lam, Sethi & Ullman, *Compilers: Principles, Techniques, and Tools* (the "Dragon Book"). <https://en.wikipedia.org/wiki/Dead-code_elimination>
- **Tree shaking** — dead-code elimination driven by `import`/`export` structure: keep only the exports reachable from an entry point and drop the rest. MDN glossary: <https://developer.mozilla.org/en-US/docs/Glossary/Tree_shaking>. Webpack guide: <https://webpack.js.org/guides/tree-shaking/>
- **Remove Dead Code** — the named refactoring for eliminating unreachable or unused segments to improve clarity and maintainability. Martin Fowler, *Refactoring* (2nd ed., 2018): <https://refactoring.com/catalog/removeDeadCode.html>

## The liveness test — reachability, not mere reference

- **Unreachable code / reachability analysis** — code with no control-flow path from the rest of the program; detecting it is a form of control-flow analysis. This is the basis for §9.8 testing reachability from a live entry point rather than the bare presence of a reference. <https://en.wikipedia.org/wiki/Unreachable_code>

## The safety overlay — why uncertain deletions escalate

- **Lava Flow anti-pattern** — suboptimal code that survives in production because accumulated dependencies and backward-compatibility fears make removal feel risky. Brown, Malveau, McCormick & Mowbray, *AntiPatterns* (1998). The §9.8 "ask when uncertain, never guess-delete" clause guards against blind risky removals. <https://en.wikipedia.org/wiki/Lava_flow_(programming)>
