"""Specifications for the bootstrap listener install closure.

The sync-ai-rules listener imports ``config.sync_ai_rules_paths`` through a
repo-root ``sys.path`` insert, so a working install into a target repo needs the
whole repo-local import closure: the workflow, the listener script, the paths
config module, and the ``config`` package marker. These specifications pin that
closure and prove both install surfaces — the bootstrap script and the manual
copy block in the docs — carry every file in it.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_SCRIPT_PATH = REPO_ROOT / "scripts" / "bootstrap-listeners.sh"
SYNC_DOC_PATH = REPO_ROOT / "docs" / "ai-rules-sync.md"

LISTENER_WORKFLOW_PATH = ".github/workflows/sync-ai-rules.yml"
LISTENER_SCRIPT_PATH = ".github/scripts/sync_ai_rules.py"
SYNC_PATHS_CONFIG_PATH = "config/sync_ai_rules_paths.py"
CONFIG_PACKAGE_MARKER_PATH = "config/__init__.py"
REQUIRED_LISTENER_PATHS: tuple[str, ...] = (
    LISTENER_WORKFLOW_PATH,
    LISTENER_SCRIPT_PATH,
    SYNC_PATHS_CONFIG_PATH,
    CONFIG_PACKAGE_MARKER_PATH,
)

CONFIG_IMPORT_STATEMENT = "from config.sync_ai_rules_paths import"
MANUAL_COPY_MARKER = "Or copy manually"
FENCED_BLOCK_DELIMITER = "```"
LINE_BREAK = "\n"


def extract_manual_copy_block(document_text: str) -> str:
    marker_index = document_text.index(MANUAL_COPY_MARKER)
    fence_open_index = document_text.index(FENCED_BLOCK_DELIMITER, marker_index)
    block_body_start = document_text.index(LINE_BREAK, fence_open_index) + 1
    fence_close_index = document_text.index(FENCED_BLOCK_DELIMITER, block_body_start)
    return document_text[block_body_start:fence_close_index]


class TestRequiredListenerPathsFormTheImportClosure:
    def should_resolve_every_required_path_to_a_file_on_disk(self) -> None:
        for each_required_path in REQUIRED_LISTENER_PATHS:
            assert (REPO_ROOT / each_required_path).is_file()

    def should_import_the_sync_paths_config_from_the_listener_script(self) -> None:
        script_text = (REPO_ROOT / LISTENER_SCRIPT_PATH).read_text(encoding="utf-8")

        assert CONFIG_IMPORT_STATEMENT in script_text


class TestBootstrapScriptInstallsEveryRequiredPath:
    def should_name_every_required_path_as_a_copy_source(self) -> None:
        script_text = BOOTSTRAP_SCRIPT_PATH.read_text(encoding="utf-8")

        for each_required_path in REQUIRED_LISTENER_PATHS:
            assert each_required_path in script_text


class TestManualCopyDocInstallsEveryRequiredPath:
    def should_name_every_required_path_in_the_manual_copy_block(self) -> None:
        document_text = SYNC_DOC_PATH.read_text(encoding="utf-8")
        manual_copy_block = extract_manual_copy_block(document_text)

        for each_required_path in REQUIRED_LISTENER_PATHS:
            assert each_required_path in manual_copy_block
