def render_thumbnail(image_bytes: bytes) -> bytes:
    return image_bytes[:1024]
