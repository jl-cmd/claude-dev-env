# Plain Language

**When this applies:** All prose you write — chat responses, `AskUserQuestion` questions and options, documentation and Markdown, PR and issue bodies, and commit messages. Anything a person reads.

**Hook enforcement:** `plain_language_blocker` (PreToolUse on `AskUserQuestion` and on Write|Edit|MultiEdit of `.md` targets) blocks a heavy word and names the everyday word to swap in. Code fences, inline code, blockquotes, URLs, and file paths are skipped so exact identifiers stay untouched. See `hooks.json` for registration.

## Rule

Write so the reader understands it on the first pass, without hunting for extra context and without wading through more than the point requires. Favor everyday words, short sentences, and concrete phrasing. This is **plain language** (ISO 24495-1:2023; U.S. Plain Writing Act of 2010) — clear writing, not dumbed-down writing.

Plain language does not mean dropping technical terms. It means:

- **Common word first.** Reach for the plain word when one carries the meaning (`use` over `utilize`, `start` over `initiate`, `enough` over `sufficient`). Keep a technical term when it is the precise name for the thing.
- **Define jargon and acronyms on first use** — unless the reader has already used them or they are core to the domain you share.
- **Short sentences, active voice.** One idea per sentence. Name the actor (`the hook blocks the write`, not `the write is blocked by the hook`).
- **Lead with the answer.** State the conclusion or recommendation first; supporting detail follows.

## Give only what's needed (progressive disclosure)

Match the amount of information to what the reader needs to act, and hold the rest in reserve until they ask. Surplus detail raises the reader's **cognitive load** without improving the decision.

- Answer the question that was asked; do not also explain three adjacent things.
- Put the essential point in the first sentence or two; offer or link depth rather than front-loading it.
- In an `AskUserQuestion`, state each option's outcome and main tradeoff in a sentence; skip code dumps and long file lists.
- Cut preamble and recap. Do not restate the task back before answering it.

## Readability check

Before sending, reread as the recipient: does every sentence land on first read, with no term they must look up and no detail they did not need? If a sentence only makes sense to someone who already knows the backstory, rewrite or cut it. Aim for wording a non-specialist in that area can follow (roughly an 8th–10th grade reading level for general prose; technical reference may sit higher where the terms are unavoidable).

## Not in scope

- **Necessary technical precision.** Exact identifiers, file paths, API names, and domain terms stay exact — plain language sharpens the words around them, it does not blur the terms themselves.
- **Code.** Naming and structure follow the code standards; this rule governs prose.

## Why

The reader is short on time and attention, and the first pass is often the only pass. Plain wording and right-sized detail carry the point across in that one pass, while dense or padded text forces the reader to do work the writer should have done. Clear writing also exposes unclear thinking: if an idea is hard to say plainly, it may not be settled yet.

## Relationship to other rules

- **confirm-implementation-forks** ("How to ask") applies this rule to fork questions: plain wording, only the detail needed to choose.
- **self-contained-docs** and **no-historical-clutter** keep a document understandable without outside context; plain language keeps the sentences themselves easy to read.
- **ask-user-question-required** routes questions through `AskUserQuestion`; this rule governs how those questions are worded.
