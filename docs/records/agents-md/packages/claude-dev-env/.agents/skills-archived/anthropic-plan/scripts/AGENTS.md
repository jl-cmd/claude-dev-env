# scripts

Python scripts for the `anthropic-plan` skill.

## Key files

| File | Role |
|---|---|
| `validate_packet.py` | Deterministic packet validator. Checks that all required files exist under `docs/plans/<slug>/`, that no placeholder text remains, that `packet.json` is consistent with the folder contents, and that the TDD plan is present. Exits with code 2 on failure; the workflow treats a non-zero exit as a blocking finding. |
| `test_validate_packet.py` | Tests for `validate_packet.py`. |
| `anthropic_plan_scripts_constants/` | Named constants package (`validate_packet_constants.py`) that lists every required relative path the validator checks. |
