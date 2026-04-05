"""Test file with @Skip (capital S) - EDGE CASE: might slip through"""
import unittest
from unittest import skip as Skip


@Skip
def test_something():
    assert True
