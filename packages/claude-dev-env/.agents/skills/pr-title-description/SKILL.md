---
name: pr-title-description
description: Review one or more pull requests and write plain titles and descriptions from the full diff.
disable-model-invocation: true
---

Accept one or more pull request links as arguments. Apply the prompt below to each link.

With no argument, use the current task, browser, worktree, or GitHub context to find the pull request or pull requests. If the context does not show a clear pull request, ask for a pull request link.

here is the FINAL version of the hook prompt for title + descriptions: 
\\\<PR link>

Read the PR and its full diff. Do not use the branch name, commit message, labels, current title, or a shallow summary.

Find the main thing this adds for a user, caller, or operator.

Write like the reader is smart but knows nothing about this code. Pretend they asked you to explain it like they are five and feel stupid. If a word needs another sentence to explain it, replace the word — or turn it into a tiny story.

Your job is not a dry API blurb. Your job is an illustrative before/after a person can picture.

Gold voice for titles and “What this adds”:

The theme package has a phone icon somewhere. We need to find it.

Before: yell “anyone know how to find icons?” and wait for a hand.

After: call the finder by its name tag: “icon finder, go.”

That’s all “operation id” is — the finder’s name tag.

Rules for that voice:

Start from a concrete scene (what’s in someone’s hand, what they’re hunting for).
Prefer Before / After when the change is “how you ask” or “how you look it up.”
Use picture words: hand it, open, find, check, save, skip, stop, call by name, name tag.
Prefer spoken results: “found it,” “missing,” “duplicated,” “couldn’t.”
When the diff uses an abstract word (operation id, registry, envelope, adapter, digest, schema), do one of two things:
Drop it and say what the person does with their hands, or
Keep it once, then gloss it in the same breath with a name-tag / mailbox / checklist metaphor — like the “finder’s name tag” line above.
Never leave jargon unexplained. Never write as if the reader already knows the jargon.
Add a tiny concrete example in parentheses when a name is abstract (like “the phone icon”).
Few words. Small words. Clear on first read.
Return:

Recommended title

Few words. Small words. Clear on first read.
Say what you hand it, what it does, and what you get back — or the Before/After of how you ask.
Prefer picture words and spoken results.
Good title: “Call the icon finder by its name tag instead of asking around”
Good title: “Given a theme STP and an asset name, report whether that asset was found, missing, or duplicated”
Bad title: anything that only says operation id / registry / typed envelope / adapter / digest / schema with no picture.
Use “Add” only if it helps. Do not force it.
No vague words like “improve,” “enhance,” or “update.”
Return one title only.
Why this title fits

1–2 short sentences in the same voice.
If needed, one Before / After beat, then what you get back.
If this section is needed to decode the title, rewrite the title.
Evidence

Key files or functions that support the title.
If you cannot read the PR or full diff, say so and do not propose a title.

Then write a short, paste-ready PR description.

Use this structure:

What this adds
1–2 short paragraphs in that illustrative voice. Lead with a scene when you can (“The theme package has a phone icon somewhere…”). If the change is a new way to ask, use Before / After. Say what you give it, what it does with its hands, and what you get back. If an abstract machine-word must appear, gloss it immediately (“That’s all X is — …”). Describe the job people can see. Do not describe inner machinery. Mention a check only if it is central to the feature. If there are many changes, keep the main one. Mention others only if they explain the main one.

Why
One short paragraph. Same plain level. Say who needs this and what goes wrong without it (the “yell and wait for a hand” problem). If this is needed to decode the feature, rewrite “What this adds.”

Verification
List only proof from the PR, CI, or your own checks.

Reported in the PR

…
Checked by you / CI here

…
Rules:

Few words. Small words. Clear on first read. ELI5 I-am-stupid mark.
Do not invent behavior, tests, or benefits.
Strip branch names, hashes, draft notes, agent notes, and merge notes.
No vague words like “improve,” “enhance,” or “update.”
Illustrative first. Abstract labels only if glossed in the same breath.
Do not edit GitHub. Return the rewritten description only. I don't know if I'm just not seeing it or what, but I'm not. I don't see the full text. So here's the text as a reminder. This is supposed to be with agencies when they commit and push. When they push a commit to APR or they make a PR, this is what they should see every single time.
