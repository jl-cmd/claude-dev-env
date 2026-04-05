"""Test file with async functions and inline imports."""

import asyncio


async def async_func_with_inline_import():
    """Async function with inline import - should fail."""
    import json
    return json.dumps({"status": "ok"})


async def regular_async_func():
    """Regular async function - should pass."""
    await asyncio.sleep(0)
