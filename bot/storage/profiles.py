import json
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

PROFILES_FILE = DATA_DIR / "profiles.json"


def _load_profiles() -> dict:
    if not PROFILES_FILE.exists():
        return {}

    with open(PROFILES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_profiles(profiles: dict) -> None:
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)


def get_profile(user_id: int) -> dict | None:
    profiles = _load_profiles()
    return profiles.get(str(user_id))


def save_profile(user_id: int, nickname: str, race: str, player_class: str) -> None:
    profiles = _load_profiles()
    profiles[str(user_id)] = {
        "nickname": nickname,
        "race": race,
        "class": player_class,
    }
    _save_profiles(profiles)


def profile_exists(user_id: int) -> bool:
    return get_profile(user_id) is not None