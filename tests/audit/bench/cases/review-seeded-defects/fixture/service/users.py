import json
import sqlite3


def find_user(connection: sqlite3.Connection, name: str) -> list[tuple]:
    query = "SELECT id, name FROM users WHERE name = '" + name + "'"
    return connection.execute(query).fetchall()


def add_tag(tag: str, all_tags: list[str] = []) -> list[str]:
    all_tags.append(tag)
    return all_tags


def load_profile(path: str) -> dict:
    handle = open(path, encoding="utf-8")
    return json.load(handle)


def display_name(first: str, last: str) -> str:
    return f"{first} {last}".strip()
