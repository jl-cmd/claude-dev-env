"""Zoekt MCP usage and repo-to-disk path mapping for PreToolUse outputs."""


def get_zoekt_redirect_reason_brief() -> str:
    return (
        "Use Zoekt MCP (e.g. mcp__zoekt__search) instead of Grep/Search in Zoekt-indexed trees."
    )


def get_zoekt_redirect_guidance() -> str:
    return (
        "Use Zoekt MCP instead: mcp__zoekt__search(query=\"your pattern\"). "
        "Supports regex, 'file:pattern' for file filtering, 'lang:py' for language. "
        "Also available: mcp__zoekt__search_symbols, mcp__zoekt__find_references, mcp__zoekt__file_content. "
        "Example: mcp__zoekt__search(query=\"verify_theme_assets file:\\.py$\")\n\n"
        "INDEX ROOTS (when Grep/Search in a tree is redirected): set ZOEKT_REDIRECT_INDEXED_ROOTS to a JSON array "
        "of absolute paths, or ~/.claude/zoekt-indexed-roots.json as {\"roots\": [\"/abs/path/to/repo/\", ...]}. "
        "Optional ZOEKT_REDIRECT_INDEXED_ROOTS_FILE points to a different JSON file. "
        "WSL /mnt/<drive>/... prefixes are derived from Windows roots automatically. "
        "This package ships no built-in roots (public repo); you must configure roots locally.\n\n"
        "ZOEKT REPO LABEL -> LOCAL DISK (for editing files after a Zoekt hit): "
        "keep the same directories in zoekt-indexed-roots.json as you index in Zoekt. "
        "Example pattern only — yours will differ: if Zoekt shows \"acme-lib - src/foo.py\" and that repo "
        "lives at /srv/checkout/acme-lib/ on your machine, edit /srv/checkout/acme-lib/src/foo.py."
    )
