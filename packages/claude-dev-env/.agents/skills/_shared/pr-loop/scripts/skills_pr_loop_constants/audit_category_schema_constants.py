"""Constants for audit_category_schema path resolution and parity checks."""

from __future__ import annotations

import re
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent.parent
_skills_home_directory = SCRIPTS_DIRECTORY.parents[3]
PACKAGE_ROOT = (
    _skills_home_directory.parent
    if _skills_home_directory.name == ".agents"
    else _skills_home_directory
)
SCHEMA_RELATIVE_PATH = Path("audit-rubrics") / "audit-categories.json"
CATEGORY_RUBRICS_DIRECTORY = PACKAGE_ROOT / "audit-rubrics" / "category_rubrics"
PROMPTS_DIRECTORY = PACKAGE_ROOT / "audit-rubrics" / "prompts"
HEADING_PATTERN = re.compile(r"^# Category ([A-Q]) — (.+)$")
HEADING_LETTER_GROUP = 1
HEADING_TITLE_GROUP = 2
EXPECTED_CATEGORY_IDS = tuple("ABCDEFGHIJKLMNOPQ")
SCHEMA_VERSION = 1
JSON_INDENT = 2
NEWLINE = "\n"
UTF8_ENCODING = "utf-8"
RUBRIC_SUB_BUCKET_ROW_TEMPLATE = r"^\| ({category_id}\d+) \| ([^|]+) \|"
SKELETON_COUNT_PATTERN = re.compile(r"decomposed into (\d+) sub-buckets")
SKELETON_PLACEHOLDER_FRAGMENT = "decomposed into [N] sub-buckets"
SKELETON_SEPARATOR_LINE = "---"
CATEGORY_SLUG_PREFIX_TEMPLATE = "category-{letter}-"
CATEGORY_ID_KEY = "id"
CATEGORY_TITLE_KEY = "title"
CATEGORY_SLUG_KEY = "slug"
CATEGORY_SUB_BUCKETS_KEY = "sub_buckets"
SUB_BUCKET_AXIS_KEY = "axis_name"
SCHEMA_CATEGORIES_KEY = "categories"
SCHEMA_VERSION_KEY = "schema_version"
