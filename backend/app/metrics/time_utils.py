import datetime
import math
from typing import Any, Optional
from zoneinfo import ZoneInfo

def resolve_zoneinfo(tz_name: Optional[str] = None) -> datetime.tzinfo:
    cleaned = (tz_name or "Asia/Manila").strip()
    try:
        return ZoneInfo(cleaned)
    except Exception:
        return datetime.timezone(datetime.timedelta(hours=8))

def parse_timestamp(val: Any, target_tz: str = "Asia/Manila") -> Optional[datetime.datetime]:
    if val is None or isinstance(val, bool):
        return None
    tz = resolve_zoneinfo(target_tz)

    if isinstance(val, datetime.datetime):
        dt = val
        if dt.tzinfo is not None:
            dt = dt.astimezone(tz)
        return dt.replace(tzinfo=None)

    if isinstance(val, datetime.date):
        return datetime.datetime(val.year, val.month, val.day, 0, 0, 0)

    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        num = float(val)
        if 20000.0 <= num <= 75000.0:
            base = datetime.datetime(1899, 12, 30)
            return base + datetime.timedelta(days=num)
        if num > 1e12:
            num = num / 1000.0
        if 946684800.0 <= num <= 4102444800.0:
            return datetime.datetime.fromtimestamp(num, tz=tz).replace(tzinfo=None)
        return None

    s = str(val).strip()
    if not s or s.lower() in ("none", "null", "nan", "na", "n/a", "--"):
        return None

    if s.replace(".", "", 1).isdigit():
        try:
            return parse_timestamp(float(s), target_tz=target_tz)
        except Exception:
            pass

    iso_candidate = s[:-1] + "+00:00" if s.endswith("Z") else s
    if len(iso_candidate) >= 5 and iso_candidate[-5] in ("+", "-") and iso_candidate[-4:].isdigit():
        iso_candidate = iso_candidate[:-2] + ":" + iso_candidate[-2:]

    try:
        dt = datetime.datetime.fromisoformat(iso_candidate)
        if dt.tzinfo is not None:
            dt = dt.astimezone(tz)
        return dt.replace(tzinfo=None)
    except ValueError:
        pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %I:%M %p",
        "%Y-%m-%d %I:%M:%S %p",
        "%Y-%m-%d %I:%M %p",
    ):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue

    return None

def format_time_12h(ts_str: Optional[str], include_seconds: bool = False) -> str:
    if not ts_str:
        return ""
    dt = parse_timestamp(ts_str)
    if dt is not None:
        if include_seconds:
            return dt.strftime("%I:%M:%S %p").lstrip("0")
        return dt.strftime("%I:%M %p").lstrip("0")
    for fmt in ["%H:%M:%S", "%H:%M"]:
        try:
            dt = datetime.datetime.strptime(ts_str.strip(), fmt)
            if include_seconds:
                return dt.strftime("%I:%M:%S %p").lstrip("0")
            return dt.strftime("%I:%M %p").lstrip("0")
        except ValueError:
            continue
    return ts_str

def format_datetime_12h(ts_str: Optional[str], include_seconds: bool = False) -> str:
    if not ts_str:
        return ""
    dt = parse_timestamp(ts_str)
    if dt is not None:
        date_part = dt.strftime("%m/%d/%Y")
        time_part = dt.strftime("%I:%M:%S %p" if include_seconds else "%I:%M %p").lstrip("0")
        return f"{date_part} {time_part}"
    return ts_str

def hour_index_to_12h(hour: int) -> str:
    h = hour % 24
    if h == 0:
        return "12 AM"
    elif h < 12:
        return f"{h} AM"
    elif h == 12:
        return "12 PM"
    else:
        return f"{h - 12} PM"

def format_date_mmddyyyy(date_str: Optional[str]) -> str:
    if not date_str:
        return ""
    s = date_str.strip().split(" ")[0].split("T")[0]
    for fmt in ["%Y-%m-%d", "%Y/%m/%d"]:
        try:
            dt = datetime.datetime.strptime(s, fmt)
            return dt.strftime("%m/%d/%Y")
        except ValueError:
            continue
    return s
