import re

PATTERN = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")


def parse_duration(text: str) -> int:
    text = text.strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    match = PATTERN.fullmatch(text)
    if match is None:
        raise ValueError(f"bad duration: {text}")
    hours, minutes, seconds = (int(each_group or 0) for each_group in match.groups())
    return hours * 3600 + minutes * 60 + seconds
