from __future__ import annotations

import subprocess
from pathlib import Path

from git_hooks_constants import (
    GH_EXECUTABLE_NAME,
    GH_PR_VIEW_ARGUMENTS,
    GH_PR_VIEW_TIMEOUT_SECONDS,
)


def get_pull_request_url(repo_dir: Path) -> str | None:
    try:
        result = subprocess.run(
            [GH_EXECUTABLE_NAME, *GH_PR_VIEW_ARGUMENTS],
            cwd=repo_dir,
            check=False,
            capture_output=True,
            text=True,
            timeout=GH_PR_VIEW_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def build_pull_request_reminder(url: str) -> str:
    prompt = "Review this pull request: <PR link>\n\nRead the PR and its full diff. Do not use the branch name, commit message, labels, current title, or a shallow summary.\n\nBefore writing, inventory every independently observable behavior in the full diff. A behavior is independent when a user, caller, operator, automation, output, error, exit status, fallback, or side effect can observe it separately. Lead with the central behavior for readability, then give every other behavior its own short paragraph or bullet.\n\nFor each behavior, state the trigger or observer, the Before -> After result, the affected surface/caller when shared, and focused proof. Include important preserved behavior and fallback paths when they help a coder rule a regression in or out. Describe outcomes, not line-by-line implementation, and do not hide multiple behaviors under vague umbrella wording.\n\nWrite like the reader is smart but knows nothing about this code. Pretend they asked you to explain it like they are five and feel stupid. If a word needs another sentence to explain it, replace the word — or turn it into a tiny story.\n\nYour job is not a dry API blurb. Your job is an illustrative before/after a person can picture.\n\nGold voice for titles and “What this adds”:\n\nThe theme package has a phone icon somewhere. We need to find it.\n\nBefore: yell “anyone know how to find icons?” and wait for a hand.\n\nAfter: call the finder by its name tag: “icon finder, go.”\n\nThat’s all “operation id” is — the finder’s name tag.\n\nRules for that voice:\n\nStart from a concrete scene (what’s in someone’s hand, what they’re hunting for).\nPrefer Before / After when the change is “how you ask” or “how you look it up.”\nUse picture words: hand it, open, find, check, save, skip, stop, call by name, name tag.\nPrefer spoken results: “found it,” “missing,” “duplicated,” “couldn’t.”\nWhen the diff uses an abstract word (operation id, registry, envelope, adapter, digest, schema), do one of two things:\nDrop it and say what the person does with their hands, or\nKeep it once, then gloss it in the same breath with a name-tag / mailbox / checklist metaphor — like the “finder’s name tag” line above.\nNever leave jargon unexplained. Never write as if the reader already knows the jargon.\nAdd a tiny concrete example in parentheses when a name is abstract (like “the phone icon”).\nFew words. Small words. Clear on first read.\nReturn:\n\nRecommended title\n\nFew words. Small words. Clear on first read.\nSay what you hand it, what it does, and what you get back — or the Before/After of how you ask.\nPrefer picture words and spoken results.\nGood title: “Call the icon finder by its name tag instead of asking around”\nGood title: “Given a theme STP and an asset name, report whether that asset was found, missing, or duplicated”\nBad title: anything that only says operation id / registry / typed envelope / adapter / digest / schema with no picture.\nUse “Add” only if it helps. Do not force it.\nNo vague words like “improve,” “enhance,” or “update.”\nReturn one title only.\nWhy this title fits\n\n1–2 short sentences in the same voice.\nIf needed, one Before / After beat, then what you get back.\nIf this section is needed to decode the title, rewrite the title.\nEvidence\n\nKey files or functions that support the title.\nIf you cannot read the PR or full diff, say so and do not propose a title.\n\nThen write a short, paste-ready PR description.\n\nUse this structure:\n\nWhat this adds\n1–2 short paragraphs in that illustrative voice. Lead with a scene when you can (“The theme package has a phone icon somewhere…”). If the change is a new way to ask, use Before / After. Say what you give it, what it does with its hands, and what you get back. If an abstract machine-word must appear, gloss it immediately (“That’s all X is — …”). Describe the job people can see. Do not describe inner machinery. Mention a check only if it is central to the feature.\n\nWhy\nOne short paragraph. Same plain level. Say who needs this and what goes wrong without it (the “yell and wait for a hand” problem). If this is needed to decode the feature, rewrite “What this adds.”\n\nVerification\nList only proof from the PR, CI, or your own checks.\n\nReported in the PR\n\n…\nChecked by you / CI here\n\n…\nRules:\n\nFew words. Small words. Clear on first read. ELI5 I-am-stupid mark.\nDo not invent behavior, tests, or benefits.\nStrip branch names, hashes, draft notes, agent notes, and merge notes.\nNo vague words like “improve,” “enhance,” or “update.”\nIllustrative first. Abstract labels only if glossed in the same breath.\nUse the recommended title and paste-ready description to run `gh pr edit <PR link> --title ... --body-file ...`, then run `gh pr view <PR link> --json title,body` to confirm the saved title and body. Report the saved result."
    return prompt.replace("<PR link>", url)
