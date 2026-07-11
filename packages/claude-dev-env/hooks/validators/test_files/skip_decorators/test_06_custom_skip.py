"""Test file with custom @skip_on_windows - should NOT be caught"""
import pytest


def skip_on_windows(func):
    return func


@skip_on_windows
def test_something():
    assert True
