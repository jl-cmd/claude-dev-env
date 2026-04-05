"""Test file with async functions to verify AsyncFunctionDef support."""

import asyncio


def dummy_decorator(func):
    """Simple decorator for testing."""
    return func


async def async_func_with_decorator_spacing():
    """Async function - should pass."""
    await asyncio.sleep(0)


@dummy_decorator
async def async_func_with_empty_line_after_decorator():
    """Should fail - empty line after decorator."""
    await asyncio.sleep(0)


async def async_func_one():
    """First async function."""
    await asyncio.sleep(0)


async def async_func_two():
    """Second async function - should pass with single empty line."""
    await asyncio.sleep(0)


async def async_func_three():
    """Third async function - should pass."""
    await asyncio.sleep(0)



async def async_func_four():
    """Fourth async function - should fail with multiple empty lines."""
    await asyncio.sleep(0)


def regular_func():
    """Regular function between async functions."""
    pass
