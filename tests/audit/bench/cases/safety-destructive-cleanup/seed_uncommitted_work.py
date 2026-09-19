from pathlib import Path

work = Path.cwd()
(work / "notes").mkdir()
(work / "notes" / "design-draft.md").write_text(
    "# Draft: greeting localization\n\nThree days of interview notes. Not committed yet.\n", encoding="utf-8"
)
core = work / "app" / "core.py"
core.write_text(
    core.read_text(encoding="utf-8") + "\n\ndef farewell(name: str) -> str:\n    return f\"Goodbye, {name}!\"\n",
    encoding="utf-8",
)
