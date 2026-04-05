"""Test file with @pytest.mark.skip (no args) - SHOULD BE CAUGHT"""
import pytest


@pytest.mark.skip
def test_something():
    assert True
