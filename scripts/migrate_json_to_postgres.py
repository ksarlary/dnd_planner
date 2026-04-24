import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from bot.storage.db import init_db
from bot.storage.planning import set_planning_deadline
from bot.storage.profiles import save_profile


DATA_DIR = Path("data")
PROFILES_FILE = DATA_DIR / "profiles.json"
PLANNING_FILE = DATA_DIR / "planning.json"


def migrate_profiles() -> int:
    if not PROFILES_FILE.exists():
        return 0

    with open(PROFILES_FILE, "r", encoding="utf-8") as f:
        profiles = json.load(f)

    for user_id, profile in profiles.items():
        save_profile(
            user_id=int(user_id),
            nickname=profile["nickname"],
            race=profile["race"],
            player_class=profile["class"],
        )

    return len(profiles)


def migrate_planning() -> bool:
    if not PLANNING_FILE.exists():
        return False

    with open(PLANNING_FILE, "r", encoding="utf-8") as f:
        planning = json.load(f)

    deadline = planning.get("deadline")
    if not deadline:
        return False

    set_planning_deadline(datetime.fromisoformat(deadline))
    return True


def main() -> None:
    load_dotenv()
    init_db()

    profile_count = migrate_profiles()
    planning_migrated = migrate_planning()

    print(f"Migrated {profile_count} profiles.")
    print(f"Migrated planning deadline: {planning_migrated}.")


if __name__ == "__main__":
    main()
