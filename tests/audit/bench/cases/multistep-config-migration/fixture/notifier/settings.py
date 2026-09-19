import configparser
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    retries: int
    all_recipients: tuple[str, ...]


def load_settings(directory: Path) -> Settings:
    parser = configparser.ConfigParser()
    parser.read(directory / "config.ini", encoding="utf-8")
    return Settings(
        host=parser["smtp"]["host"],
        port=parser.getint("smtp", "port"),
        retries=parser.getint("notify", "retries"),
        all_recipients=tuple(
            each_address.strip() for each_address in parser["notify"]["recipients"].split(",")
        ),
    )
