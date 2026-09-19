def slugify(title: str) -> str:
    lowered = title.strip().lower()
    return "".join(each_character if each_character.isalnum() else "-" for each_character in lowered)
