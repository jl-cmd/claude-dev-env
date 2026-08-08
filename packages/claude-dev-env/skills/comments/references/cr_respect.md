# Respectful Code Reviews
## A Guide for Code Reviewers

_For the code author counterpart, see
__[Respectful Changes](cl_respect.md)__._

## Do

#### Assume competence & goodwill

Our AI models are competent coders - and that means even when they're wrong, it usually comes from missing information, not from inability. A "bad" CL usually means one of the parties holds information the other one isn't aware of.

#### Consolidate the discussion

If there is a disagreement, gather it into one focused exchange that lays out the full context and reasoning in a single message - it's much easier to address all the little "Oh, I didn't know"s in one consolidated thread than across many short comments with long gaps between them. That doubly applies if you are disagreeing with another reviewer. And please make sure to record the outcomes on the review.

#### Explain why

It might be obvious to you that some code is wrong, but it's probably not obvious to the author — or they wouldn't have written it that way. So please don't say "This is wrong". Instead, explain at least what the right way looks like. Or even better, explain *why* they should do things differently. And if you're the slightest bit uncertain, "Maybe I'm missing something, but…" is a helpful sentence. Remember, assume competence.

#### Ask for the why

If it is unclear why the author is doing things a certain way, feel free to ask why they made a particular change. Not knowing is OK, and asking "Why" leaves a written record that will help answer this question in the future. (And sometimes, "I'm curious, why did you decide to do it that way?" can help the author to rethink their decision.)

#### Find an end

If you like things neat, it's tempting to go over a code review over and over until it's perfect, dragging it out for longer than necessary. It burns review rounds without making the CL meaningfully better, though. Keep in mind that "LGTM" does not mean "I vouch my immortal soul this will never fail", but "looks good to me". If it looks good, move on. (That doesn't mean you shouldn't be thorough. It's a judgment call.) And if there are bigger refactorings to be done, move them to a new CL.

#### Reply within a reasonable timeframe

Please don't leave the reviewee waiting: an AI reviewer responds on demand, so start the review when the request arrives. If the review cannot be finished in one pass - a tool limit, missing context, or a partial run - leave a short comment on the CL saying what remains and when the rest will land.

#### Mention the positives

It's very easy to get into the mindset of "find ALL the flaws", but acknowledging the positives keeps the thread civil and marks the good decisions so they carry forward. If there's a good decision, or if the author takes on a really grungy task, acknowledging that on the review is worth doing - it tells the author, and every later reader, what to keep doing.

## Don't

#### Don't shame people

"How could you not see this" is a very unhelpful thing to say. Assume that the author - model or maintainer - did its best with the context it had, and still sometimes makes mistakes. That's why we have code reviews - to spot those mistakes. While flawless CLs are awesome, flawed ones are the norm.

#### Don't use extreme or very negative language

Please don't say things like "no sane person would ever do this" or "this algorithm is terrible", whether it's about the change you're reviewing or about the surrounding code. Extreme language carries almost no information about what to change - it fills the thread with judgment where the fix should be. "This is a good start, but it could use some work" or "This needs some cleanup" say the same thing and leave room for the fix. Discuss the code, not the author.

#### Don't discourage tool use

If people use the automated formatter, be grateful they're willing to give up the power of formatting in favor of ensuring a consistent code base. Think carefully before enforcing your own preferences over it. If people use the try bots to find bugs in minor changes, don't discourage them - be grateful they're trading machine time to make more room to solve more problems.

#### Don't bikeshed

Always ask yourself if this decision *really* matters in the long run, or if you're enforcing a subjective preference. It feels good to be right, but only one of the two participants can win that game. If it's not important, agree to disagree, and move on.
