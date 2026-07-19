"""Named constants for the validators package (designated config module).

The CODE_RULES gate treats every constant defined here as configuration, so the
validator modules that import these names carry no magic-value, string-magic, or
single-use-constant finding. Extensions, join separators, git command vectors,
display widths, and slice indices all live here.
"""

from pathlib import Path
from typing import Final

VALIDATORS_DIR = Path(__file__).resolve().parent.parent

PYTHON_EXTENSION = ".py"
ALL_REACT_FILE_EXTENSIONS = (".tsx", ".jsx")
ALL_CODE_FILE_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".jsx")

LINE_SEPARATOR = "\n"
MODULE_PATH_SEPARATOR = "."

ALL_GIT_STAGED_DIFF_COMMAND = ["git", "diff", "--cached", "--name-only"]
ALL_GIT_LAST_COMMIT_DIFF_COMMAND = ["git", "diff", "--name-only", "HEAD~1"]

SEPARATOR_WIDTH = 60
DEFAULT_CONTEXT_LINES = 2
FILE_DISPLAY_CAP = 10
MYPY_OUTPUT_TRUNCATION_LIMIT = 500
MESSAGE_PARTITION_INDEX = 2
IDENTITY_KEY_LENGTH: Final = 2
