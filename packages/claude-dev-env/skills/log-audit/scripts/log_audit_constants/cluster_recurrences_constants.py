"""Constants for the cluster_recurrences script.

PATH_PATTERN, HASH_PATTERN, DIGIT_PATTERN: regexes stripped from a message, in this
    order, so records that differ only in a path, hash, or number share one signature.
SIGNATURE_PLACEHOLDER: the token each stripped span collapses to.
SECONDS_PER_HOUR: seconds in one hour, dividing a record's age into hours.
RECENCY_DECAY_BASE: the weight a record carries once it is one half-life old.
RECENCY_HALF_LIFE_HOURS: age in hours at which a record's weight reaches the decay base.
TIMING_REGRESSION_RATIO: recent-over-baseline duration ratio that flags a regression.
MIN_TIMING_SAMPLES_PER_HALF: samples required in the baseline half and the recent half.
SAMPLE_HALVES: the number of halves a timing series splits into before it can be judged.
"""

PATH_PATTERN = r"(?:[A-Za-z]:)?(?:[\\/][\w.\-]+)+"
HASH_PATTERN = r"\b[0-9a-f]{7,40}\b"
DIGIT_PATTERN = r"\d+"
SIGNATURE_PLACEHOLDER = "*"
SECONDS_PER_HOUR = 3600
RECENCY_DECAY_BASE = 0.5
RECENCY_HALF_LIFE_HOURS = 24.0
TIMING_REGRESSION_RATIO = 1.5
MIN_TIMING_SAMPLES_PER_HALF = 3
SAMPLE_HALVES = 2