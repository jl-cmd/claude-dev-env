"""Test file with @pytest.mark.xfail - should NOT be caught (allowed)"""
import pytest


@pytest.mark.xfail(reason="Known bug")
def test_something():
    assert False
