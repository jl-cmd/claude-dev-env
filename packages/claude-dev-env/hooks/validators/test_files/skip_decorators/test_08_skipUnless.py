"""Test file with @unittest.skipUnless - SHOULD BE CAUGHT"""
import unittest


@unittest.skipUnless(False, "Reason")
def test_something():
    assert True
