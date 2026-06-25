from pathlib import Path

APP_NAME = "RentDays"
APP_VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SCRIPTS_DIR = DATA_DIR / "scripts"
PROJECTS_FILE = DATA_DIR / "projects.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
SESSION_FILE = DATA_DIR / "session.json"

DEFAULT_SPREADSHEET_ID = "1SeNtHW-7KTXUO4uScKs2C3ZbtxmZgzdjMaE6nFddJg0"
DEFAULT_SHEET_GID = "0"
RENT_CHECK_INTERVAL_SEC = 3600

# Backward-compatible alias
from rentdays.theme import COLORS  # noqa: E402
