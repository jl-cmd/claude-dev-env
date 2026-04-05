"""Test file with @skip() with parentheses - SHOULD BE CAUGHT"""
import pytest
from unittest import skip


@skip("test reason")
def test_something():
    assert True
