def export_rows(all_rows: list[dict[str, str]]) -> str:
    return "
".join(",".join(each_row.values()) for each_row in all_rows)
