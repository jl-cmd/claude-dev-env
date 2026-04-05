"""Test file with simple @skip decorator - SHOULD BE CAUGHT"""
import pytest
from unittest import skip


@skip
def test_something():
    assert True
