import subprocess
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

import psutil

from rentdays.commands import write_batch_file
from rentdays.config import SCRIPTS_DIR


class ProcessState(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    STARTING = "starting"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class RuntimeInfo:
    state: ProcessState = ProcessState.STOPPED
    pid: Optional[int] = None
    stopped_by_rent: bool = False
    last_error: str = ""


@dataclass
class ProcessManager:
    _processes: dict[str, subprocess.Popen] = field(default_factory=dict)
    _runtime: dict[str, RuntimeInfo] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _on_change: Optional[Callable[[str], None]] = None

    def set_on_change(self, callback: Callable[[str], None]) -> None:
        self._on_change = callback

    def _notify(self, project_id: str) -> None:
        if self._on_change:
            self._on_change(project_id)

    def get_runtime(self, project_id: str) -> RuntimeInfo:
        with self._lock:
            return self._runtime.setdefault(project_id, RuntimeInfo())

    def is_running(self, project_id: str) -> bool:
        with self._lock:
            proc = self._processes.get(project_id)
            if proc is None:
                return False
            if proc.poll() is not None:
                self._cleanup_project(project_id)
                return False
            return True

    def _cleanup_project(self, project_id: str) -> None:
        info = self._runtime.setdefault(project_id, RuntimeInfo())
        info.pid = None
        info.state = ProcessState.STOPPED
        self._processes.pop(project_id, None)

    def _kill_tree(self, pid: int) -> None:
        try:
            parent = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        try:
            parent.kill()
        except psutil.NoSuchProcess:
            pass

    def start(
        self,
        project_id: str,
        command: str,
        work_dir: str = "",
        clear_rent_flag: bool = True,
    ) -> tuple[bool, str]:
        with self._lock:
            if self.is_running(project_id):
                return False, "Проект уже запущен"

            info = self._runtime.setdefault(project_id, RuntimeInfo())
            info.state = ProcessState.STARTING
            info.last_error = ""
            if clear_rent_flag:
                info.stopped_by_rent = False

        try:
            cwd = Path(work_dir) if work_dir else None
            if cwd and not cwd.exists():
                raise FileNotFoundError(f"Рабочая папка не найдена: {work_dir}")

            batch_path = write_batch_file(
                SCRIPTS_DIR,
                project_id,
                command,
                work_dir,
            )

            proc = subprocess.Popen(
                ["cmd.exe", "/c", str(batch_path)],
                shell=False,
                cwd=str(cwd) if cwd else None,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        except Exception as exc:
            with self._lock:
                info = self._runtime.setdefault(project_id, RuntimeInfo())
                info.state = ProcessState.ERROR
                info.last_error = str(exc)
            self._notify(project_id)
            return False, str(exc)

        with self._lock:
            self._processes[project_id] = proc
            info = self._runtime.setdefault(project_id, RuntimeInfo())
            info.state = ProcessState.RUNNING
            info.pid = proc.pid

        self._notify(project_id)
        return True, "Запущен"

    def stop(self, project_id: str, by_rent: bool = False) -> tuple[bool, str]:
        with self._lock:
            proc = self._processes.get(project_id)
            info = self._runtime.setdefault(project_id, RuntimeInfo())
            if proc is None or proc.poll() is not None:
                self._cleanup_project(project_id)
                info.stopped_by_rent = by_rent
                self._notify(project_id)
                return True, "Уже остановлен"

            info.state = ProcessState.STOPPING
            pid = proc.pid

        self._kill_tree(pid)

        with self._lock:
            self._cleanup_project(project_id)
            info = self._runtime.setdefault(project_id, RuntimeInfo())
            info.stopped_by_rent = by_rent

        self._notify(project_id)
        return True, "Остановлен"

    def restart(
        self,
        project_id: str,
        command: str,
        work_dir: str = "",
    ) -> tuple[bool, str]:
        self.stop(project_id, by_rent=False)
        return self.start(project_id, command, work_dir, clear_rent_flag=True)

    def run_async(
        self,
        action: Callable[[], tuple[bool, str]],
        on_done: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        def work() -> None:
            try:
                ok, msg = action()
            except Exception as exc:
                ok, msg = False, str(exc)
            if on_done:
                on_done(ok, msg)

        threading.Thread(target=work, daemon=True).start()

    def stop_all(self) -> None:
        with self._lock:
            ids = list(self._processes.keys())
        for project_id in ids:
            self.stop(project_id)
