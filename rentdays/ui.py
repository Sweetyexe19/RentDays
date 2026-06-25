import customtkinter as ctk
import threading
import uuid
from tkinter import filedialog, messagebox
from typing import Callable, Optional

from rentdays.clipboard import enable_clipboard
from rentdays.modal import close_modal, configure_modal, focus_dialog, release_modal_grab, restore_pair, show_message
from rentdays.autostart import set_autostart
from rentdays.commands import command_preview
from rentdays.config import APP_NAME, APP_VERSION
from rentdays.msk_time import format_msk_datetime, format_msk_short, format_msk_time, now_msk
from rentdays.process_manager import ProcessManager, ProcessState
from rentdays.rent_cache import RentCache, RentInfo
from rentdays.rent_checker import RentChecker
from rentdays.session import load_session, projects_to_restore, save_session
from rentdays.storage import Project, Settings, load_projects, load_settings, save_projects, save_settings
from rentdays.theme import COLORS, RADIUS, ctk_font, status_colors

C = COLORS
R = RADIUS

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


def _font(key: str, **kw) -> ctk.CTkFont:
    return ctk.CTkFont(**ctk_font(key, **kw))


def _btn_primary(master, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(
        master,
        fg_color=C["accent"],
        hover_color=C["accent_hover"],
        text_color=C["accent_text"],
        font=_font("body_bold"),
        corner_radius=R["md"],
        **kw,
    )


def _btn_ghost(master, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(
        master,
        fg_color=C["surface_2"],
        hover_color=C["surface_hover"],
        border_width=1,
        border_color=C["border"],
        text_color=C["text_secondary"],
        font=_font("body"),
        corner_radius=R["md"],
        **kw,
    )


def _btn_danger(master, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(
        master,
        fg_color=C["danger_dim"],
        hover_color=C["danger"],
        text_color=C["danger"],
        font=_font("body"),
        corner_radius=R["md"],
        **kw,
    )


class AddProjectDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        on_save: Callable[[Project], None],
        project: Optional[Project] = None,
    ):
        super().__init__(master)
        self.on_save = on_save
        self.project = project
        self.title("Проект")
        self.geometry("540x660")
        self.resizable(False, False)
        self.configure(fg_color=C["bg"])
        self._master = master
        configure_modal(self, master)
        self.grid_columnconfigure(0, weight=1)

        pad = {"padx": 32, "sticky": "ew"}

        ctk.CTkLabel(
            self,
            text="Редактирование" if project else "Новый проект",
            font=_font("title"),
            text_color=C["text"],
        ).grid(row=0, column=0, pady=(28, 4), **pad)

        ctk.CTkLabel(
            self,
            text="Название совпадает с колонкой в Google Sheets",
            font=_font("small"),
            text_color=C["text_muted"],
        ).grid(row=1, column=0, pady=(0, 20), **pad)

        self.name_entry = self._field("Название", 2)
        self._label("Команды CMD — по одной на строку", 4)
        self.cmd_box = ctk.CTkTextbox(
            self,
            height=150,
            fg_color=C["surface"],
            border_color=C["border"],
            border_width=1,
            text_color=C["text_secondary"],
            font=_font("mono"),
            corner_radius=R["md"],
            wrap="none",
        )
        self.cmd_box.grid(row=5, column=0, padx=32, pady=(0, 6), sticky="ew")

        ctk.CTkLabel(
            self,
            text="cd, pip install, activate, python — всё в одной сессии",
            font=_font("tiny"),
            text_color=C["text_dim"],
        ).grid(row=6, column=0, pady=(0, 12), **pad)

        self.dir_entry = self._field("Рабочая папка", 7)

        rent_row = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=R["md"])
        rent_row.grid(row=9, column=0, padx=32, pady=(8, 20), sticky="ew")

        inner = ctk.CTkFrame(rent_row, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(
            inner,
            text="Контроль аренды",
            font=_font("body_bold"),
            text_color=C["text"],
        ).pack(side="left")

        self.rent_switch = ctk.CTkSwitch(
            inner,
            text="",
            width=44,
            progress_color=C["accent"],
            button_color=C["border_light"],
            button_hover_color=C["text_muted"],
        )
        self.rent_switch.pack(side="right")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=10, column=0, padx=32, pady=(0, 28), sticky="ew")
        btns.grid_columnconfigure((0, 1), weight=1)

        _btn_ghost(btns, text="Отмена", height=44, command=self._close).grid(
            row=0, column=0, padx=(0, 6), sticky="ew"
        )
        _btn_primary(btns, text="Сохранить", height=44, command=self._save).grid(
            row=0, column=1, padx=(6, 0), sticky="ew"
        )

        if project:
            self.name_entry.insert(0, project.name)
            self.cmd_box.insert("1.0", project.command)
            self.dir_entry.insert(0, project.work_dir)
            if project.rent_enabled:
                self.rent_switch.select()
        else:
            self.cmd_box.insert(
                "1.0",
                "cd C:\\Projects\\mybot\n"
                "venv\\Scripts\\activate\n"
                "pip install -r requirements.txt\n"
                "python main.py",
            )

        _btn_ghost(self, text="Обзор", width=72, height=30, command=self._browse_dir).place(
            x=430, y=392
        )

        enable_clipboard(self.name_entry)
        enable_clipboard(self.dir_entry)
        enable_clipboard(self.cmd_box)

        self.after(50, lambda: focus_dialog(self))

    def _label(self, text: str, row: int) -> None:
        ctk.CTkLabel(
            self, text=text, font=_font("small"), text_color=C["text_muted"]
        ).grid(row=row, column=0, padx=32, pady=(0, 4), sticky="w")

    def _field(self, label: str, row: int) -> ctk.CTkEntry:
        self._label(label, row)
        entry = ctk.CTkEntry(
            self,
            height=42,
            fg_color=C["surface"],
            border_color=C["border"],
            text_color=C["text"],
            font=_font("body"),
            corner_radius=R["md"],
        )
        entry.grid(row=row + 1, column=0, padx=32, pady=(0, 14), sticky="ew")
        return entry

    def _close(self) -> None:
        close_modal(self)

    def _browse_dir(self) -> None:
        with release_modal_grab(self):
            path = filedialog.askdirectory(parent=self._master)
        if path:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, path)

    def _save(self) -> None:
        name = self.name_entry.get().strip()
        command = self.cmd_box.get("1.0", "end").strip()
        work_dir = self.dir_entry.get().strip()
        if not name:
            show_message(self._master, messagebox.showwarning, "Ошибка", "Укажите название", parent=self)
            return
        if not command:
            show_message(self._master, messagebox.showwarning, "Ошибка", "Укажите команды", parent=self)
            return
        self.on_save(
            Project(
                id=self.project.id if self.project else str(uuid.uuid4()),
                name=name,
                command=command,
                work_dir=work_dir,
                rent_enabled=bool(self.rent_switch.get()),
            )
        )
        self._close()


def _icon_btn(master, text: str, command, danger: bool = False, **kw) -> ctk.CTkButton:
    return ctk.CTkButton(
        master,
        text=text,
        width=kw.pop("width", 28),
        height=kw.pop("height", 28),
        font=ctk.CTkFont(size=13),
        fg_color=C["surface"] if not danger else C["danger_dim"],
        hover_color=C["surface_hover"] if not danger else C["danger"],
        text_color=C["text_secondary"] if not danger else C["danger"],
        corner_radius=R["sm"],
        command=command,
        **kw,
    )


class ProjectSection(ctk.CTkFrame):
    """Секция-папка: Аренда / Без аренды."""

    def __init__(self, master, title: str, count: int, accent: str, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.expanded = True
        self.grid_columnconfigure(0, weight=1)

        self.header = ctk.CTkFrame(
            self, fg_color=C["surface_2"], corner_radius=R["md"], height=36
        )
        self.header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.header.grid_propagate(False)
        self.header.bind("<Button-1>", lambda _e: self._toggle())

        self.chevron = ctk.CTkLabel(
            self.header,
            text="▾",
            font=ctk.CTkFont(size=13),
            text_color=C["text_muted"],
            width=24,
        )
        self.chevron.pack(side="left", padx=(10, 4))
        self.chevron.bind("<Button-1>", lambda _e: self._toggle())

        ctk.CTkLabel(
            self.header,
            text=title,
            font=_font("body_bold"),
            text_color=accent,
        ).pack(side="left")

        ctk.CTkLabel(
            self.header,
            text=str(count),
            font=_font("tiny"),
            text_color=C["text_dim"],
            fg_color=C["surface"],
            corner_radius=R["sm"],
            width=28,
            height=20,
        ).pack(side="left", padx=(8, 0))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="ew")
        self.body.grid_columnconfigure(0, weight=1)

    def _toggle(self) -> None:
        self.expanded = not self.expanded
        if self.expanded:
            self.body.grid()
            self.chevron.configure(text="▾")
        else:
            self.body.grid_remove()
            self.chevron.configure(text="▸")


class ProjectCard(ctk.CTkFrame):
    ROW_H = 36

    def __init__(
        self,
        master,
        project: Project,
        process_manager: ProcessManager,
        rent_cache: RentCache,
        on_edit: Callable[[Project], None],
        on_delete: Callable[[Project], None],
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color=C["surface_2"],
            corner_radius=R["md"],
            height=self.ROW_H,
            **kwargs,
        )
        self.project = project
        self.process_manager = process_manager
        self.rent_cache = rent_cache
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.expanded = False
        self._busy = False
        self.grid_propagate(False)

        # ── Тонкая строка (как папка) ──
        self.row = ctk.CTkFrame(self, fg_color="transparent", height=self.ROW_H)
        self.row.pack(fill="x", side="top")
        self.row.pack_propagate(False)

        self.stripe = ctk.CTkFrame(self.row, width=3, corner_radius=0, fg_color=C["text_dim"])
        self.stripe.pack(side="left", fill="y")

        self.expand_btn = ctk.CTkButton(
            self.row,
            text="▸",
            width=22,
            height=22,
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=C["surface_hover"],
            text_color=C["text_muted"],
            command=self._toggle,
        )
        self.expand_btn.pack(side="left", padx=(4, 2))

        self.name_label = ctk.CTkLabel(
            self.row,
            text=project.name,
            font=_font("body_bold"),
            text_color=C["text"],
            anchor="w",
        )
        self.name_label.pack(side="left", padx=(2, 6))
        self.name_label.bind("<Button-1>", lambda _e: self._toggle())

        self.meta_label = ctk.CTkLabel(
            self.row,
            text="",
            font=_font("tiny"),
            text_color=C["text_muted"],
            anchor="w",
        )
        self.meta_label.pack(side="left")

        actions = ctk.CTkFrame(self.row, fg_color="transparent")
        actions.pack(side="right", padx=(4, 6))

        self.btn_start = _icon_btn(actions, "▶", self._start)
        self.btn_start.pack(side="left", padx=1)
        self.btn_stop = _icon_btn(actions, "■", self._stop)
        self.btn_stop.pack(side="left", padx=1)
        self.btn_restart = _icon_btn(actions, "↻", self._restart)
        self.btn_restart.pack(side="left", padx=1)
        _icon_btn(actions, "✎", lambda: self.on_edit(project)).pack(side="left", padx=1)
        _icon_btn(actions, "✕", self._delete, danger=True).pack(side="left", padx=1)

        # ── Детали при раскрытии ──
        self.details = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=R["sm"])

        self.status_label = ctk.CTkLabel(
            self.details, text="", font=_font("small"), anchor="w"
        )
        self.status_label.pack(anchor="w", padx=12, pady=(8, 2))

        self.cmd_label = ctk.CTkLabel(
            self.details,
            text=command_preview(project.command, max_lines=6),
            font=_font("mono_sm"),
            text_color=C["text_dim"],
            anchor="w",
            justify="left",
        )
        self.cmd_label.pack(anchor="w", padx=12, pady=(0, 4))

        rent_row = ctk.CTkFrame(self.details, fg_color="transparent")
        rent_row.pack(anchor="w", fill="x", padx=12, pady=(0, 8))

        self.rent_badge = ctk.CTkLabel(
            rent_row, text="", font=_font("tiny"), corner_radius=R["sm"], height=20, width=96
        )
        self.rent_badge.pack(side="left", padx=(0, 8))

        self.rent_detail = ctk.CTkLabel(
            rent_row, text="", font=_font("small"), text_color=C["text_muted"], anchor="w"
        )
        self.rent_detail.pack(side="left", fill="x", expand=True)

        self.refresh()

    def _toggle(self) -> None:
        self.expanded = not self.expanded
        if self.expanded:
            self.details.pack(fill="x", padx=6, pady=(0, 6), side="top")
            self.grid_propagate(True)
            self.expand_btn.configure(text="▾")
        else:
            self.details.pack_forget()
            self.configure(height=self.ROW_H)
            self.grid_propagate(False)
            self.expand_btn.configure(text="▸")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.btn_start.configure(state=state)
        self.btn_stop.configure(state=state)
        self.btn_restart.configure(state=state)

    def _on_action_done(self, ok: bool, msg: str) -> None:
        self._set_busy(False)
        self.refresh()
        if not ok and msg:
            top = self.winfo_toplevel()
            if hasattr(top, "_append_log"):
                top._append_log(f"{self.project.name}: {msg}")

    def _start(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        p = self.project
        self.process_manager.run_async(
            lambda: self.process_manager.start(p.id, p.command, p.work_dir),
            on_done=lambda ok, msg: self.after(0, lambda: self._on_action_done(ok, msg)),
        )

    def _stop(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        pid = self.project.id
        self.process_manager.run_async(
            lambda: self.process_manager.stop(pid, by_rent=False),
            on_done=lambda ok, msg: self.after(0, lambda: self._on_action_done(ok, msg)),
        )

    def _restart(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        p = self.project
        self.process_manager.run_async(
            lambda: self.process_manager.restart(p.id, p.command, p.work_dir),
            on_done=lambda ok, msg: self.after(0, lambda: self._on_action_done(ok, msg)),
        )

    def _delete(self) -> None:
        if show_message(
            self.winfo_toplevel(),
            messagebox.askyesno,
            "Удалить",
            f"Удалить «{self.project.name}»?",
            parent=self.winfo_toplevel(),
        ):
            pid = self.project.id
            if self.process_manager.is_running(pid):
                self.process_manager.run_async(
                    lambda: self.process_manager.stop(pid),
                    on_done=lambda _ok, _msg: self.after(0, lambda: self.on_delete(self.project)),
                )
            else:
                self.on_delete(self.project)

    def refresh(self) -> None:
        rt = self.process_manager.get_runtime(self.project.id)
        running = self.process_manager.is_running(self.project.id)
        err = rt.state == ProcessState.ERROR
        rent_stop = rt.stopped_by_rent

        stripe_c, _ = status_colors(running, err, rent_stop)
        self.stripe.configure(fg_color=stripe_c)

        if running:
            self.status_label.configure(
                text=f"Запущен  ·  PID {rt.pid or '?'}", text_color=C["success"]
            )
        elif err:
            self.status_label.configure(
                text=f"Ошибка  ·  {rt.last_error}", text_color=C["danger"]
            )
        elif rent_stop:
            self.status_label.configure(
                text="Остановлен  ·  истекла аренда", text_color=C["warning"]
            )
        else:
            self.status_label.configure(text="Остановлен", text_color=C["text_muted"])

        self._apply_rent(self.rent_cache.get(self.project.name, self.project.rent_enabled))

    def _set_rent_badge(self, text: str, fg: str, text_color: str) -> None:
        self.rent_badge.configure(text=text, fg_color=fg, text_color=text_color)

    def _apply_rent(self, info: RentInfo) -> None:
        if not self.project.rent_enabled:
            self._set_rent_badge("—", C["surface"], C["text_dim"])
            self.rent_detail.configure(text="аренда не отслеживается", text_color=C["text_dim"])
            self.meta_label.configure(text="", text_color=C["text_dim"])
            return

        if info.loading:
            self._set_rent_badge("…", C["surface_2"], C["text_muted"])
            self.rent_detail.configure(text="загрузка таблицы", text_color=C["text_muted"])
            self.meta_label.configure(text="", text_color=C["text_muted"])
            return

        if info.error:
            self._set_rent_badge("!", C["warning_dim"], C["warning"])
            self.rent_detail.configure(text=info.error, text_color=C["warning"])
            self.meta_label.configure(text="нет в таблице", text_color=C["warning"])
            return

        if info.expiry is None:
            self._set_rent_badge("!", C["warning_dim"], C["warning"])
            self.rent_detail.configure(text="дата не указана", text_color=C["warning"])
            self.meta_label.configure(text="нет даты", text_color=C["warning"])
            return

        date_str = info.expiry.strftime("%d.%m.%Y")
        client = f" · {info.username}" if info.username else ""

        if info.active:
            days = (info.expiry - now_msk().date()).days
            badge_fg = C["success_dim"] if days > 3 else C["warning_dim"]
            badge_txt = C["success"] if days > 3 else C["warning"]
            self._set_rent_badge("активна", badge_fg, badge_txt)
            left = "сегодня" if days == 0 else "1 дн." if days == 1 else f"{days} дн."
            detail = f"до {date_str}{client}  ·  {left}"
            self.rent_detail.configure(text=detail, text_color=badge_txt)
            short = f"до {date_str}"
            if info.username:
                short += f" · {info.username}"
            if len(short) > 32:
                short = short[:29] + "…"
            self.meta_label.configure(text=short, text_color=badge_txt)
        else:
            self._set_rent_badge("истекла", C["danger_dim"], C["danger"])
            detail = f"закончилась {date_str}{client}"
            self.rent_detail.configure(text=detail, text_color=C["danger"])
            self.meta_label.configure(text=f"истекла {date_str}", text_color=C["danger"])


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1180x740")
        self.minsize(960, 620)
        self.configure(fg_color=C["bg"])

        self.projects: list[Project] = load_projects()
        self.settings: Settings = load_settings()
        self.process_manager = ProcessManager()
        self.process_manager.set_on_change(self._on_process_change)
        self.rent_cache = RentCache()
        self.cards: dict[str, ProjectCard] = {}
        self._active_dialog: Optional[ctk.CTkToplevel] = None

        self._build_ui()

        self.rent_checker = RentChecker(
            process_manager=self.process_manager,
            get_projects=lambda: self.projects,
            get_settings=lambda: self.settings,
            on_log=self._append_log,
            on_check_done=lambda _: self.after(0, self._on_rent_check_done),
        )
        self.rent_checker.start()
        self._tick_clock()
        self.after(400, self._restore_projects_on_start)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Map>", self._on_main_restore, add="+")

    def _on_rent_check_done(self) -> None:
        self._refresh_rent_async()

    def _refresh_rent_async(self) -> None:
        self.rent_cache.refresh_async(
            self.settings,
            on_done=lambda: self.after(0, self._refresh_all_cards),
        )

    def _on_main_restore(self, event=None) -> None:
        if event is not None and event.widget != self:
            return
        restore_pair(self)

    def _open_dialog(self, factory: Callable[[], ctk.CTkToplevel]) -> None:
        if self._active_dialog and self._active_dialog.winfo_exists():
            focus_dialog(self._active_dialog)
            return
        dialog = factory()
        self._active_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda _e: setattr(self, "_active_dialog", None),
            add="+",
        )

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar ──
        sidebar = ctk.CTkFrame(
            self, width=220, fg_color=C["bg_elevated"], corner_radius=0
        )
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text="RentDays",
            font=_font("logo"),
            text_color=C["accent"],
        ).pack(anchor="w", padx=24, pady=(28, 0))

        ctk.CTkLabel(
            sidebar,
            text=f"v{APP_VERSION}  ·  VPS panel",
            font=_font("tiny"),
            text_color=C["text_dim"],
        ).pack(anchor="w", padx=24, pady=(2, 28))

        self.stat_total = self._sidebar_stat(sidebar, "0", "проектов")
        self.stat_running = self._sidebar_stat(sidebar, "0", "запущено")
        self.stat_rent = self._sidebar_stat(sidebar, "0", "аренда")

        ctk.CTkFrame(sidebar, height=1, fg_color=C["border"]).pack(
            fill="x", padx=20, pady=20
        )

        _btn_primary(
            sidebar, text="+  Новый проект", height=42, command=self._add_project
        ).pack(fill="x", padx=20, pady=(0, 8))

        _btn_ghost(
            sidebar, text="Проверить аренду", height=38, command=self._check_rent_now
        ).pack(fill="x", padx=20, pady=(0, 8))

        _btn_ghost(sidebar, text="Настройки", height=38, command=self._open_settings).pack(
            fill="x", padx=20
        )

        self.msk_label = ctk.CTkLabel(
            sidebar,
            text="",
            font=_font("mono_sm"),
            text_color=C["text_dim"],
        )
        self.msk_label.pack(side="bottom", padx=20, pady=20)

        # ── Center: projects ──
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew", padx=(16, 8), pady=16)
        center.grid_rowconfigure(1, weight=1)
        center.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            center,
            text="Проекты",
            font=_font("heading"),
            text_color=C["text"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        self.scroll = ctk.CTkScrollableFrame(
            center,
            fg_color="transparent",
            scrollbar_button_color=C["border"],
            scrollbar_button_hover_color=C["accent_dim"],
        )
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

        # ── Right: log ──
        log_panel = ctk.CTkFrame(
            self,
            width=300,
            fg_color=C["bg_elevated"],
            corner_radius=R["xl"],
            border_width=1,
            border_color=C["border"],
        )
        log_panel.grid(row=0, column=2, sticky="nsew", padx=(8, 16), pady=16)
        log_panel.grid_propagate(False)
        log_panel.grid_rowconfigure(1, weight=1)
        log_panel.grid_columnconfigure(0, weight=1)

        log_head = ctk.CTkFrame(log_panel, fg_color="transparent")
        log_head.grid(row=0, column=0, padx=18, pady=(18, 10), sticky="ew")

        ctk.CTkLabel(
            log_head, text="Журнал", font=_font("body_bold"), text_color=C["text"]
        ).pack(side="left")

        self.check_label = ctk.CTkLabel(
            log_head, text="", font=_font("tiny"), text_color=C["text_dim"]
        )
        self.check_label.pack(side="right")

        self.log_box = ctk.CTkTextbox(
            log_panel,
            fg_color=C["surface"],
            text_color=C["text_muted"],
            font=_font("mono_sm"),
            corner_radius=R["md"],
            border_width=1,
            border_color=C["border"],
            wrap="word",
        )
        self.log_box.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="nsew")
        self.log_box.configure(state="disabled")

        self._rebuild_cards()
        self._append_log("панель запущена")

    def _sidebar_stat(self, parent, value: str, label: str) -> ctk.CTkLabel:
        box = ctk.CTkFrame(parent, fg_color=C["surface"], corner_radius=R["md"])
        box.pack(fill="x", padx=20, pady=(0, 8))

        val = ctk.CTkLabel(
            box, text=value, font=_font("stat", size=26), text_color=C["text"]
        )
        val.pack(anchor="w", padx=14, pady=(10, 0))

        ctk.CTkLabel(
            box, text=label, font=_font("tiny"), text_color=C["text_muted"]
        ).pack(anchor="w", padx=14, pady=(0, 10))

        return val

    def _rebuild_cards(self) -> None:
        for card in self.cards.values():
            card.destroy()
        self.cards.clear()

        for child in self.scroll.winfo_children():
            child.destroy()

        if not self.projects:
            ctk.CTkLabel(
                self.scroll,
                text="Пока пусто\n\nДобавьте первый проект\nкнопкой слева",
                font=_font("body"),
                text_color=C["text_dim"],
                justify="center",
            ).grid(row=0, column=0, pady=80)
            self._update_stats()
            return

        rent_projects = [p for p in self.projects if p.rent_enabled]
        own_projects = [p for p in self.projects if not p.rent_enabled]

        row = 0
        if rent_projects:
            section = ProjectSection(
                self.scroll,
                title="Аренда",
                count=len(rent_projects),
                accent=C["gold"],
            )
            section.grid(row=row, column=0, sticky="ew", pady=(0, 10))
            row += 1
            self._place_cards_in_section(section.body, rent_projects)

        if own_projects:
            section = ProjectSection(
                self.scroll,
                title="Без аренды",
                count=len(own_projects),
                accent=C["accent"],
            )
            section.grid(row=row, column=0, sticky="ew", pady=(0, 10))
            self._place_cards_in_section(section.body, own_projects)

        self._update_stats()
        if self.projects:
            self._refresh_rent_async()

    def _place_cards_in_section(
        self, parent: ctk.CTkFrame, projects: list[Project]
    ) -> None:
        for i, project in enumerate(projects):
            card = ProjectCard(
                parent,
                project=project,
                process_manager=self.process_manager,
                rent_cache=self.rent_cache,
                on_edit=self._edit_project,
                on_delete=self._delete_project,
            )
            card.grid(row=i, column=0, padx=0, pady=2, sticky="ew")
            self.cards[project.id] = card

    def _update_stats(self) -> None:
        running = sum(1 for p in self.projects if self.process_manager.is_running(p.id))
        self.stat_total.configure(text=str(len(self.projects)))
        self.stat_running.configure(text=str(running))
        self.stat_rent.configure(text=str(sum(1 for p in self.projects if p.rent_enabled)))

    def _refresh_all_cards(self) -> None:
        for card in self.cards.values():
            card.refresh()
        self._update_stats()

    def _on_process_change(self, project_id: str) -> None:
        self._save_session_state()
        self.after(0, self._refresh_all_cards)

    def _running_project_ids(self) -> list[str]:
        return [p.id for p in self.projects if self.process_manager.is_running(p.id)]

    def _save_session_state(self) -> None:
        save_session(self._running_project_ids())

    def _restore_projects_on_start(self) -> None:
        if not self.settings.restore_projects_on_start:
            return

        def run():
            session = load_session()
            to_start, mode = projects_to_restore(self.projects, self.settings, session)
            if not to_start:
                self._append_log("восстановление: нечего запускать")
                return
            self._append_log(f"восстановление ({mode}): {len(to_start)}")
            for project in to_start:
                ok, msg = self.process_manager.start(
                    project.id, project.command, project.work_dir
                )
                self._append_log(f"  {project.name}: {'ok' if ok else msg}")
            self._save_session_state()
            self.after(0, self._refresh_all_cards)
            self.after(0, self._refresh_rent_async)

        threading.Thread(target=run, daemon=True).start()

    def _add_project(self) -> None:
        self._open_dialog(
            lambda: AddProjectDialog(self, on_save=self._save_project)
        )

    def _edit_project(self, project: Project) -> None:
        self._open_dialog(
            lambda: AddProjectDialog(self, on_save=self._save_project, project=project)
        )

    def _save_project(self, project: Project) -> None:
        idx = next((i for i, p in enumerate(self.projects) if p.id == project.id), None)
        if idx is not None:
            self.projects[idx] = project
            self._append_log(f"обновлён: {project.name}")
        else:
            self.projects.append(project)
            self._append_log(f"добавлен: {project.name}")
        save_projects(self.projects)
        self._rebuild_cards()

    def _delete_project(self, project: Project) -> None:
        self.projects = [p for p in self.projects if p.id != project.id]
        save_projects(self.projects)
        self._append_log(f"удалён: {project.name}")
        self._rebuild_cards()

    def _check_rent_now(self) -> None:
        self._append_log("проверка аренды...")

        def run():
            self.rent_checker.check_now()
            self.rent_cache.refresh_sync(self.settings)
            self.after(0, self._refresh_all_cards)

        threading.Thread(target=run, daemon=True).start()

    def _open_settings(self) -> None:
        if self._active_dialog and self._active_dialog.winfo_exists():
            focus_dialog(self._active_dialog)
            return

        dialog = ctk.CTkToplevel(self)
        self._active_dialog = dialog
        dialog.bind(
            "<Destroy>",
            lambda _e: setattr(self, "_active_dialog", None),
            add="+",
        )
        dialog.title("Настройки")
        dialog.geometry("500x560")
        dialog.resizable(False, False)
        dialog.configure(fg_color=C["bg"])
        configure_modal(dialog, self)
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        def section(title: str, row: int) -> None:
            ctk.CTkLabel(
                scroll,
                text=title,
                font=_font("heading"),
                text_color=C["text"],
            ).grid(row=row, column=0, sticky="w", pady=(18 if row else 4, 10))

        def flabel(text: str, row: int) -> None:
            ctk.CTkLabel(
                scroll, text=text, font=_font("small"), text_color=C["text_muted"]
            ).grid(row=row, column=0, sticky="w", pady=(0, 4))

        section("Панель", 0)
        autostart_var = ctk.BooleanVar(value=self.settings.autostart_windows)
        restore_var = ctk.BooleanVar(value=self.settings.restore_projects_on_start)
        stop_exit_var = ctk.BooleanVar(value=self.settings.stop_projects_on_exit)

        for i, (text, var) in enumerate(
            [
                ("Автозапуск при старте Windows", autostart_var),
                ("Восстанавливать проекты при открытии", restore_var),
                ("Останавливать проекты при закрытии", stop_exit_var),
            ],
            start=1,
        ):
            ctk.CTkSwitch(
                scroll,
                text=text,
                variable=var,
                font=_font("body"),
                progress_color=C["accent"],
                button_color=C["border_light"],
            ).grid(row=i, column=0, sticky="w", pady=6)

        section("Google Sheets", 4)
        flabel("ID таблицы", 5)
        sheet_entry = ctk.CTkEntry(scroll, height=40, fg_color=C["surface"], border_color=C["border"])
        sheet_entry.grid(row=6, column=0, sticky="ew", pady=(0, 10))
        sheet_entry.insert(0, self.settings.spreadsheet_id)

        flabel("Интервал проверки, сек", 7)
        interval_entry = ctk.CTkEntry(scroll, height=40, fg_color=C["surface"], border_color=C["border"])
        interval_entry.grid(row=8, column=0, sticky="ew")
        interval_entry.insert(0, str(self.settings.rent_check_interval_sec))

        enable_clipboard(sheet_entry)
        enable_clipboard(interval_entry)

        btns = ctk.CTkFrame(dialog, fg_color="transparent")
        btns.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        btns.grid_columnconfigure((0, 1), weight=1)

        def save():
            try:
                self.settings.rent_check_interval_sec = int(interval_entry.get().strip())
            except ValueError:
                show_message(
                    self, messagebox.showwarning, "Ошибка", "Интервал — число", parent=dialog
                )
                return
            self.settings.spreadsheet_id = sheet_entry.get().strip()
            self.settings.autostart_windows = bool(autostart_var.get())
            self.settings.restore_projects_on_start = bool(restore_var.get())
            self.settings.stop_projects_on_exit = bool(stop_exit_var.get())
            ok, err = set_autostart(self.settings.autostart_windows)
            if not ok:
                show_message(self, messagebox.showerror, "Автозапуск", err, parent=dialog)
                return
            save_settings(self.settings)
            self._append_log("настройки сохранены")
            close_modal(dialog)

        _btn_ghost(btns, text="Отмена", height=42, command=lambda: close_modal(dialog)).grid(
            row=0, column=0, padx=(0, 6), sticky="ew"
        )
        _btn_primary(btns, text="Сохранить", height=42, command=save).grid(
            row=0, column=1, padx=(6, 0), sticky="ew"
        )

        dialog.after(50, lambda: focus_dialog(dialog))

    def _append_log(self, message: str) -> None:
        ts = format_msk_time()

        def update():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", f"{ts}  {message}\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, update)

    def _tick_clock(self) -> None:
        self.msk_label.configure(text=format_msk_datetime())
        last = self.rent_checker.last_check
        self.check_label.configure(
            text=f"проверка {format_msk_short(last)}" if last else ""
        )
        self.after(1000, self._tick_clock)

    def _on_close(self) -> None:
        self._save_session_state()

        if self._active_dialog and self._active_dialog.winfo_exists():
            close_modal(self._active_dialog)

        if self.settings.stop_projects_on_exit:
            if not show_message(
                self, messagebox.askyesno,
                "Выход", "Остановить проекты и закрыть панель?", parent=self,
            ):
                return
            self.rent_checker.stop()
            self.process_manager.stop_all()
        else:
            if not show_message(
                self, messagebox.askyesno,
                "Выход", "Закрыть панель? Проекты останутся в фоне.", parent=self,
            ):
                return
            self.rent_checker.stop()
        self.destroy()


def run_app() -> None:
    app = MainWindow()
    app.mainloop()
