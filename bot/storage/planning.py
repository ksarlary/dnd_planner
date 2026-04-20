import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

PLANNING_FILE = DATA_DIR / "planning.json"


def _load_data() -> dict:
    if not PLANNING_FILE.exists():
        return {}

    with open(PLANNING_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_data(data: dict) -> None:
    with open(PLANNING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def set_planning_deadline(deadline: datetime) -> None:
    data = _load_data()
    data["deadline"] = deadline.isoformat()
    _save_data(data)


def get_planning_deadline() -> datetime | None:
    data = _load_data()
    raw_deadline = data.get("deadline")

    if not raw_deadline:
        return None

    try:
        return datetime.fromisoformat(raw_deadline)
    except ValueError:
        return None


def is_planning_open(now: datetime | None = None) -> bool:
    deadline = get_planning_deadline()
    if deadline is None:
        return False

    now = now or datetime.now()
    return now <= deadline