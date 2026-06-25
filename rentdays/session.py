import json
from dataclasses import asdict, dataclass
from typing import Optional

from rentdays.config import SESSION_FILE
from rentdays.msk_time import now_msk
from rentdays.sheets import fetch_rent_rows, find_rent_for_project, is_rent_active
from rentdays.storage import Project, Settings, ensure_data_dir


@dataclass
class SessionState:
    last_running_ids: list[str]
    saved_at: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        return cls(
            last_running_ids=list(data.get("last_running_ids", [])),
            saved_at=data.get("saved_at", ""),
        )


def load_session() -> Optional[SessionState]:
    ensure_data_dir()
    if not SESSION_FILE.exists():
        return None
    with SESSION_FILE.open(encoding="utf-8") as f:
        raw = json.load(f)
    if not raw.get("last_running_ids"):
        return None
    return SessionState.from_dict(raw)


def save_session(running_ids: list[str]) -> None:
    ensure_data_dir()
    state = SessionState(
        last_running_ids=running_ids,
        saved_at=now_msk().isoformat(timespec="seconds"),
    )
    with SESSION_FILE.open("w", encoding="utf-8") as f:
        json.dump(asdict(state), f, ensure_ascii=False, indent=2)


def _rent_allows_start(
    project: Project,
    rows,
    sheet_error: str,
) -> tuple[bool, str]:
    if not project.rent_enabled:
        return True, ""

    if sheet_error:
        return False, sheet_error

    row = find_rent_for_project(project.name, rows)
    if row is None:
        return False, f"«{project.name}» не найден в таблице"

    if not is_rent_active(row.expiry):
        return False, f"аренда истекла ({row.expiry.strftime('%d.%m.%Y')})"
    return True, ""


def projects_to_restore(
    projects: list[Project],
    settings: Settings,
    session: Optional[SessionState],
) -> tuple[list[Project], str]:
    """Returns (projects to start, mode description)."""
    if not settings.restore_projects_on_start:
        return [], "восстановление отключено"

    if session and session.last_running_ids:
        id_set = set(session.last_running_ids)
        candidates = [p for p in projects if p.id in id_set]
        mode = f"сессия ({len(candidates)} из {len(session.last_running_ids)})"
    else:
        candidates = list(projects)
        mode = "авто (без сохранённой сессии)"

    try:
        rows = fetch_rent_rows(settings.spreadsheet_id, settings.sheet_gid)
        sheet_error = ""
    except Exception as exc:
        rows = []
        sheet_error = str(exc)

    result: list[Project] = []
    for project in candidates:
        ok, _reason = _rent_allows_start(project, rows, sheet_error)
        if ok:
            result.append(project)

    return result, mode
