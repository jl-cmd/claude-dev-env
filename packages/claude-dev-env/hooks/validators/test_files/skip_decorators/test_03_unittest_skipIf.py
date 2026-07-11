"""Test file with @unittest.skipIf - SHOULD BE CAUGHT"""
import unittest


class TestCase(unittest.TestCase):
    @unittest.skipIf(True, "Reason")
    def test_something(self):
        self.assertTrue(True)
