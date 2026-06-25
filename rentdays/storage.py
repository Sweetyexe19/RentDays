import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from rentdays.config import DATA_DIR, PROJECTS_FILE, SETTINGS_FILE, DEFAULT_SPREADSHEET_ID


@dataclass
class Project:
    id: str
    name: str
    command: str
    work_dir: str = ""
    rent_enabled: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        return cls(
            id=data["id"],
            name=data["name"],
            command=data["command"],
            work_dir=data.get("work_dir", ""),
            rent_enabled=bool(data.get("rent_enabled", False)),
        )


@dataclass
class Settings:
    spreadsheet_id: str = DEFAULT_SPREADSHEET_ID
    sheet_gid: str = "0"
    rent_check_interval_sec: int = 3600
    autostart_windows: bool = False
    restore_projects_on_start: bool = True
    stop_projects_on_exit: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        return cls(
            spreadsheet_id=data.get("spreadsheet_id", DEFAULT_SPREADSHEET_ID),
            sheet_gid=data.get("sheet_gid", "0"),
            rent_check_interval_sec=int(data.get("rent_check_interval_sec", 3600)),
            autostart_windows=bool(data.get("autostart_windows", False)),
            restore_projects_on_start=bool(data.get("restore_projects_on_start", True)),
            stop_projects_on_exit=bool(data.get("stop_projects_on_exit", True)),
        )


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_projects() -> list[Project]:
    ensure_data_dir()
    if not PROJECTS_FILE.exists():
        return []
    with PROJECTS_FILE.open(encoding="utf-8") as f:
        raw = json.load(f)
    return [Project.from_dict(item) for item in raw]


def save_projects(projects: list[Project]) -> None:
    ensure_data_dir()
    with PROJECTS_FILE.open("w", encoding="utf-8") as f:
        json.dump([asdict(p) for p in projects], f, ensure_ascii=False, indent=2)


def load_settings() -> Settings:
    ensure_data_dir()
    if not SETTINGS_FILE.exists():
        return Settings()
    with SETTINGS_FILE.open(encoding="utf-8") as f:
        return Settings.from_dict(json.load(f))


def save_settings(settings: Settings) -> None:
    ensure_data_dir()
    with SETTINGS_FILE.open("w", encoding="utf-8") as f:
        json.dump(asdict(settings), f, ensure_ascii=False, indent=2)
