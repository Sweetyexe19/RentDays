import csv
import io
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional
from urllib.error import URLError
from urllib.request import urlopen

from rentdays.config import DEFAULT_SPREADSHEET_ID
from rentdays.msk_time import today_msk


@dataclass
class RentRow:
    project_name: str
    expiry: date
    username: str


def _csv_export_url(spreadsheet_id: str, gid: str) -> str:
    return (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export"
        f"?format=csv&gid={gid}"
    )


def parse_dd_mm(value: str, today: Optional[date] = None) -> Optional[date]:
    today = today or today_msk()
    value = value.strip()
    if not value:
        return None

    match = re.match(r"^(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?$", value)
    if not match:
        return None

    day, month = int(match.group(1)), int(match.group(2))
    year = int(match.group(3)) if match.group(3) else today.year

    try:
        expiry = date(year, month, day)
    except ValueError:
        return None

    if match.group(3) is None:
        if expiry < today - timedelta(days=30):
            try:
                expiry = date(year + 1, month, day)
            except ValueError:
                return None
        elif expiry > today + timedelta(days=335):
            try:
                expiry = date(year - 1, month, day)
            except ValueError:
                return None

    return expiry


def is_rent_active(expiry: date, today: Optional[date] = None) -> bool:
    today = today or today_msk()
    return today <= expiry


def fetch_rent_rows(
    spreadsheet_id: str = DEFAULT_SPREADSHEET_ID,
    gid: str = "0",
    timeout: int = 20,
) -> list[RentRow]:
    url = _csv_export_url(spreadsheet_id, gid)
    with urlopen(url, timeout=timeout) as response:
        text = response.read().decode("utf-8-sig")

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []

    result: list[RentRow] = []
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        name = row[0].strip()
        date_raw = row[1].strip() if len(row) > 1 else ""
        username = row[2].strip() if len(row) > 2 else ""
        expiry = parse_dd_mm(date_raw)
        if expiry is None:
            continue
        result.append(RentRow(project_name=name, expiry=expiry, username=username))
    return result


def find_rent_for_project(
    project_name: str,
    rows: list[RentRow],
) -> Optional[RentRow]:
    normalized = project_name.strip().casefold()
    for row in rows:
        if row.project_name.strip().casefold() == normalized:
            return row
    return None


def fetch_rent_status(
    project_name: str,
    spreadsheet_id: str,
    gid: str = "0",
) -> tuple[Optional[bool], Optional[date], Optional[str], Optional[str]]:
    """Returns (is_active, expiry_date, username, error_message)."""
    try:
        rows = fetch_rent_rows(spreadsheet_id, gid)
    except (URLError, TimeoutError, OSError) as exc:
        return None, None, None, str(exc)

    row = find_rent_for_project(project_name, rows)
    if row is None:
        return None, None, None, f"Проект «{project_name}» не найден в таблице"

    active = is_rent_active(row.expiry)
    return active, row.expiry, row.username, None
