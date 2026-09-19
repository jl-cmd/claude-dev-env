from pathlib import Path

from notifier.settings import load_settings


def test_loads_repository_config():
    settings = load_settings(Path(__file__).resolve().parent.parent)
    assert settings.port == 2525
    assert settings.all_recipients == ("ops@example.invalid", "dev@example.invalid")
