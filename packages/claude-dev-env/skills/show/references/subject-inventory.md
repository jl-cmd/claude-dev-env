# Subject inventory

List every element of the subject a reader expects to find, then mark each one kept or cut and say why in prose.

For a diff or a pull request the list is fixed and needs no judgment:

- Files touched
- Identifiers added and removed
- Behavior changed
- Tests added
- Docs changed
- Commits

Read those six from the repo itself:

```bash
git diff --stat <base>..<head>
git log --oneline <base>..<head>
```

Every element then sits in a visual or gets named in the surrounding prose. An inventory too large for one canvas becomes an overview visual plus detail visuals.
