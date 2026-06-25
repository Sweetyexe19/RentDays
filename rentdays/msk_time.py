from datetime import date, datetime
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")
MSK_LABEL = "MSK"


def now_msk() -> datetime:
    return datetime.now(MSK)


def today_msk() -> date:
    return now_msk().date()


def format_msk_time() -> str:
    return now_msk().strftime("%H:%M:%S")


def format_msk_datetime() -> str:
    return now_msk().strftime("%d.%m.%Y %H:%M:%S") + f" {MSK_LABEL}"


def format_msk_short(dt: datetime) -> str:
    return dt.strftime("%H:%M")
