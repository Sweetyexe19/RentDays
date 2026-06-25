import threading
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional

from rentdays.sheets import RentRow, fetch_rent_rows, find_rent_for_project, is_rent_active
from rentdays.storage import Settings


@dataclass
class RentInfo:
    active: Optional[bool] = None
    expiry: Optional[date] = None
    username: str = ""
    error: str = ""
    loading: bool = True


@dataclass
class RentCache:
    _rows: list[RentRow] = field(default_factory=list)
    _error: str = ""
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _loading: bool = False
    _updated_at: float = 0.0

    def get(self, project_name: str, rent_enabled: bool) -> RentInfo:
        if not rent_enabled:
            return RentInfo(loading=False)

        with self._lock:
            if self._loading:
                return RentInfo(loading=True)
            if self._error:
                return RentInfo(error=self._error, loading=False)

            row = find_rent_for_project(project_name, self._rows)
            if row is None:
                return RentInfo(
                    error=f"«{project_name}» не найден в таблице",
                    loading=False,
                )
            active = is_rent_active(row.expiry)
            return RentInfo(
                active=active,
                expiry=row.expiry,
                username=row.username,
                loading=False,
            )

    def refresh_async(
        self,
        settings: Settings,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        def work() -> None:
            self._fetch(settings)
            if on_done:
                on_done()

        threading.Thread(target=work, daemon=True).start()

    def refresh_sync(self, settings: Settings) -> None:
        self._fetch(settings)

    def _fetch(self, settings: Settings) -> None:
        with self._lock:
            self._loading = True
        try:
            rows = fetch_rent_rows(settings.spreadsheet_id, settings.sheet_gid)
            err = ""
        except Exception as exc:
            rows = []
            err = str(exc)
        with self._lock:
            self._rows = rows
            self._error = err
            self._loading = False
            self._updated_at = time.time()
