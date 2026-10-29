from typing import List, Dict, Any, Tuple
from backend.app.ingestion.models import CanonicalRecord

def detect_record_conflicts(
    records_a: List[CanonicalRecord],
    records_b: List[CanonicalRecord],
    tolerance_kw: float = 0.05
) -> Dict[str, Any]:
    if not records_a or not records_b:
        return {
            "has_overlap": False,
            "overlap_start": None,
            "overlap_end": None,
            "conflicting_points": 0,
            "conflicts": []
        }

    start_a, end_a = records_a[0].timestamp, records_a[-1].timestamp
    start_b, end_b = records_b[0].timestamp, records_b[-1].timestamp

    overlap_start = max(start_a, start_b)
    overlap_end = min(end_a, end_b)

    if overlap_start > overlap_end:
        return {
            "has_overlap": False,
            "overlap_start": None,
            "overlap_end": None,
            "conflicting_points": 0,
            "conflicts": []
        }

    map_a = {r.timestamp: r for r in records_a}
    conflicts: List[Dict[str, Any]] = []

    for r_b in records_b:
        ts = r_b.timestamp
        if ts in map_a:
            r_a = map_a[ts]
            pv_diff = abs(r_a.pv_power_kw - r_b.pv_power_kw)
            load_diff = abs(r_a.load_power_kw - r_b.load_power_kw)
            grid_diff = abs(r_a.grid_power_kw - r_b.grid_power_kw)
            batt_diff = abs(r_a.battery_power_kw - r_b.battery_power_kw)

            if max(pv_diff, load_diff, grid_diff, batt_diff) > tolerance_kw:
                conflicts.append({
                    "timestamp": ts,
                    "pv_diff_kw": round(pv_diff, 3),
                    "load_diff_kw": round(load_diff, 3),
                    "grid_diff_kw": round(grid_diff, 3),
                    "batt_diff_kw": round(batt_diff, 3),
                    "source_a_values": {
                        "pv": r_a.pv_power_kw,
                        "load": r_a.load_power_kw,
                        "grid": r_a.grid_power_kw,
                        "batt": r_a.battery_power_kw
                    },
                    "source_b_values": {
                        "pv": r_b.pv_power_kw,
                        "load": r_b.load_power_kw,
                        "grid": r_b.grid_power_kw,
                        "batt": r_b.battery_power_kw
                    }
                })

    return {
        "has_overlap": True,
        "overlap_start": overlap_start,
        "overlap_end": overlap_end,
        "conflicting_points": len(conflicts),
        "conflicts": conflicts[:50]
    }

def resolve_and_merge_records(
    records_existing: List[CanonicalRecord],
    records_new: List[CanonicalRecord],
    policy: str = "KEEP_EXISTING"
) -> List[CanonicalRecord]:
    if not records_existing:
        return sorted(records_new, key=lambda r: r.timestamp)
    if not records_new:
        return sorted(records_existing, key=lambda r: r.timestamp)

    combined_map: Dict[str, CanonicalRecord] = {}

    if policy == "REPLACE_OLDER":
        for r in records_existing:
            combined_map[r.timestamp] = r
        for r in records_new:
            combined_map[r.timestamp] = r
    else:
        for r in records_new:
            combined_map[r.timestamp] = r
        for r in records_existing:
            combined_map[r.timestamp] = r

    merged = list(combined_map.values())
    merged.sort(key=lambda r: r.timestamp)
    return merged

