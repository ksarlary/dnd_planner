import random
from pathlib import Path


EVENT_COVERS_DIR = Path("assets/event_covers")
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def get_random_event_cover_paths(count: int) -> list[Path]:
    if not EVENT_COVERS_DIR.exists():
        return []

    image_paths = [
        path
        for path in EVENT_COVERS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    if not image_paths:
        return []

    if count <= len(image_paths):
        return random.sample(image_paths, count)

    random.shuffle(image_paths)
    return image_paths + [
        random.choice(image_paths)
        for index in range(count - len(image_paths))
    ]


def read_event_cover(path: Path | None) -> bytes | None:
    if path is None:
        return None

    return path.read_bytes()
