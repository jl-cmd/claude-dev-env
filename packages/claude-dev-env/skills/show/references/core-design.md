# Core design

Use flat surfaces, transparent outer containers, sentence case, the 16-at-680 scaled text floor set in `references/svg-contract.md`, and weights 400 or 500. Keep visible prose outside the visual. Use no decorative gradients, glow, blur, noise, or drop shadows. Use no emoji. Keep a visual compact and split it when labels or relationships become hard to read.

## Color

Color is the default, in the style of `samples/`: pick a palette of three to four named hues (for example a red, a green, an amber) plus neutral grays and near-black text, and use it throughout the visual.

- Paint category and state surfaces with light tinted fills of the palette hues (for example `#DFF0E4` under a `#1E8449` stroke), with white or warm-white cards for plain content.
- Draw strokes and text in strong fixed colors: near-black `#1A1A1A` for primary text, mid-gray for secondary, a palette hue for anything whose color carries meaning.
- Use each hue for one meaning and keep that meaning consistent across the visual; a short legend explains any pairing the reader cannot work out alone.
- Every SVG draws its own opaque warm-white background rect (see `references/svg-contract.md`), so the fixed palette stays legible on light and dark hosts alike.
- Keep contrast strong: text and strokes hold up against the fill behind them.
- Reserve a monochrome outline style for the rare case the user asks for it.
