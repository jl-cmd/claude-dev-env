# catalog

`catalog.paging.paginate(items, page, size)` returns the items on a 1-based
page. `page_count(total, size)` returns how many pages exist. A final page
that is only partly full still counts and still returns its items.
