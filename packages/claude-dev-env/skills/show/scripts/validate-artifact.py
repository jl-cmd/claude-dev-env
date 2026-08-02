from pathlib import Path
import re
import sys

standard_canvas_width = 680.0
large_canvas_minimum_width = 1360.0
large_canvas_maximum_width = 2000.0
text_floor_at_standard_width = 16.0
connector_tags = {"line", "path", "polyline"}
tag_pattern = re.compile(r"<(/?)([a-zA-Z][\w:.-]*)([^>]*?)(/?)>", re.DOTALL)
fill_pattern = re.compile(r'\bfill=["\']([^"\']*)["\']')
style_fill_pattern = re.compile(r'style=["\'][^"\']*\bfill\s*:\s*([^;"\']+)')
marker_pattern = re.compile(r"\bmarker-(?:start|mid|end)=")


def find_unfilled_connectors(markup: str) -> list[str]:
    """Name every connector whose fill resolves to something other than none.

    A connector is a line, path, or polyline carrying a marker. Its fill comes
    from its own attribute when it has one, and from the nearest enclosing
    element otherwise::

        <g fill="none"><line marker-end="url(#a)"/></g>   ok: inherits none
        <line fill="red" marker-end="url(#a)"/>           flag: own fill wins
        <path d="M0 0L9 9Z" fill="currentColor"/>         ok: glyph, no marker

    Args:
        markup: The full SVG or HTML source text.

    Returns:
        The tag name of each offending connector, in document order.
    """
    inherited_fills = [""]
    offenders = []
    for each_tag in tag_pattern.finditer(markup):
        is_closing, tag_name, attributes, is_self_closing = each_tag.groups()
        if is_closing:
            inherited_fills = inherited_fills[:-1] or [""]
            continue
        own_fill = style_fill_pattern.search(attributes) or fill_pattern.search(attributes)
        effective_fill = own_fill.group(1).strip() if own_fill else inherited_fills[-1]
        is_connector = tag_name in connector_tags and bool(marker_pattern.search(attributes))
        if is_connector and effective_fill != "none": offenders.append(tag_name)
        if not is_self_closing: inherited_fills.append(effective_fill)
    return offenders


if len(sys.argv[1:]) != 1:
    raise SystemExit("usage: validate-artifact.py <svg-or-html>")
path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(f"missing artifact: {path}")
text = path.read_text(encoding="utf-8")
errors = []
warnings = []
defined_properties = set(re.findall(r'(--[\w-]+)\s*:', text))
for each_property_name in re.findall(r'var\(\s*(--[\w-]+)', text):
    if each_property_name not in defined_properties: errors.append(f"undefined custom property {each_property_name}")
defined_ids = set(re.findall(r'\bid=["\']([^"\']+)["\']', text))
referenced_ids = re.findall(r'href=["\']#([^"\']+)["\']', text) + re.findall(r'url\(\s*#([^)\s"\']+)', text)
for each_referenced_id in referenced_ids:
    if each_referenced_id not in defined_ids: errors.append(f"reference to missing id #{each_referenced_id}")
if path.suffix.lower() == ".svg":
    if not re.search(r'<svg[^>]+role=["\']img["\']', text): errors.append("SVG needs role=img")
    viewbox = re.search(r'<svg[^>]+viewBox=["\']0 0 ([0-9.]+) ', text)
    canvas_width = float(viewbox.group(1)) if viewbox else 0.0
    is_standard_canvas = canvas_width == standard_canvas_width
    is_large_canvas = large_canvas_minimum_width <= canvas_width <= large_canvas_maximum_width
    if not is_standard_canvas and not is_large_canvas: errors.append("SVG viewBox width must be 680 or 1360-2000")
    if not re.search(r'<svg[^>]*>\s*<title>.*?</title>\s*<desc>', text, re.DOTALL): errors.append("SVG title and desc must be first")
    if find_unfilled_connectors(text): errors.append("connectors need fill=none")
    text_floor = round(text_floor_at_standard_width * canvas_width / standard_canvas_width)
    sizes = [float(x) for x in re.findall(r'font-size=["\']([0-9.]+)', text)]
    if any(size < text_floor for size in sizes): errors.append(f"text below {text_floor}px")
    for each_marker in re.findall(r'<marker\b[^>]*>', text):
        if not re.search(r'markerUnits=["\']userSpaceOnUse["\']', each_marker): warnings.append("marker without markerUnits=userSpaceOnUse scales with stroke width")
elif path.suffix.lower() in {".html", ".htm"}:
    if not re.match(r'\s*<h2[^>]+class=["\']sr-only["\']', text): errors.append("HTML needs a first sr-only h2")
    if re.search(r'position\s*:\s*fixed|overflow\s*:\s*(?:auto|scroll)', text): errors.append("fixed positioning and nested scrolling are forbidden")
else:
    errors.append("artifact must be SVG or HTML")
for each_warning in warnings:
    print(f"ARTIFACT WARNING: {each_warning}")
if errors:
    print("ARTIFACT INVALID")
    print("\n".join(errors))
    sys.exit(1)
print(f"ARTIFACT VALID: {path.name}")
