"""Verify all validator paths referenced in SKILL.md exist."""

import re
import sys
from pathlib import Path


SKILL_MD_PATH = Path(__file__).parent.parent.parent / "skills" / "pr-review-responder" / "SKILL.md"
VALIDATORS_DIR = Path(__file__).parent


def extract_validator_paths(content: str) -> list[str]:
    """Extract validator file paths from SKILL.md content."""
    pattern = r"validators[/\\](\w+\.py)"
    matches = re.findall(pattern, content)
    return list(set(matches))


def verify_validators() -> int:
    """Verify all referenced validators exist.

    Returns:
        Exit code: 0 if all exist, 1 if any missing
    """
    if not SKILL_MD_PATH.exists():
        print(f"ERROR: SKILL.md not found at {SKILL_MD_PATH}")
        return 1

    content = SKILL_MD_PATH.read_text(encoding="utf-8")
    referenced_validators = extract_validator_paths(content)

    print(f"Found {len(referenced_validators)} validator references in SKILL.md")
    print()

    missing = []
    for validator_file in sorted(referenced_validators):
        validator_path = VALIDATORS_DIR / validator_file
        if validator_path.exists():
            print(f"  [OK] {validator_file}")
        else:
            print(f"  [MISSING] {validator_file}")
            missing.append(validator_file)

    print()

    if missing:
        print(f"ERROR: {len(missing)} validator(s) missing:")
        for validator_file in missing:
            print(f"  - {validator_file}")
        return 1

    print("All referenced validators exist.")
    return 0


if __name__ == "__main__":
    sys.exit(verify_validators())
