# Tabbed decision artifact

A one-page HTML artifact for handing someone a set of open decisions. One tab per decision, each tab explaining its subject in full, with a choice card and a note box. A button at the bottom gathers every answer into one block of text to paste back into a conversation.

The template lives beside this file: `tabbed-decision-artifact-template.html`. It runs as-is, and it is its own worked example: each tab states one rule for writing a tab and follows that rule, and the Reference group carries four full worked tabs. Read it once, then replace the tabs with your own decisions.

## When it fits

Use it when all of these hold:

- Several separate things need a person's answer, and the answers are independent of each other.
- Each thing needs a paragraph or two of background before the question makes sense.
- The reader should be able to answer without opening anything else — no pull request, no ticket, no dashboard.
- You want the answers back as text you can act on.

Use something shorter when there is one question, or when the questions share one answer.

## The rule that outranks the rest

**Every claim in a tab carries a source you checked.** A command you ran and its output, a file you opened named by path, a page you read named by title. A number is checked when you can say the command that produced it.

Three things never go in a tab:

- **A branching guess.** "If the cache is stale, do X; if not, do Y" hands the reader your homework. Check which one holds, then write that one.
- **An unconfirmed problem.** A fix for a problem that cannot happen wastes the decision. Reproduce it, or drop the tab.
- **A softened claim.** "This may cause issues" reads as a finding and carries none. Say what happens, or say you do not know.

When you cannot check something, say so in the tab: name what you could not reach, and what it would take to reach it. Before the docket ships, have a second pass go through every claim against its source — a writer cannot audit their own confidence. Anything that pass cannot confirm comes out, or ships flagged as unconfirmed.

## The rule the format exists for

**Every tab carries its own full context.** A reference number and a link give a reader nothing. Say what the thing is, what it does, what happens if it lands, and what it costs. A reader who has never seen the underlying system should be able to answer every tab in the docket.

That rule shapes the writing:

- Name things the way the reader names them. A person runs *the test suite*, not *the pytest collection root*.
- Give the number and where it came from. "437 test files" beats "a large number".
- Link any source that has an address. An issue or pull request carries its link, not its number alone; a file carries its path; a command carries its exact text.
- State the honest gap. When something rests on a theory nobody tested, say so in the tab.
- Say what a choice costs alongside what it gives. Cost is what the reader gives up: time, rework, work left undone, or a risk carried.
- Keep sentences to 20 words and one idea. Move detail into a table, where a reader can find one row without reading the rest.
- Cut any sentence that restates the one before it, or that argues a choice is good. The facts already made that case.
- State what happens, then stop. Cut the clause that says what else it does — "does more than X, it also Y", "not simply X, but Y", "not only X, it is Y". The build-up costs the reader the point.

  | Padded | Direct |
  |---|---|
  | Accepting it does more than add the new work. It also restores the old version of everything else. | Accepting it restores the old version of everything that copy contains. |
  | This is not simply a formatting change; it also alters the output. | This alters the output. |
- Reach for a table, chart, image, or diagram whenever the reader would otherwise hold several numbers in their head.
- Draw the thing to scale when a decision turns on position, size, or layout. Two drawings side by side with the gap labelled between them carry a spatial disagreement that a pair of numbers leaves each reader to picture differently. Plain markup and styling draw this.
- Put the measurements in a table beside any drawing, and name the command or measurement that produced them.
- State a claim by naming what the thing is, and state guidance as the action to take. Reserve naming what to avoid for behaviour you can pin down only by its failure — the source rule is `doc-prose-cuts`.

The template's own tabs state these rules and follow them, so the fastest way to learn the format is to open it and read.

## How the file is put together

The file reads in this order — a token layer, then three numbered sections:

| Section | What it holds | Edit it? |
|---|---|---|
| Palette and type tokens | Every colour, typeface, spacing step, and shadow, as CSS custom properties across three theme blocks | Only to change the look |
| `CONFIG` | Headline, standfirst, the figures row, the footnote, the browser storage key | Yes, first |
| `ITEMS` | One entry per tab | Yes, this is the work |
| Engine | Rendering, keyboard handling, storage, the copy button | No |

### CONFIG

| Field | What it does |
|---|---|
| `topline` | Small mono line above the headline. Date it, or name the source. |
| `title` | The headline. Say what the reader is being asked for. |
| `intro` | One or two short sentences saying what the docket is. |
| `steps` | A sequence the docket's work runs in, one entry per step. Renders as a stepper under the intro. An empty list hides it. Use it for a real order — a staged rollout, a migration, a dependency chain. Generic page instructions belong nowhere: the reader can see the tabs, the cards, and the copy button already. |
| `figures` | List of `{value, label}` tiles, each taking an optional `unit` and `tone`. `unit` rides inside the number at a smaller size, so `{value: "3", unit: " of 8"}` reads as one value. `tone` (`good` / `warn` / `risk`) colours the number itself. An empty list hides the row. Keep any "decisions on this page" figure in step with the dock, which counts only the items carrying a choice. |
| `footnote` | Small print. Where the numbers came from, and where the answers live. |
| `copyHeading` | Heading on the text the copy button produces. |
| `storageKey` | Browser storage key. Give each docket its own so two open dockets never overwrite each other. |

### An item

| Field | What it does |
|---|---|
| `id` | Short unique slug. Drives storage and the tab anchor. |
| `group` | Rail heading. Consecutive items sharing a group sit under one heading. |
| `tab` | Rail label. Short enough to read at a glance. |
| `urgent` | `true` paints the rail dot red. On an item with choices the dot turns green once answered. On a reading-only item it stays red, marking a tab that always wants attention. |
| `readingOnly` | `true` makes it a reading-only tab: choices and the note box stay off, and the count skips it. An item carrying no `options` reads the same way. |
| `label` | Mono line above the panel heading. Scope, owner, or state. |
| `title` | Panel heading. A full sentence beats a label. |
| `summary` | One paragraph. The whole situation in plain words. |
| `blocks` | List of body blocks. |
| `chips` | Optional list of `{text, tone}` pills under the summary, stating where the tab stands. Tone: `""`, `"good"`, `"warn"`, `"risk"`. |
| `options` | List of choices. Reading-only items leave it off. |

Suggested groups, in reading order:

1. **Read this first** — context the rest depends on.
2. **Only you can answer** — genuine judgement calls.
3. **Ready when you say go** — decided in principle, waiting on a yes.
4. **Reference** — background, no decision.

### Body blocks

Three kinds, mixed freely in any order:

```js
{heading: "Heading", paragraphs: ["Paragraph.", "Another paragraph."]}
{heading: "Heading", bullets: ["Point.", "Another point."]}
{heading: "Heading", table: {caption: "Optional line above it.", head: ["Column"], rows: [["a"]]}}
{heading: "Heading", command: "python -m pytest tests/"}
{callout: "", claim: "One serif line.", paragraphs: ["The detail beneath it."]}
```

Callout tones: `""` for a neutral recommendation, `"good"` for reassurance, `"warn"` for a warning, `"risk"` for a real hazard. An optional `claim` opens the callout in the serif face at a larger size, with the paragraphs beneath it.

A `command` block quotes text exactly, in a bordered frame that scrolls rather than wraps — a wrapped command line is one the reader mistypes. It is what the evidence rule asks for when a claim rests on something you ran.

A table column reads as numeric when it carries at least one digit and every filled cell reads as a number. Such a column gets right-aligned and set in tabular figures, so a reader can compare down the column. Commas, decimal points, spaces, percent signs, currency marks, and a leading sign all count as part of a number. An empty cell counts as neutral, so one gap keeps a column of counts aligned. A column of dashes sits left, with the prose. That happens on its own — there is nothing to mark up.

### Options

```js
{recommended: true, decision: "The sentence written into the copied output", title: "Card title", detail: "Where the path goes, and what it costs."}
```

| Field | What it holds |
|---|---|
| `decision` | The sentence copied into the output. First person, an instruction you can act on. |
| `title` | Card title. Two or three words. |
| `detail` | Where the path goes, and what it costs. |
| `recommended` | `true` puts a Recommended flag on the card. Use it on at most one. |

Write `decision` in the reader's voice: "Bring everything up to date first". It lands in the copied text word for word.

Mark one card `recommended: true` when you have a view, put it first, and back it with a callout that says why. Leave every card unmarked when you have no view.

Offer as many paths as the decision really has. Do not invent one to look balanced, and do not drop a real one to look tidy.

## Text is placed as HTML

Every string is written into the page as HTML. That is deliberate: it lets you write `<strong>`, `<em>`, `<code>`, and entities such as `&mdash;` and `&ldquo;` inside the copy. The content is authored by whoever fills the template in — a reader never types into it — so nothing is escaped.

The copy button strips the tags and entities back out, so the text a reader pastes into a conversation is plain.

## What the reader gets

- **Keyboard**: arrow keys move along the rail, Home and End jump to the ends, every focus state is visible.
- **Screen readers**: the rail is announced as a vertical tab list, the decided count reads out as it changes, and the meter reports its value against its total.
- **Motion**: a reader who asks for reduced motion gets each jump without the travel. That covers the scripted scrolls as well as the transitions.
- **Cross-tab links**: a link carrying `data-tab="<item id>"` jumps to that tab, so a rule can point at its worked example.
- **Storage**: choices and notes are held in the browser under `CONFIG.storageKey`. Closing the tab and coming back keeps them. Nothing is sent anywhere.
- **Counter**: the dock reads "N of M decided", counting only the tabs that carry a choice, above a bar that fills as answers land and turns green on the last one. The dock rides the bottom of the viewport through a long tab, and settles into the page at the end.
- **Rail marks**: two channels, so colour is never the only carrier. Shape says what you owe — a ring waits for an answer, a filled disc holds one, a bar asks for nothing. Colour says which kind of attention it wants, on a four-step ramp: red today, amber this session, blue worth reading, green settled.

  | Mark | Meaning |
  |---|---|
  | Ring, red | Wants your answer today |
  | Ring, amber | Waiting for your answer |
  | Disc, green | Answered |
  | Bar, blue | Read this first |
  | Bar, calm | Background, nothing to answer |

  Every mark takes a hue from the palette. The calm tone is the accent hue drained of saturation, so a low-priority mark still belongs to the design; a neutral grey mark reads as unstyled rather than low-priority.

  A legend under the rail lists the marks a docket actually uses, rendered from the same list the marks are drawn from.
- **Themes**: light and dark, both from the token layer, following the viewer's system setting and their own toggle.
- **Narrow screens**: the page sizes itself to the device width. Below 860 pixels the rail turns into a horizontal strip along the top. The dock holds its place at the bottom, taking about 150 pixels of a phone screen, so the panel begins below the fold.

## Filling it in

1. Copy `tabbed-decision-artifact-template.html` to a working file.
2. Rewrite `CONFIG`, including a fresh `storageKey`.
3. Replace all five example items with your own. Keep one item per decision.
4. Read each tab as somebody who has never seen the system. Anywhere you reach for outside knowledge, write that knowledge into the tab.
5. Publish it with the Artifact tool, passing the file path.

## A second shape: six views of one item set

A worked example sits beside this file: `tabbed-decision-artifact-multiview-example.html`. It captures decisions the same way and displays them differently. Six tabs hold six views of one item set.

Every view renders the same item objects. A decision recorded in the swimlane shows in the table, the timeline, and the tree. Clicking an item in any view opens a drawer with the full case, the choice cards, and the note box.

Use this shape when the items are stages of one piece of work. The reader's first question is then how the items relate. One tab per decision suits independent questions. Six views suit a chain.

Each view answers a different question about the same items:

| View | What it is good at |
|---|---|
| Swimlane | Who acts at each stage. Shows how few stages need a person. |
| Dependencies | What must exist before the next thing can start. |
| State machine | The life of one record through the system, including a branch held out of the comparison. |
| Order | Build order and relative weight, as bars rather than dates. |
| Table | Every item at once, for scanning. |
| Evidence cards | One card per check you ran. A flagged card marks a check that changed the plan. |

The state machine view carries the lesson worth copying. The example counts alerts engineers acted on against alerts they ignored. It holds untriaged alerts out of that comparison. An alert nobody looked at is not an alert somebody rejected. Name the pile you hold out, and say why, wherever a view shows a split.

Write every string in the example to the [`eli11-replies`](../../packages/claude-dev-env/rules/eli11-replies.md) shape: one idea per sentence, the action first, few words. A drawer holds four or five short lines, not two long paragraphs. A reader deciding five things reads every panel, so length costs them five times over.

Give the example's `STORE` constant a fresh value when you copy the file. Two artifacts sharing a storage key overwrite each other's answers.

Fill it in by rewriting `ITEMS`, then the six panels' static text. The swimlane cells and tree tiers carry a `data-slot` attribute naming an item `id`; the engine renders each named item into its slot.

## Changing the look

The palette is a token layer: three blocks near the top of the file define the same set of custom properties for the default theme, for `prefers-color-scheme: dark`, and for the viewer's explicit `data-theme` toggle. Components style themselves through those tokens only.

To reskin, rewrite the tokens in all three blocks and leave everything below them alone. Keep `--good`, `--warn`, and `--risk` distinct from `--accent`; they carry meaning, and a reader reads the callout tone before reading the words.

`--lift` and `--lift-high` carry the depth between the rail, the panel, and the dock. Give each a value that suits its own theme's ground: a shadow tuned for a pale ground reads as a smudge on a dark one.
