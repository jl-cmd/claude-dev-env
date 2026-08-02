# SVG contract

Put `<title>`, `<desc>`, then `<defs>` first. Every connector has `fill="none"`; arrowheads use the standard marker. Avoid negative coordinates, clipping, crossing labels, and standalone labels outside a region or callout.

## Canvas tiers

Pick one of two widths:

- **Standard** — `viewBox="0 0 680 H"`. Use it for a single small explainer.
- **Large infographic** — `viewBox="0 0 W H"` with `W` from 1360 to 2000. This is the default for anything with two or more panels or more than about 6 labeled elements.

## Text floor

The smallest caption sits at `16 × (width / 680)` units, rounded to the nearest whole unit: 16 at 680, 32 at 1360, 41 at 1760. Body text sits above that floor.

## Safe area

The safe area scales with the canvas the same way: `40 × (width / 680)` units, so 40 at 680 and about 80 at 1360. Keep authored content inside it.

## Background

Standard-tier visuals stay transparent. A large-tier illustrative scene that uses fixed scene colors may draw its own background rect.
