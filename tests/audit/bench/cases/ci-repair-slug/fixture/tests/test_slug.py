from textutil.slug import slugify


def test_lowercases():
    assert slugify("Hello") == "hello"


def test_replaces_space():
    assert slugify("a b") == "a-b"


def test_collapses_runs():
    assert slugify("Hello --  World") == "hello-world"
