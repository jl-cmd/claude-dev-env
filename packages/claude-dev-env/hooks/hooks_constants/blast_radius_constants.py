"""Constants for the blast-radius declaration check."""

BLAST_RADIUS_RUN_SUFFIX = "RunFatal"
BLAST_RADIUS_ITEM_SUFFIX = "ItemBlocked"
ALL_BLAST_RADIUS_SUFFIXES = (BLAST_RADIUS_RUN_SUFFIX, BLAST_RADIUS_ITEM_SUFFIX)

MAX_BLAST_RADIUS_ISSUES = 20

BLAST_RADIUS_MESSAGE_SUFFIX = (
    "raises inside per-item work without naming its blast radius — end the type in "
    f"{BLAST_RADIUS_RUN_SUFFIX} when the whole run stops, or {BLAST_RADIUS_ITEM_SUFFIX} "
    "when only this one item stops and the batch carries on. See "
    "rules/failure-blast-radius.md."
)
