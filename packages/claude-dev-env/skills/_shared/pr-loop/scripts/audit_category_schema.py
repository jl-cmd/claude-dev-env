"""Load and validate the A-Q audit-category schema.

One machine-readable source under audit-rubrics/audit-categories.json holds
each category id, title, slug, and sub-bucket id/axis pairs. Worked examples
stay in the rubric markdown files only.

::

    schema = load_audit_category_schema()
    entries = category_id_title_entries()
    # entries[0] == ("A", "API contract verification")
    findings = validate_projections()
    # findings == [] when rubrics and prompt skeletons match the schema

Use validate_projections before shipping a rubric or prompt change so the
three surfaces cannot drift.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from skills_pr_loop_constants.audit_category_schema_constants import (
    CATEGORY_ID_KEY,
    CATEGORY_RUBRICS_DIRECTORY,
    CATEGORY_SLUG_KEY,
    CATEGORY_SLUG_PREFIX_TEMPLATE,
    CATEGORY_SUB_BUCKETS_KEY,
    CATEGORY_TITLE_KEY,
    EXPECTED_CATEGORY_IDS,
    HEADING_LETTER_GROUP,
    HEADING_PATTERN,
    HEADING_TITLE_GROUP,
    JSON_INDENT,
    NEWLINE,
    PACKAGE_ROOT,
    PROMPTS_DIRECTORY,
    RUBRIC_SUB_BUCKET_ROW_TEMPLATE,
    SCHEMA_CATEGORIES_KEY,
    SCHEMA_RELATIVE_PATH,
    SCHEMA_VERSION,
    SCHEMA_VERSION_KEY,
    SKELETON_COUNT_PATTERN,
    SKELETON_PLACEHOLDER_FRAGMENT,
    SKELETON_SEPARATOR_LINE,
    SUB_BUCKET_AXIS_KEY,
    UTF8_ENCODING,
)

CategoryMapping = dict[str, object]
SchemaMapping = dict[str, object]


def audit_category_schema_path() -> Path:
    """Return the path to the committed A-Q schema JSON file.

    Returns:
        Absolute path to audit-categories.json under the package root.
    """
    return PACKAGE_ROOT / SCHEMA_RELATIVE_PATH


def load_audit_category_schema() -> SchemaMapping:
    """Load and structurally check the A-Q schema document.

    Returns:
        The schema object with schema_version and categories.

    Raises:
        FileNotFoundError: When the schema file is missing.
        ValueError: When required fields or order are wrong.
        json.JSONDecodeError: When the schema file is not valid JSON.
    """
    schema_path = audit_category_schema_path()
    loaded_document = json.loads(schema_path.read_text(encoding=UTF8_ENCODING))
    if not isinstance(loaded_document, dict):
        raise ValueError("schema root must be an object")
    if loaded_document.get(SCHEMA_VERSION_KEY) != SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {SCHEMA_VERSION}, "
            f"got {loaded_document.get(SCHEMA_VERSION_KEY)!r}"
        )
    all_categories = loaded_document.get(SCHEMA_CATEGORIES_KEY)
    if not isinstance(all_categories, list) or not all_categories:
        raise ValueError("categories must be a non-empty list")
    all_ids = [
        each_category.get(CATEGORY_ID_KEY)
        for each_category in all_categories
        if isinstance(each_category, dict)
    ]
    if all_ids != list(EXPECTED_CATEGORY_IDS):
        raise ValueError(f"categories must list A-Q in order, got {all_ids!r}")
    all_checked_categories: list[CategoryMapping] = []
    for each_category in all_categories:
        if not isinstance(each_category, dict):
            raise ValueError("each category must be an object")
        all_checked_categories.append(_require_category_shape(each_category))
    return {
        SCHEMA_VERSION_KEY: SCHEMA_VERSION,
        SCHEMA_CATEGORIES_KEY: all_checked_categories,
    }


def _require_category_shape(all_category_fields: CategoryMapping) -> CategoryMapping:
    category_id = all_category_fields.get(CATEGORY_ID_KEY)
    if not isinstance(category_id, str) or len(category_id) != 1:
        raise ValueError(f"category id must be a single letter, got {category_id!r}")
    title = all_category_fields.get(CATEGORY_TITLE_KEY)
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"category {category_id} title must be a non-empty string")
    slug = all_category_fields.get(CATEGORY_SLUG_KEY)
    expected_slug_prefix = CATEGORY_SLUG_PREFIX_TEMPLATE.format(letter=category_id.lower())
    if not isinstance(slug, str) or not slug.startswith(expected_slug_prefix):
        raise ValueError(
            f"category {category_id} slug must start with {expected_slug_prefix!r}, "
            f"got {slug!r}"
        )
    all_sub_bucket_fields = all_category_fields.get(CATEGORY_SUB_BUCKETS_KEY)
    if not isinstance(all_sub_bucket_fields, list) or not all_sub_bucket_fields:
        raise ValueError(f"category {category_id} needs a non-empty sub_buckets list")
    all_sub_buckets: list[CategoryMapping] = []
    for each_index, each_sub_bucket in enumerate(all_sub_bucket_fields):
        if not isinstance(each_sub_bucket, dict):
            raise ValueError(f"category {category_id} sub_bucket {each_index} must be object")
        expected_id = f"{category_id}{each_index + 1}"
        sub_bucket_id = each_sub_bucket.get(CATEGORY_ID_KEY)
        if sub_bucket_id != expected_id:
            raise ValueError(
                f"category {category_id} sub_bucket {each_index} id must be "
                f"{expected_id}, got {sub_bucket_id!r}"
            )
        axis_name = each_sub_bucket.get(SUB_BUCKET_AXIS_KEY)
        if not isinstance(axis_name, str) or not axis_name.strip():
            raise ValueError(
                f"category {category_id} sub_bucket {sub_bucket_id} needs axis_name"
            )
        all_sub_buckets.append(
            {CATEGORY_ID_KEY: expected_id, SUB_BUCKET_AXIS_KEY: axis_name}
        )
    return {
        CATEGORY_ID_KEY: category_id,
        CATEGORY_TITLE_KEY: title,
        CATEGORY_SLUG_KEY: slug,
        CATEGORY_SUB_BUCKETS_KEY: all_sub_buckets,
    }


def category_id_title_entries() -> list[tuple[str, str]]:
    """Return (id, title) pairs in A-Q order from the schema.

    Returns:
        List of (category letter, title) tuples from the schema file.
    """
    all_schema = load_audit_category_schema()
    all_categories = all_schema[SCHEMA_CATEGORIES_KEY]
    assert isinstance(all_categories, list)
    all_entries: list[tuple[str, str]] = []
    for each_category in all_categories:
        assert isinstance(each_category, dict)
        category_id = each_category[CATEGORY_ID_KEY]
        title = each_category[CATEGORY_TITLE_KEY]
        assert isinstance(category_id, str)
        assert isinstance(title, str)
        all_entries.append((category_id, title))
    return all_entries


def render_skeleton_projections(all_schema: SchemaMapping) -> dict[str, str]:
    """Build deterministic skeleton text per category from the schema only.

    Args:
        all_schema: Loaded audit-category schema.

    Returns:
        Map of category letter to a stable multi-line skeleton projection.
    """
    projection_by_letter: dict[str, str] = {}
    all_categories = all_schema[SCHEMA_CATEGORIES_KEY]
    assert isinstance(all_categories, list)
    for each_category in all_categories:
        assert isinstance(each_category, dict)
        category_id = each_category[CATEGORY_ID_KEY]
        title = each_category[CATEGORY_TITLE_KEY]
        slug = each_category[CATEGORY_SLUG_KEY]
        all_sub_buckets = each_category[CATEGORY_SUB_BUCKETS_KEY]
        assert isinstance(category_id, str)
        assert isinstance(title, str)
        assert isinstance(slug, str)
        assert isinstance(all_sub_buckets, list)
        sub_bucket_count = len(all_sub_buckets)
        all_lines = [
            f"Category {category_id} — {title}",
            f"slug: {slug}",
            f"decomposed into {sub_bucket_count} sub-buckets",
            f"For each sub-bucket {category_id}1-{category_id}{sub_bucket_count}:",
        ]
        for each_sub_bucket in all_sub_buckets:
            assert isinstance(each_sub_bucket, dict)
            sub_bucket_id = each_sub_bucket[CATEGORY_ID_KEY]
            axis_name = each_sub_bucket[SUB_BUCKET_AXIS_KEY]
            all_lines.append(f"{sub_bucket_id}. {axis_name}")
        projection_by_letter[category_id] = NEWLINE.join(all_lines) + NEWLINE
    return projection_by_letter


def _validate_one_category(each_category: CategoryMapping) -> list[str]:
    category_id = each_category[CATEGORY_ID_KEY]
    slug = each_category[CATEGORY_SLUG_KEY]
    title = each_category[CATEGORY_TITLE_KEY]
    all_sub_buckets = each_category[CATEGORY_SUB_BUCKETS_KEY]
    assert isinstance(category_id, str)
    assert isinstance(slug, str)
    assert isinstance(title, str)
    assert isinstance(all_sub_buckets, list)
    all_findings: list[str] = []
    rubric_path = CATEGORY_RUBRICS_DIRECTORY / f"{slug}.md"
    prompt_path = PROMPTS_DIRECTORY / f"{slug}.md"
    if not rubric_path.is_file():
        return [f"{category_id}: missing rubric {rubric_path.name}"]
    if not prompt_path.is_file():
        return [f"{category_id}: missing prompt {prompt_path.name}"]
    rubric_text = rubric_path.read_text(encoding=UTF8_ENCODING)
    all_rubric_lines = rubric_text.splitlines()
    if not all_rubric_lines:
        return [f"{category_id}: empty rubric"]
    heading_match = HEADING_PATTERN.match(all_rubric_lines[0])
    if heading_match is None:
        return [f"{category_id}: rubric heading does not match pattern"]
    heading_letter = heading_match.group(HEADING_LETTER_GROUP)
    heading_title = heading_match.group(HEADING_TITLE_GROUP)
    if heading_letter != category_id:
        all_findings.append(f"{category_id}: rubric heading letter {heading_letter!r}")
    if heading_title != title:
        all_findings.append(
            f"{category_id}: rubric title {heading_title!r} != schema {title!r}"
        )
    row_pattern = re.compile(
        RUBRIC_SUB_BUCKET_ROW_TEMPLATE.format(category_id=re.escape(category_id)),
        re.MULTILINE,
    )
    all_rubric_rows = row_pattern.findall(rubric_text)
    all_schema_rows: list[tuple[str, str]] = []
    for each_sub_bucket in all_sub_buckets:
        assert isinstance(each_sub_bucket, dict)
        sub_bucket_id = each_sub_bucket[CATEGORY_ID_KEY]
        axis_name = each_sub_bucket[SUB_BUCKET_AXIS_KEY]
        assert isinstance(sub_bucket_id, str)
        assert isinstance(axis_name, str)
        all_schema_rows.append((sub_bucket_id, axis_name))
    all_rubric_pairs = [(row_id, axis.strip()) for row_id, axis in all_rubric_rows]
    if all_rubric_pairs != all_schema_rows:
        all_findings.append(
            f"{category_id}: rubric sub-buckets {all_rubric_pairs!r} "
            f"!= schema {all_schema_rows!r}"
        )
    all_findings.extend(
        _validate_prompt_skeleton_count(category_id, prompt_path, len(all_sub_buckets))
    )
    return all_findings


def _validate_prompt_skeleton_count(
    category_id: str,
    prompt_path: Path,
    sub_bucket_count: int,
) -> list[str]:
    prompt_text = prompt_path.read_text(encoding=UTF8_ENCODING)
    all_skeleton_lines: list[str] = []
    for each_line in prompt_text.splitlines():
        if each_line == SKELETON_SEPARATOR_LINE:
            break
        all_skeleton_lines.append(each_line)
    skeleton_text = NEWLINE.join(all_skeleton_lines)
    count_match = SKELETON_COUNT_PATTERN.search(skeleton_text)
    if count_match is not None:
        skeleton_count = int(count_match.group(HEADING_LETTER_GROUP))
        if skeleton_count != sub_bucket_count:
            return [
                f"{category_id}: prompt skeleton count {skeleton_count} "
                f"!= schema {sub_bucket_count}"
            ]
        return []
    if SKELETON_PLACEHOLDER_FRAGMENT not in skeleton_text:
        return [f"{category_id}: prompt skeleton missing sub-bucket count form"]
    return []


def validate_projections() -> list[str]:
    """Compare schema against on-disk rubric and prompt skeleton projections.

    Returns:
        Finding strings; empty when every category is in parity.
    """
    all_schema = load_audit_category_schema()
    all_categories = all_schema[SCHEMA_CATEGORIES_KEY]
    assert isinstance(all_categories, list)
    all_findings: list[str] = []
    for each_category in all_categories:
        assert isinstance(each_category, dict)
        all_findings.extend(_validate_one_category(each_category))
    return all_findings


def main(all_argv: list[str]) -> int:
    """CLI: validate projections or print deterministic skeleton projections.

    Args:
        all_argv: Argument list without the program name.

    Returns:
        Process exit code (0 success, 1 validation findings).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate rubric and prompt projections against the schema.",
    )
    parser.add_argument(
        "--render-skeletons",
        action="store_true",
        help="Print deterministic skeleton projections as JSON.",
    )
    arguments = parser.parse_args(all_argv)
    if arguments.validate:
        all_findings = validate_projections()
        if all_findings:
            for each_finding in all_findings:
                print(each_finding, file=sys.stderr)
            return 1
        print("OK")
        return 0
    if arguments.render_skeletons:
        all_schema = load_audit_category_schema()
        print(
            json.dumps(
                render_skeleton_projections(all_schema),
                indent=JSON_INDENT,
                ensure_ascii=False,
            )
        )
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
