import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from rentdays.msk_time import now_msk
from rentdays.process_manager import ProcessManager
from rentdays.sheets import (
    RentRow,
    fetch_rent_rows,
    find_rent_for_project,
    is_rent_active,
)
from rentdays.storage import Project, Settings


@dataclass
class RentCheckResult:
    project_id: str
    project_name: str
    action: str
    message: str
    expiry: Optional[str] = None


@dataclass
class RentChecker:
    process_manager: ProcessManager
    get_projects: Callable[[], list[Project]]
    get_settings: Callable[[], Settings]
    on_log: Callable[[str], None] = field(default=lambda _: None)
    on_check_done: Callable[[list[RentCheckResult]], None] = field(
        default=lambda _: None
    )

    _thread: Optional[threading.Thread] = None
    _stop_event: threading.Event = field(default_factory=threading.Event)
    _last_check: Optional[datetime] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.on_log("Мониторинг аренды запущен")

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def last_check(self) -> Optional[datetime]:
        return self._last_check

    def check_now(self) -> list[RentCheckResult]:
        return self._run_check()

    def _loop(self) -> None:
        self._run_check()
        while not self._stop_event.wait(self.get_settings().rent_check_interval_sec):
            self._run_check()

    def _run_check(self) -> list[RentCheckResult]:
        self._last_check = now_msk()
        settings = self.get_settings()
        projects = [p for p in self.get_projects() if p.rent_enabled]
        results: list[RentCheckResult] = []

        if not projects:
            self.on_check_done(results)
            return results

        self.on_log(f"Проверка аренды ({len(projects)} проектов)...")

        try:
            rows = fetch_rent_rows(settings.spreadsheet_id, settings.sheet_gid)
            sheet_error = ""
        except Exception as exc:
            rows = []
            sheet_error = str(exc)

        for project in projects:
            result = self._check_project(project, rows, sheet_error)
            if result:
                results.append(result)
                self.on_log(result.message)

        self.on_check_done(results)
        return results

    def _check_project(
        self,
        project: Project,
        rows: list[RentRow],
        sheet_error: str,
    ) -> Optional[RentCheckResult]:
        if sheet_error:
            return RentCheckResult(
                project_id=project.id,
                project_name=project.name,
                action="warn",
                message=f"{project.name}: {sheet_error}",
            )

        row = find_rent_for_project(project.name, rows)
        if row is None:
            return RentCheckResult(
                project_id=project.id,
                project_name=project.name,
                action="warn",
                message=f"{project.name}: «{project.name}» не найден в таблице",
            )

        active = is_rent_active(row.expiry)
        expiry = row.expiry
        username = row.username

        expiry_str = expiry.strftime("%d.%m.%Y") if expiry else "?"
        runtime = self.process_manager.get_runtime(project.id)
        running = self.process_manager.is_running(project.id)

        if active is False:
            if running:
                self.process_manager.stop(project.id, by_rent=True)
                return RentCheckResult(
                    project_id=project.id,
                    project_name=project.name,
                    action="stopped",
                    message=(
                        f"{project.name}: аренда истекла ({expiry_str}) — остановлен"
                    ),
                    expiry=expiry_str,
                )
            runtime.stopped_by_rent = True
            return RentCheckResult(
                project_id=project.id,
                project_name=project.name,
                action="expired",
                message=f"{project.name}: аренда истекла ({expiry_str})",
                expiry=expiry_str,
            )

        if active is True and runtime.stopped_by_rent and not running:
            ok, msg = self.process_manager.start(
                project.id,
                project.command,
                project.work_dir,
                clear_rent_flag=True,
            )
            if ok:
                runtime.stopped_by_rent = False
                user_part = f", {username}" if username else ""
                return RentCheckResult(
                    project_id=project.id,
                    project_name=project.name,
                    action="started",
                    message=(
                        f"{project.name}: продлено до {expiry_str}{user_part} — запущен"
                    ),
                    expiry=expiry_str,
                )
            return RentCheckResult(
                project_id=project.id,
                project_name=project.name,
                action="error",
                message=f"{project.name}: не запустился — {msg}",
                expiry=expiry_str,
            )

        if active is True and expiry:
            user_part = f" ({username})" if username else ""
            days_left = (expiry - now_msk().date()).days
            if days_left <= 3:
                return RentCheckResult(
                    project_id=project.id,
                    project_name=project.name,
                    action="warning",
                    message=(
                        f"{project.name}: до {expiry_str}{user_part} "
                        f"(осталось {days_left} дн.)"
                    ),
                    expiry=expiry_str,
                )

        return None
