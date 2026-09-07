from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(TESTS_DIRECTORY))

import test_automatic_advisory as support
import test_automatic_advisory_repairs as process_support

OWNER_EXIT_TIMEOUT_SECONDS = 10.0
CHILD_START_WAIT_SECONDS = 5.0
CHILD_START_POLL_SECONDS = 0.05


def _build_owner_exit_script(
    checkout_path: Path,
    child_identifier_path: Path,
) -> str:
    child_script = (
        "import os,time\n"
        "from pathlib import Path\n"
        f"Path({str(child_identifier_path)!r}).write_text(str(os.getpid()), encoding='utf-8')\n"
        "time.sleep(30)\n"
    )
    return (
        "import os,sys,time\n"
        "from pathlib import Path\n"
        "from types import SimpleNamespace\n"
        "from automatic_advisory import execution\n"
        f"registration = SimpleNamespace(checkout_path=Path({str(checkout_path)!r}))\n"
        "scripts_directory = Path(execution.__file__).resolve().parents[1]\n"
        "child_environment = execution._build_child_environment(registration, scripts_directory)\n"
        "owned_child = execution._start_child_process(\n"
        f"    (sys.executable, '-c', {child_script!r}), registration, child_environment\n"
        ")\n"
        "if owned_child is None:\n"
        "    raise SystemExit(2)\n"
        f"deadline = time.monotonic() + {CHILD_START_WAIT_SECONDS!r}\n"
        f"while not Path({str(child_identifier_path)!r}).is_file() and time.monotonic() < deadline:\n"
        f"    time.sleep({CHILD_START_POLL_SECONDS!r})\n"
        f"if not Path({str(child_identifier_path)!r}).is_file():\n"
        "    raise SystemExit(3)\n"
        "os._exit(0)\n"
    )


def test_owner_exit_closes_job_and_ends_active_child(tmp_path: Path) -> None:
    if sys.platform != "win32":
        return
    child_identifier_path = tmp_path / "owned-child.pid"
    owner_script = _build_owner_exit_script(tmp_path, child_identifier_path)
    completed_owner = subprocess.run(
        (sys.executable, "-c", owner_script),
        cwd=support.SCRIPTS_DIRECTORY,
        capture_output=True,
        check=False,
        text=True,
        timeout=OWNER_EXIT_TIMEOUT_SECONDS,
    )
    assert child_identifier_path.is_file(), completed_owner.stderr
    child_identifier = int(child_identifier_path.read_text(encoding="utf-8"))

    try:
        assert completed_owner.returncode == 0, completed_owner.stderr
        assert process_support._wait_for_process_exit(child_identifier)
    finally:
        process_support._end_process_for_test(child_identifier)
