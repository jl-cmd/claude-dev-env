def page_count(total: int, size: int) -> int:
    if size <= 0:
        raise ValueError("size must be positive")
    return total // size


def paginate(items: list[str], page: int, size: int) -> list[str]:
    if page < 1 or page > page_count(len(items), size):
        return []
    start = (page - 1) * size
    return items[start : start + size]
