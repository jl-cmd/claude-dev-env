# Accessibility

HTML widgets begin with `<h2 class="sr-only">` containing a one-sentence summary. Interactive controls have accessible names and visible focus. Decorative icons use `aria-hidden="true"`.

SVG roots use `role="img"` with `<title>` and `<desc>` as the first children. Text remains readable in light and dark modes. Color never carries meaning without a label, shape, position, or legend.
