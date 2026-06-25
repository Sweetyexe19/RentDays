import customtkinter as ctk
from contextlib import contextmanager
from typing import Callable, Optional


def close_modal(window: ctk.CTkToplevel) -> None:
    if window.winfo_exists():
        window.destroy()


def configure_modal(
    window: ctk.CTkToplevel,
    master: ctk.CTk,
    on_close: Optional[Callable[[], None]] = None,
) -> None:
    """Modal without grab_set — avoids freeze/minimize bugs on Windows."""
    window.transient(master)
    window.lift()
    window.focus_force()

    def do_close() -> None:
        if on_close:
            on_close()
        close_modal(window)

    window.protocol("WM_DELETE_WINDOW", do_close)

    def sync_windows() -> None:
        if not window.winfo_exists():
            return
        try:
            master_state = master.state()
            dialog_state = window.state()
            if master_state == "iconic" and dialog_state != "iconic":
                window.iconify()
            elif master_state == "normal" and dialog_state == "iconic":
                window.deiconify()
                window.lift()
        except Exception:
            pass

    def on_master_unmap(event) -> None:
        if event.widget == master:
            master.after(20, sync_windows)

    def on_master_map(event) -> None:
        if event.widget != master or not window.winfo_exists():
            return
        master.after(30, restore_pair)

    def on_dialog_unmap(event) -> None:
        if event.widget != window:
            return
        master.after(30, lambda: master.iconify() if _dialog_iconic(window) else None)

    def on_dialog_map(event) -> None:
        if event.widget == window:
            window.focus_force()

    master.bind("<Map>", on_master_map, add="+")
    master.bind("<Unmap>", on_master_unmap, add="+")
    window.bind("<Map>", on_dialog_map, add="+")
    window.bind("<Unmap>", on_dialog_unmap, add="+")


def _dialog_iconic(window: ctk.CTkToplevel) -> bool:
    try:
        return window.winfo_exists() and window.state() == "iconic"
    except Exception:
        return False


def restore_pair(master: ctk.CTk) -> None:
    for child in master.winfo_children():
        if not isinstance(child, ctk.CTkToplevel) or not child.winfo_exists():
            continue
        try:
            master.deiconify()
            child.deiconify()
            master.lift()
            child.lift()
            child.focus_force()
            return
        except Exception:
            continue


def release_all_grabs(root: ctk.CTk) -> None:
    for widget in [root, *root.winfo_children()]:
        try:
            widget.grab_release()
        except Exception:
            pass


def restore_active_dialog(root: ctk.CTk) -> None:
    restore_pair(root)


@contextmanager
def release_modal_grab(window: ctk.CTkToplevel):
    yield


def show_message(root: ctk.CTk, fn: Callable, *args, **kwargs):
    return fn(*args, **kwargs)


def focus_dialog(dialog: ctk.CTkToplevel) -> None:
    if not dialog.winfo_exists():
        return
    try:
        master = dialog.master
        if isinstance(master, ctk.CTk):
            restore_pair(master)
        else:
            if dialog.state() == "iconic":
                dialog.deiconify()
            dialog.lift()
            dialog.focus_force()
    except Exception:
        pass
