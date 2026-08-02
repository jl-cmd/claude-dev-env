from pathlib import Path
import sys

skill_root = Path(__file__).resolve().parents[1]
required = ["SKILL.md", "routing.yaml", "references/core-design.md", "references/accessibility.md", "references/quality-gates.md", "references/subject-inventory.md", "workflows/create-visual.md", "workflows/review-visual.md", "templates/svg-base.svg", "templates/html-widget.html"]
missing = [p for p in required if not (skill_root / p).is_file()]
text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
errors = missing[:]
for each_token in ["routing.yaml", "workflows/create-visual.md", "references/quality-gates.md"]:
    if each_token not in text:
        errors.append(f"SKILL.md missing {each_token}")
if errors:
    print("PACKAGE INVALID")
    print("\n".join(errors))
    sys.exit(1)
print(f"PACKAGE VALID: {len(required)} required files present")
