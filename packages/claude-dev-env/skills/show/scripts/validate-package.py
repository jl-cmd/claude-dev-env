import re
from pathlib import Path
import sys

skill_root = Path(__file__).resolve().parents[1]
routing_text = (skill_root / "routing.yaml").read_text(encoding="utf-8")
routed = re.findall(r"(?:references|workflows|templates)/[\w.-]+", routing_text)
required = ["SKILL.md", "routing.yaml", "workflows/review-visual.md", *sorted(set(routed))]
text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
errors = [p for p in required if not (skill_root / p).is_file()]
for each_token in ["routing.yaml", "workflows/create-visual.md"]:
    if each_token not in text:
        errors.append(f"SKILL.md missing {each_token}")
if errors:
    print("PACKAGE INVALID")
    print("\n".join(errors))
    sys.exit(1)
print(f"PACKAGE VALID: {len(required)} required files present")
