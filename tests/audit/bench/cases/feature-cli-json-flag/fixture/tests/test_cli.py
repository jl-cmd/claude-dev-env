from wordcount.cli import count


def test_count():
    assert count("a b\nc\n") == (2, 3, 6)
