import datetime
from typing import Optional

def format_time_12h(ts_str: Optional[str], include_seconds: bool = False) -> str:
    if not ts_str:
        return ""
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%H:%M:%S", "%H:%M", "%Y-%m-%dT%H:%M:%S"]:
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
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"]:
        try:
            dt = datetime.datetime.strptime(ts_str.strip(), fmt)
            date_part = dt.strftime("%Y-%m-%d")
            time_part = dt.strftime("%I:%M:%S %p" if include_seconds else "%I:%M %p").lstrip("0")
            return f"{date_part} {time_part}"
        except ValueError:
            continue
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

