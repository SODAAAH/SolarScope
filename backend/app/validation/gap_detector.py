import datetime
from typing import List, Dict, Any, Tuple
from collections import Counter

def parse_dt(ts: str) -> datetime.datetime | None:
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
        try:
            return datetime.datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return None

def analyze_sampling_intervals(
    timestamps: List[str],
    gap_threshold_minutes: float = 30.0
) -> Dict[str, Any]:
    if len(timestamps) < 2:
        return {
            "total_intervals": 0,
            "median_interval_minutes": 5.0,
            "interval_distribution": {},
            "gaps": [],
            "total_gap_duration_minutes": 0.0,
            "coverage_ratio": 1.0,
            "duplicate_timestamps": 0,
            "is_monotonic": True
        }

    dt_list: List[datetime.datetime] = []
    for ts in timestamps:
        parsed = parse_dt(ts)
        if parsed:
            dt_list.append(parsed)

    if len(dt_list) < 2:
        return {
            "total_intervals": 0,
            "median_interval_minutes": 5.0,
            "interval_distribution": {},
            "gaps": [],
            "total_gap_duration_minutes": 0.0,
            "coverage_ratio": 1.0,
            "duplicate_timestamps": 0,
            "is_monotonic": True
        }

    intervals_sec: List[float] = []
    gaps: List[Dict[str, Any]] = []
    duplicate_count = 0
    is_monotonic = True

    for i in range(len(dt_list) - 1):
        diff = (dt_list[i + 1] - dt_list[i]).total_seconds()
        if diff < 0:
            is_monotonic = False
        elif diff == 0:
            duplicate_count += 1
        else:
            intervals_sec.append(diff)
            diff_min = diff / 60.0
            if diff_min >= gap_threshold_minutes:
                gaps.append({
                    "start_time": dt_list[i].strftime("%Y-%m-%d %H:%M:%S"),
                    "end_time": dt_list[i + 1].strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_minutes": round(diff_min, 2),
                    "severity": "CRITICAL" if diff_min >= 60.0 else "WARNING"
                })

    intervals_min = [round(sec / 60.0, 1) for sec in intervals_sec]
    dist = dict(Counter(intervals_min))

    sorted_intervals = sorted(intervals_min)
    mid = len(sorted_intervals) // 2
    if len(sorted_intervals) % 2 == 0:
        median_int = (sorted_intervals[mid - 1] + sorted_intervals[mid]) / 2.0 if sorted_intervals else 5.0
    else:
        median_int = sorted_intervals[mid] if sorted_intervals else 5.0

    total_span_minutes = (dt_list[-1] - dt_list[0]).total_seconds() / 60.0 if dt_list else 0.0
    total_gap_duration = sum(g["duration_minutes"] for g in gaps)
    coverage = max(0.0, min(1.0, (total_span_minutes - total_gap_duration) / total_span_minutes)) if total_span_minutes > 0 else 1.0

    return {
        "total_intervals": len(intervals_sec),
        "median_interval_minutes": round(median_int, 2),
        "interval_distribution": dist,
        "gaps": gaps,
        "total_gap_duration_minutes": round(total_gap_duration, 2),
        "coverage_ratio": round(coverage, 4),
        "duplicate_timestamps": duplicate_count,
        "is_monotonic": is_monotonic
    }
