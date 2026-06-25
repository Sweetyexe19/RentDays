"""Visual theme — warm dark control-panel aesthetic."""

COLORS = {
    "bg": "#09090b",
    "bg_elevated": "#111113",
    "surface": "#18181b",
    "surface_2": "#1f1f23",
    "surface_hover": "#27272a",
    "border": "#2e2e33",
    "border_light": "#3f3f46",
    "accent": "#2dd4bf",
    "accent_dim": "#134e4a",
    "accent_hover": "#5eead4",
    "accent_text": "#042f2e",
    "gold": "#d4a574",
    "gold_dim": "#2a2218",
    "success": "#4ade80",
    "success_dim": "#14532d",
    "danger": "#f87171",
    "danger_dim": "#450a0a",
    "warning": "#fbbf24",
    "warning_dim": "#422006",
    "text": "#fafafa",
    "text_secondary": "#d4d4d8",
    "text_muted": "#71717a",
    "text_dim": "#52525b",
}

FONTS = {
    "title": ("Segoe UI", 22, "bold"),
    "heading": ("Segoe UI", 15, "bold"),
    "body": ("Segoe UI", 13),
    "body_bold": ("Segoe UI", 13, "bold"),
    "small": ("Segoe UI", 11),
    "tiny": ("Segoe UI", 10),
    "mono": ("Cascadia Mono", 11),
    "mono_sm": ("Cascadia Mono", 10),
    "stat": ("Segoe UI", 32, "bold"),
    "logo": ("Segoe UI", 20, "bold"),
}

RADIUS = {
    "sm": 6,
    "md": 10,
    "lg": 14,
    "xl": 18,
}


def ctk_font(key: str, size: int | None = None) -> dict:
    family, font_size, *weight = FONTS[key]
    w = weight[0] if weight else "normal"
    return {"family": family, "size": size or font_size, "weight": w}


def status_colors(running: bool, error: bool = False, rent_stop: bool = False) -> tuple[str, str]:
    if error:
        return COLORS["danger"], COLORS["danger_dim"]
    if rent_stop:
        return COLORS["warning"], COLORS["warning_dim"]
    if running:
        return COLORS["success"], COLORS["success_dim"]
    return COLORS["text_dim"], COLORS["surface_2"]
