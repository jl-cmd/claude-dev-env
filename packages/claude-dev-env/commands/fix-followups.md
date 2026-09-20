---
description: Fix every non-breaking finding the follow-up ledger holds and open a draft PR for it
argument-hint: [repository root, or blank for the current repository]
---

Fix the non-breaking findings a local gate recorded rather than blocked on,
and deliver them as one draft pull request.

The repository root is `$ARGUMENTS`, or the current repository when that is
blank.

Use `rules/asd-ste100-language.md` for user-facing wording.

## 1. Read the ledger

Run `cde followup brief --repository-root <root>`.

When it prints `no follow-ups recorded`, report that and stop. There is no
work.

Otherwise the brief lists one line per finding, each carrying the rule
identifier, the file, and the message.

## 2. Group the findings

Group the lines by rule identifier. A rule with several findings takes one
pass over every file it names, so the same fix shape lands once.

Read each named file before editing it. A recorded finding names the state of
the file at the moment the gate ran, so confirm the finding still holds.
Keep a finding the current file still carries. Drop the rest.

## 3. Fix each group

Each finding is non-breaking, so the change that raised it already shipped.
Keep every fix mechanical. Touch no behavior, change no signature, and add no
abstraction.

Run the repository's own fast checks over the files you changed. Where a
finding names a generated file, regenerate it with the repository's tooling.

## 4. Open the pull request

Branch from the repository's default branch. Commit each rule group on its
own, with a message naming the rule identifier and the files.

Open the pull request as a draft. Write the body as:

- One `Before:` paragraph saying which findings stood open.
- One `After:` paragraph saying what the tree now holds.
- A short `How` paragraph naming the rule groups and the files each touched.

Push, then confirm the required checks report on the branch head.

## 5. Empty the ledger

Once the pull request is open, run
`cde followup clear --repository-root <root>`.

A finding the pull request left alone goes back in the ledger with
`cde followup ingest`, so the next pass picks it up.

## Report

Name the pull request link, the rule groups fixed, the findings dropped as no
longer present, and anything left in the ledger.
