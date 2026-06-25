import tkinter as tk
from typing import Union

import customtkinter as ctk


def _tk_widget(widget: Union[ctk.CTkEntry, ctk.CTkTextbox]) -> tk.Widget:
    if isinstance(widget, ctk.CTkEntry):
        return widget._entry
    if isinstance(widget, ctk.CTkTextbox):
        return widget._textbox
    raise TypeError(f"Unsupported widget: {type(widget)}")


def _is_entry(widget: tk.Widget) -> bool:
    return isinstance(widget, tk.Entry)


def _select_all(widget: tk.Widget, entry: bool) -> None:
    if entry:
        widget.select_range(0, "end")
        widget.icursor("end")
    else:
        widget.tag_add("sel", "1.0", "end-1c")
    widget.focus_set()


def _copy(widget: tk.Widget, entry: bool) -> None:
    try:
        if entry:
            text = widget.selection_get()
        else:
            try:
                text = widget.get("sel.first", "sel.last")
            except tk.TclError:
                return
        widget.clipboard_clear()
        widget.clipboard_append(text)
    except tk.TclError:
        pass


def _cut(widget: tk.Widget, entry: bool) -> None:
    _copy(widget, entry)
    try:
        if entry:
            widget.delete("sel.first", "sel.last")
        else:
            widget.delete("sel.first", "sel.last")
    except tk.TclError:
        pass


def _paste(widget: tk.Widget, entry: bool) -> None:
    try:
        text = widget.clipboard_get()
    except tk.TclError:
        return
    try:
        if entry:
            try:
                widget.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
            widget.insert("insert", text)
        else:
            try:
                widget.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
            widget.insert("insert", text)
    except tk.TclError:
        pass


def enable_clipboard(widget: Union[ctk.CTkEntry, ctk.CTkTextbox]) -> None:
    inner = _tk_widget(widget)
    entry = _is_entry(inner)

    menu = tk.Menu(inner, tearoff=0)
    menu.add_command(label="Вырезать", command=lambda: _cut(inner, entry))
    menu.add_command(label="Копировать", command=lambda: _copy(inner, entry))
    menu.add_command(label="Вставить", command=lambda: _paste(inner, entry))
    menu.add_separator()
    menu.add_command(label="Выделить всё", command=lambda: _select_all(inner, entry))

    def show_menu(event: tk.Event) -> None:
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def bind_shortcut(sequence: str, handler) -> None:
        widget.bind(sequence, handler, add="+")
        inner.bind(sequence, handler, add="+")

    bind_shortcut("<Button-3>", show_menu)
    bind_shortcut("<Control-a>", lambda _e: (_select_all(inner, entry), "break")[-1])
    bind_shortcut("<Control-A>", lambda _e: (_select_all(inner, entry), "break")[-1])
    bind_shortcut("<Control-c>", lambda _e: (_copy(inner, entry), "break")[-1])
    bind_shortcut("<Control-C>", lambda _e: (_copy(inner, entry), "break")[-1])
    bind_shortcut("<Control-v>", lambda _e: (_paste(inner, entry), "break")[-1])
    bind_shortcut("<Control-V>", lambda _e: (_paste(inner, entry), "break")[-1])
    bind_shortcut("<Control-x>", lambda _e: (_cut(inner, entry), "break")[-1])
    bind_shortcut("<Control-X>", lambda _e: (_cut(inner, entry), "break")[-1])


def enable_clipboard_tree(root: tk.Misc) -> None:
    for child in root.winfo_children():
        if isinstance(child, ctk.CTkEntry):
            enable_clipboard(child)
        elif isinstance(child, ctk.CTkTextbox):
            enable_clipboard(child)
        enable_clipboard_tree(child)
