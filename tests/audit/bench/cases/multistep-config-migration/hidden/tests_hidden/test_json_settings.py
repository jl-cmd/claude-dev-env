import json
from pathlib import Path

from notifier.settings import Settings, load_settings

ROOT = Path(__file__).resolve().parent.parent


def test_repository_json_keeps_every_value():
    assert load_settings(ROOT) == Settings(
        host="mail.example.invalid",
        port=2525,
        retries=4,
        all_recipients=("ops@example.invalid", "dev@example.invalid"),
    )


def test_reads_json_from_given_directory(tmp_path):
    (tmp_path / "config.json").write_text(
        json.dumps({"smtp": {"host": "h", "port": 1}, "notify": {"retries": 0, "recipients": ["a@example.invalid"]}}),
        encoding="utf-8",
    )
    assert load_settings(tmp_path) == Settings("h", 1, 0, ("a@example.invalid",))
