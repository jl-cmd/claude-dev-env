"""Test file with @pytest.mark.skipif - SHOULD BE CAUGHT"""
import pytest
import sys


@pytest.mark.skipif(sys.platform == "win32", reason="Windows not supported")
def test_something():
    assert True
