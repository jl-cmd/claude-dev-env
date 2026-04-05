"""Test file with async Django views to verify AsyncFunctionDef support."""

from django.http import HttpRequest, HttpResponse


async def async_home_view(request: HttpRequest) -> HttpResponse:
    """Async view with correct naming - should pass."""
    return HttpResponse("Home")


async def async_about(request: HttpRequest) -> HttpResponse:
    """Async view without _view suffix - should fail."""
    return HttpResponse("About")


async def async_helper(data: str) -> str:
    """Async function not a view - should be ignored."""
    return data.upper()


async def async_profile_view(request: HttpRequest) -> HttpResponse:
    """Another async view with correct naming - should pass."""
    return HttpResponse("Profile")
