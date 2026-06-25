import re
from pathlib import Path

ACTIVATE_RE = re.compile(
    r"^(?:call\s+)?(?P<path>.+\\Scripts\\activate(?:\.bat)?)\s*$",
    re.IGNORECASE,
)


def _normalize_line(line: str) -> str:
    line = line.strip()
    if not line:
        return ""

    match = ACTIVATE_RE.match(line)
    if match:
        path = match.group("path").strip().strip('"')
        return f'call "{path}"' if " " in path else f"call {path}"

    if line.lower().startswith("source "):
        # bash-style, convert to call for Windows venv
        path = line[7:].strip().strip('"')
        if path.endswith("/activate"):
            path = path.replace("/", "\\") + ".bat"
        return f'call "{path}"' if " " in path else f"call {path}"

    return line


def parse_command_lines(command: str) -> list[str]:
    lines: list[str] = []
    for raw in command.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("::"):
            continue
        lines.append(_normalize_line(stripped))
    return [line for line in lines if line]


def build_batch_content(command: str, work_dir: str = "") -> str:
    lines = ["@echo off", "setlocal EnableExtensions"]

    if work_dir.strip():
        path = work_dir.strip().strip('"')
        lines.append(f'cd /d "{path}"')

    cmd_lines = parse_command_lines(command)
    if not cmd_lines:
        raise ValueError("Нет команд для запуска")

    lines.extend(cmd_lines)
    return "\r\n".join(lines) + "\r\n"


def write_batch_file(
    scripts_dir: Path,
    project_id: str,
    command: str,
    work_dir: str = "",
) -> Path:
    scripts_dir.mkdir(parents=True, exist_ok=True)
    batch_path = scripts_dir / f"{project_id}.bat"
    batch_path.write_text(
        build_batch_content(command, work_dir),
        encoding="utf-8",
    )
    return batch_path


def command_preview(command: str, max_lines: int = 2) -> str:
    lines = parse_command_lines(command)
    if not lines:
        return "—"
    if len(lines) <= max_lines:
        sep = "\n" if max_lines > 2 else " → "
        return sep.join(lines)
    shown = lines[:max_lines]
    sep = "\n" if max_lines > 2 else " → "
    tail = f"\n… (+{len(lines) - max_lines})" if max_lines > 2 else f" → … (+{len(lines) - max_lines})"
    return sep.join(shown) + tail
