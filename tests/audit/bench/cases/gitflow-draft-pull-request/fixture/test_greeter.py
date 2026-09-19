from greeter import greet


def test_greet():
    assert greet("Ada").startswith("Hello")
